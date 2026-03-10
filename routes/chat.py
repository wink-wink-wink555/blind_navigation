"""
统一聊天路由 - 多Agent调度中心
基于意图路由器将用户消息分发到不同的Agent处理
支持完整对话上下文传递
"""
import re
import requests
import json
from flask import Blueprint, request, session, jsonify
from utils.decorators import login_required
from services.router_agent import RouterAgent
from services.settings_agent import SettingsAgent
from services.deepseek_ai import DeepSeekAI
from services.baidu_map_mcp import BaiduMapMCP
from config import DEEPSEEK_CONFIG, BAIDU_MAP_CONFIG

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """统一聊天接口 - 意图路由 + 多Agent调度"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "请求数据为空"}), 400

        user_message = data.get('message', '').strip()
        user_location = data.get('user_location')
        chat_history = data.get('chat_history', [])

        if not user_message:
            return jsonify({"status": "error", "message": "请输入消息"}), 400

        user_id = session.get('user_id')

        # Step 1: 意图路由（带上下文，让Router看到对话脉络）
        router = RouterAgent(DEEPSEEK_CONFIG['api_key'])
        route_result = router.classify_intent(user_message, chat_history)

        if not route_result['success']:
            return _handle_chat(user_message, chat_history)

        intent = route_result['intent']
        confidence = route_result['confidence']
        extracted_info = route_result.get('extracted_info', {})

        print(f"[Chat] 意图={intent}, 置信度={confidence}")

        # Step 2: 分发到对应Agent（均带上下文）
        if intent == 'settings':
            return _handle_settings(user_message, user_id, chat_history)
        elif intent == 'map':
            return _handle_map(user_message, user_location, chat_history)
        elif intent == 'message':
            return _handle_message(user_message, extracted_info)
        else:
            return _handle_chat(user_message, chat_history)

    except Exception as e:
        print(f"[Chat] 异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "intent": "error",
            "message": f"服务异常：{str(e)}"
        }), 500


def _build_context_messages(chat_history, max_turns=20):
    """将前端对话历史转换为LLM消息格式，限制最大轮数防止token溢出"""
    messages = []
    recent = chat_history[-max_turns * 2:] if len(chat_history) > max_turns * 2 else chat_history
    for item in recent:
        role = item.get('role', 'user')
        content = item.get('content', '')
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})
    return messages


def _get_user_profile_context():
    """从 session 获取用户个人信息，构建 AI 可理解的用户画像描述"""
    user_settings = session.get('user_settings', {})
    name = user_settings.get('name', '用户')
    gender = user_settings.get('gender', '未指定')
    age = user_settings.get('age', '未指定')

    gender_term = ""
    if gender == "男":
        gender_term = "先生"
    elif gender == "女":
        gender_term = "女士"

    age_desc = ""
    if age == "老年":
        age_desc = "年长的"
    elif age == "青年":
        age_desc = "年轻的"
    elif age == "中年":
        age_desc = "中年"

    full_name = f"{name}{gender_term}" if gender_term else name
    profile = f"用户是{age_desc}{full_name}。" if age_desc else f"用户是{full_name}。"
    profile += f"请在回复时称呼用户为「{full_name}」。"
    return profile, user_settings


def _handle_settings(user_message, user_id, chat_history=None):
    """处理设置查询/修改请求"""
    agent = SettingsAgent(DEEPSEEK_CONFIG['api_key'])
    user_profile, _ = _get_user_profile_context()
    result = agent.process(user_message, user_id, chat_history, user_profile)

    if result.get('success') and result.get('updated_settings'):
        session['user_settings'] = result['updated_settings']
        session.modified = True
        # 同步到全局变量，使盲道转向语音也能使用最新设置
        from routes.main import update_current_user_settings
        update_current_user_settings(result['updated_settings'])

    return jsonify({
        "status": "success" if result['success'] else "error",
        "intent": "settings",
        "content": result['response'],
        "changes": result.get('changes', []),
        "updated_settings": result.get('updated_settings')
    })


def _handle_map(user_message, user_location, chat_history=None):
    """处理地图查询请求 - 复用现有ReAct循环，带对话上下文和用户信息"""
    ai_assistant = DeepSeekAI(DEEPSEEK_CONFIG['api_key'])
    baidu_mcp = BaiduMapMCP(BAIDU_MAP_CONFIG['api_key'])

    user_profile, _ = _get_user_profile_context()

    context_summary = f"[用户信息] {user_profile}\n"
    if chat_history:
        recent = chat_history[-6:]
        parts = []
        for item in recent:
            role_label = "用户" if item.get('role') == 'user' else "助手"
            parts.append(f"{role_label}: {item.get('content', '')}")
        context_summary += "[之前的对话上下文]\n" + "\n".join(parts) + "\n[当前问题]\n"

    full_message = context_summary + user_message

    tool_history = []
    max_iterations = 10

    for iteration in range(max_iterations):
        print(f"[Chat-Map] === 第 {iteration + 1} 轮思考 ===")

        intent_result = ai_assistant.understand_user_intent(
            full_message, user_location, tool_history
        )

        if not intent_result['success']:
            return jsonify({
                "status": "error",
                "intent": "map",
                "content": "地图AI理解失败，请重试",
                "tool_history": tool_history
            }), 400

        intent = intent_result['intent']
        intent_type = intent.get('type')

        if intent_type == 'answer':
            return jsonify({
                "status": "success",
                "intent": "map",
                "content": intent.get('content', ''),
                "reasoning": intent.get('reasoning', ''),
                "tool_history": tool_history,
                "iterations": iteration + 1
            })

        elif intent_type == 'tool_call':
            action = intent.get('action')
            params = intent.get('params', {})
            reasoning = intent.get('reasoning', '')

            print(f"[Chat-Map] 调用工具: {action}, 参数: {params}")

            result = _execute_map_tool(baidu_mcp, action, params)

            tool_history.append({
                'action': action,
                'params': params,
                'reasoning': reasoning,
                'result': result
            })
            continue

        else:
            return jsonify({
                "status": "error",
                "intent": "map",
                "content": f"未知AI决策类型: {intent_type}",
                "tool_history": tool_history
            }), 400

    return jsonify({
        "status": "error",
        "intent": "map",
        "content": f"问题过于复杂，已达到最大处理步骤（{max_iterations}步）",
        "tool_history": tool_history
    }), 400


def _execute_map_tool(baidu_mcp, action, params):
    """执行地图工具调用"""
    try:
        if action == 'geocoding':
            return baidu_mcp.geocoding(
                params.get('address', ''), params.get('city')
            )
        elif action == 'reverse_geocoding':
            return baidu_mcp.reverse_geocoding(
                params.get('lat'), params.get('lng')
            )
        elif action == 'search_places':
            return baidu_mcp.search_nearby_places(
                params.get('query', ''), params.get('lat'),
                params.get('lng'), params.get('radius', 1000)
            )
        elif action == 'route_planning':
            return baidu_mcp.calculate_route(
                params.get('origin_lat'), params.get('origin_lng'),
                params.get('dest_lat'), params.get('dest_lng'),
                mode='walking'
            )
        else:
            return {'success': False, 'error': f'不支持的工具: {action}'}
    except Exception as e:
        return {'success': False, 'error': f'工具执行异常: {str(e)}'}


def _handle_message(user_message, extracted_info):
    """处理发送消息请求"""
    message_content = extracted_info.get('message_content', '')

    if not message_content:
        patterns = [
            r'(?:发给|发送给?)(?:家属|家人)(?:消息|信息)?[：:]\s*(.+)',
            r'(?:给|跟)(?:家属|家人)(?:说|发|发送)[：:]?\s*(.+)',
            r'(?:告诉|通知)(?:家属|家人)[：:]?\s*(.+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, user_message)
            if match:
                message_content = match.group(1).strip()
                break

    if not message_content:
        message_content = _extract_message_via_llm(user_message)

    if message_content:
        return jsonify({
            "status": "success",
            "intent": "message",
            "content": f"好的，已经帮您把消息发送给家属了，内容是：「{message_content}」。家属收到后会了解您的情况，请放心。"
        })
    else:
        return jsonify({
            "status": "success",
            "intent": "message",
            "content": "您想给家属发什么消息呢？您可以直接说，比如「帮我发给家属消息：我已经到了」，我来帮您发送。"
        })


def _extract_message_via_llm(user_message):
    """使用LLM提取消息内容（正则匹配失败时的兜底）"""
    try:
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_CONFIG["api_key"]}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': DEEPSEEK_CONFIG['model'],
            'messages': [
                {'role': 'system', 'content': '从用户的话中提取要发送给家属的消息内容。只返回消息内容本身，不要加任何额外说明。如果无法提取，返回空字符串。'},
                {'role': 'user', 'content': user_message}
            ],
            'temperature': 0.1,
            'max_tokens': 200
        }
        response = requests.post(
            DEEPSEEK_CONFIG['base_url'], headers=headers, json=data
        )
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
    except Exception:
        pass
    return ''


def _handle_chat(user_message, chat_history=None):
    """处理普通闲聊 - 带完整对话上下文和用户个人信息"""
    try:
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_CONFIG["api_key"]}',
            'Content-Type': 'application/json'
        }

        user_profile, _ = _get_user_profile_context()

        system_msg = {
            'role': 'system',
            'content': (
                '你是一个温暖、耐心的AI助手，是一款专为视障人士设计的导航辅助系统的一部分。\n'
                '你的用户是视障人士（盲人或低视力），请始终牢记以下原则：\n'
                '- 用温暖、亲切、鼓励的语气与用户交流，让他们感受到陪伴和关怀\n'
                '- 回复要简洁清晰，因为内容会被语音播报给用户，避免过长或复杂的句式\n'
                '- 适时给予鼓励和肯定，比如"您做得很好"、"没问题，我来帮您"\n'
                '- 当用户遇到困难时，主动安抚并给出明确的引导\n'
                '- 不要使用"看一下"、"看看"等视觉相关的表述，改用"了解一下"、"听听"等\n'
                '- 对用户的每一个请求都认真对待，体现尊重和耐心\n\n'
                f'{user_profile}\n'
                '你可以帮助用户：\n'
                '1. 查询或修改系统设置（语音速度、音量、鼓励功能等）\n'
                '2. 查询地图信息（路线规划、附近搜索等）\n'
                '3. 给家属发送消息\n'
                '4. 日常聊天陪伴，缓解用户的孤独感\n'
                '请在对话中使用用户的称呼，让他们感到被重视。'
            )
        }

        messages = [system_msg]
        if chat_history:
            messages.extend(_build_context_messages(chat_history))
        messages.append({'role': 'user', 'content': user_message})

        data = {
            'model': DEEPSEEK_CONFIG['model'],
            'messages': messages,
            'temperature': 0.7,
            'max_tokens': 500
        }
        response = requests.post(
            DEEPSEEK_CONFIG['base_url'], headers=headers, json=data
        )
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            return jsonify({
                "status": "success",
                "intent": "chat",
                "content": content
            })
        else:
            return jsonify({
                "status": "error",
                "intent": "chat",
                "content": "AI服务暂时不可用，请稍后再试"
            }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "intent": "chat",
            "content": f"对话异常：{str(e)}"
        }), 500
