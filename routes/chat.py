"""
统一聊天路由 - 多Agent调度中心
基于意图路由器将用户消息分发到不同的Agent处理
支持完整对话上下文传递

所有 LLM/STT 调用都通过 ai_provider 按用户的 AI 设置（云端/本地）路由。
"""
import os
import re
import requests
import json
import tempfile
from flask import Blueprint, request, session, jsonify
from utils.decorators import login_required
from services.router_agent import RouterAgent
from services.settings_agent import SettingsAgent
from services.deepseek_ai import DeepSeekAI
from services.baidu_map_mcp import BaiduMapMCP
from services.speech_agent import SpeechToTextAgent, StutterCorrectionAgent
from services.ai_provider import (
    get_text_llm_config, get_stt_config, chat_completion as unified_chat_completion
)
from config import BAIDU_MAP_CONFIG
from models.database import get_family_contacts, find_family_contact_by_name
from utils.email_utils import send_family_email

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

        # 取当前用户激活的文本模型配置（云端 or 本地 Ollama）
        text_cfg = get_text_llm_config(user_id)

        # Step 1: 意图路由（带上下文，让Router看到对话脉络）
        router = RouterAgent(text_cfg['api_key'], text_cfg['base_url'], text_cfg['model'])
        route_result = router.classify_intent(user_message, chat_history)

        if not route_result['success']:
            return _handle_chat(user_message, chat_history, user_id)

        intent = route_result['intent']
        confidence = route_result['confidence']
        extracted_info = route_result.get('extracted_info', {})

        print(f"[Chat] 意图={intent}, 置信度={confidence}")

        # Step 2: 分发到对应Agent（均带上下文）
        if intent == 'settings':
            return _handle_settings(user_message, user_id, chat_history, text_cfg)
        elif intent == 'map':
            return _handle_map(user_message, user_location, chat_history, user_id, text_cfg)
        elif intent == 'message':
            return _handle_message(user_message, extracted_info, user_id)
        else:
            return _handle_chat(user_message, chat_history, user_id)

    except Exception as e:
        print(f"[Chat] 异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "intent": "error",
            "message": f"服务异常：{str(e)}"
        }), 500


@chat_bp.route('/speech_to_text', methods=['POST'])
@login_required
def speech_to_text():
    """
    语音转文字接口 - 接收音频文件，返回识别文本（经口吃纠正处理）
    根据当前用户的 AI 设置自动选择云端 / 本地 STT，
    口吃纠正使用当前激活的文本模型。
    """
    try:
        if 'audio' not in request.files:
            return jsonify({"status": "error", "message": "未收到音频文件"}), 400

        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"status": "error", "message": "音频文件为空"}), 400

        user_id = session.get('user_id')
        stt_cfg = get_stt_config(user_id)
        text_cfg = get_text_llm_config(user_id)

        tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
        os.makedirs(tmp_dir, exist_ok=True)

        tmp_path = os.path.join(tmp_dir, f'stt_temp_{user_id or "0"}.wav')
        audio_file.save(tmp_path)
        print(f"[STT] 音频文件已保存: {tmp_path}, 大小: {os.path.getsize(tmp_path)} bytes "
              f"(deployment={stt_cfg['deployment']}, model={stt_cfg['model']})")

        stt_agent = SpeechToTextAgent(
            api_key=stt_cfg['api_key'],
            model=stt_cfg['model'],
            deployment=stt_cfg['deployment'],
            base_url=stt_cfg.get('base_url', '')
        )
        stt_result = stt_agent.transcribe(tmp_path)

        try:
            os.remove(tmp_path)
        except OSError:
            pass

        if not stt_result['success']:
            return jsonify({
                "status": "error",
                "message": stt_result['error']
            }), 400

        raw_text = stt_result['text']

        if not raw_text.strip():
            return jsonify({
                "status": "error",
                "message": "未识别到有效语音内容，请重新录制"
            }), 400

        # 口吃纠正使用当前文本模型（云端或 Ollama 同样适用）
        stutter_agent = StutterCorrectionAgent(
            api_key=text_cfg['api_key'],
            base_url=text_cfg['base_url'],
            model=text_cfg['model']
        )
        correction_result = stutter_agent.correct(raw_text)

        final_text = correction_result['corrected'] if correction_result['success'] else raw_text

        return jsonify({
            "status": "success",
            "text": final_text,
            "raw_text": raw_text,
            "has_stutter": correction_result.get('has_stutter', False)
        })

    except Exception as e:
        print(f"[STT] 接口异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"语音识别服务异常：{str(e)}"
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


def _handle_settings(user_message, user_id, chat_history=None, text_cfg=None):
    """处理设置查询/修改请求"""
    if text_cfg is None:
        text_cfg = get_text_llm_config(user_id)
    agent = SettingsAgent(text_cfg['api_key'], text_cfg['base_url'], text_cfg['model'])
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


def _handle_map(user_message, user_location, chat_history=None, user_id=None, text_cfg=None):
    """处理地图查询请求 - 复用现有ReAct循环，带对话上下文和用户信息"""
    if text_cfg is None:
        text_cfg = get_text_llm_config(user_id)
    ai_assistant = DeepSeekAI(text_cfg['api_key'], text_cfg['base_url'], text_cfg['model'])
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


def _handle_message(user_message, extracted_info, user_id=None):
    """处理发送消息请求 — 真正通过邮件发送给家属"""
    if user_id is None:
        user_id = session.get('user_id')
    user_profile, user_settings = _get_user_profile_context()
    sender_name = user_settings.get('name', '用户')

    # 1. 提取消息内容和收件人
    message_content = extracted_info.get('message_content', '')
    recipient_name = extracted_info.get('recipient', '')

    if not message_content:
        patterns = [
            r'(?:发给|发送给?)(.+?)(?:消息|信息|说|：|:)\s*(.+)',
            r'(?:给|跟)(.+?)(?:说|发|发送|发消息)[：:]?\s*(.+)',
            r'(?:告诉|通知)(.+?)[：:]?\s*(.+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, user_message)
            if match:
                possible_recipient = match.group(1).strip()
                message_content = match.group(2).strip()
                if not recipient_name and possible_recipient not in ('家属', '家人'):
                    recipient_name = possible_recipient
                break

    if not message_content:
        message_content = _extract_message_via_llm(user_message, user_id)

    if not message_content:
        reply = _generate_message_reply(user_profile, '', None, user_id=user_id)
        return jsonify({"status": "success", "intent": "message", "content": reply})

    # 2. 查找家属联系人
    contacts, _ = get_family_contacts(user_id)

    if not contacts:
        return jsonify({
            "status": "success",
            "intent": "message",
            "content": "您还没有添加家属联系人哦，请先在设置中添加家属的称呼和邮箱，我就能帮您发消息了。"
        })

    target_contact = None

    if recipient_name:
        target_contact = find_family_contact_by_name(user_id, recipient_name)

    if not target_contact and len(contacts) == 1:
        target_contact = contacts[0]

    if not target_contact and len(contacts) > 1:
        names = '、'.join([c['name'] for c in contacts])
        return jsonify({
            "status": "success",
            "intent": "message",
            "content": f"您有多个家属联系人（{names}），请告诉我要发给谁呢？"
        })

    # 3. 发送邮件
    success, msg = send_family_email(
        to_email=target_contact['email'],
        sender_name=sender_name,
        message_content=message_content
    )

    # 4. 生成自然语言回复
    reply = _generate_message_reply(
        user_profile, message_content, target_contact['name'], success, user_id=user_id
    )

    return jsonify({
        "status": "success",
        "intent": "message",
        "content": reply
    })


def _generate_message_reply(user_profile, message_content, recipient_name,
                            send_success=None, user_id=None):
    """使用当前激活的文本模型生成自然回复"""
    if message_content and send_success is True:
        prompt = (
            f'{user_profile}\n'
            f'你是视障导航系统的AI助手，用户刚让你帮忙通过邮件发了一条消息给{recipient_name}，内容是：「{message_content}」。邮件已经成功发送。\n'
            '请用1句温暖自然的话确认消息已发送。要求：\n'
            '- 提及发给了谁、消息内容的关键词，让用户确认发对了\n'
            '- 语气亲切，不要机械化\n'
            '- 不超过30个字\n'
            '- 每次措辞要有变化'
        )
    elif message_content and send_success is False:
        prompt = (
            f'{user_profile}\n'
            f'你是视障导航系统的AI助手，用户让你帮忙给{recipient_name}发消息，但邮件发送失败了。\n'
            '请用1句话温和地告知用户发送失败，建议稍后重试。要求：\n'
            '- 语气安抚，不要让用户焦虑\n'
            '- 不超过25个字'
        )
    else:
        prompt = (
            f'{user_profile}\n'
            '你是视障导航系统的AI助手，用户想给家属发消息但没说清楚内容。\n'
            '请用1句话温和地询问要发什么。要求：\n'
            '- 语气自然亲切\n'
            '- 不超过20个字'
        )

    result = unified_chat_completion(
        user_id,
        messages=[{'role': 'system', 'content': prompt}],
        temperature=0.8,
        max_tokens=100
    )
    if result['success']:
        return result['content']

    if message_content and send_success is True:
        return f'已把消息通过邮件发给{recipient_name}了：「{message_content}」'
    elif message_content and send_success is False:
        return '抱歉，邮件发送失败了，请稍后再试一下。'
    return '您想给家属说什么呢？'


def _extract_message_via_llm(user_message, user_id=None):
    """使用当前激活的文本模型提取消息内容（正则匹配失败时兜底）"""
    result = unified_chat_completion(
        user_id,
        messages=[
            {'role': 'system', 'content': '从用户的话中提取要发送给家属的消息内容。只返回消息内容本身，不要加任何额外说明。如果无法提取，返回空字符串。'},
            {'role': 'user', 'content': user_message}
        ],
        temperature=0.1,
        max_tokens=200
    )
    return result['content'] if result['success'] else ''


def _handle_chat(user_message, chat_history=None, user_id=None):
    """处理普通闲聊 - 带完整对话上下文和用户个人信息"""
    user_profile, _ = _get_user_profile_context()

    system_msg = {
        'role': 'system',
        'content': (
            '你是一款视障导航系统的AI助手，用户是盲人或低视力人士，你的回复会被语音播报。\n\n'
            '⚠️ 回复规则：\n'
            '- 控制在1~3句话，不超过60个字\n'
            '- 禁止列举、排比、长篇大论，直接回答\n'
            '- 每次回复的措辞和句式要自然多样，不要反复使用同一种开头或结尾\n\n'
            '语言规则：\n'
            '- 语气温暖亲切，像朋友聊天一样自然\n'
            '- 禁止"看一下/看看/看到"等视觉表述，用"了解/听听/感受"代替\n'
            '- 不要建议用户乘坐公交、地铁、打车等，用户只能步行出行\n'
            f'- {user_profile}\n'
            '- 用用户的称呼来称呼他们，但不要每句话都以称呼开头'
        )
    }

    messages = [system_msg]
    if chat_history:
        messages.extend(_build_context_messages(chat_history))
    messages.append({'role': 'user', 'content': user_message})

    result = unified_chat_completion(
        user_id, messages=messages, temperature=0.7, max_tokens=200
    )

    if result['success']:
        return jsonify({
            "status": "success",
            "intent": "chat",
            "content": result['content']
        })

    return jsonify({
        "status": "error",
        "intent": "chat",
        "content": result.get('error') or "AI服务暂时不可用，请稍后再试"
    }), 500
