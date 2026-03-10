"""
地图相关路由 - 位置更新、地图服务、AI助手
"""
from flask import Blueprint, request, session, jsonify
import time
import geopy.distance
from utils.decorators import login_required
from services.baidu_map_mcp import BaiduMapMCP
from services.deepseek_ai import DeepSeekAI
from config import BAIDU_MAP_CONFIG, DEEPSEEK_CONFIG
from utils.voice_utils import ai_speak, stop_ai_speak, is_ai_speaking

map_bp = Blueprint('map', __name__)

# 位置数据存储
user_locations = {}  # 格式: {user_id: {'lat': latitude, 'lng': longitude, 'timestamp': timestamp}}


@map_bp.route('/update_location', methods=['POST'])
@login_required
def update_location():
    """更新用户位置"""
    user_id = session.get('user_id')
    data = request.get_json()

    if not data or 'lat' not in data or 'lng' not in data:
        return jsonify({"status": "error", "message": "位置数据不完整"}), 400

    # 更新用户位置
    user_locations[user_id] = {
        'lat': data['lat'],
        'lng': data['lng'],
        'timestamp': time.time()
    }

    return jsonify({
        "status": "success",
        "message": "位置已更新"
    })


@map_bp.route('/get_location/<int:user_id>', methods=['GET'])
@login_required
def get_location(user_id):
    """获取指定用户的位置"""
    # 检查权限（只允许查看自己或关联的家属/被照顾者的位置）
    current_user_id = session.get('user_id')

    # 这里应该有更完善的权限检查逻辑，例如家属关系验证
    # 暂时简化为允许查看所有用户位置

    if user_id in user_locations:
        # 检查位置数据是否过期（例如5分钟）
        if time.time() - user_locations[user_id]['timestamp'] > 300:
            return jsonify({
                "status": "warning",
                "message": "位置数据已过期",
                "location": user_locations[user_id]
            })

        return jsonify({
            "status": "success",
            "location": user_locations[user_id]
        })
    else:
        return jsonify({
            "status": "error",
            "message": "未找到用户位置数据"
        }), 404


@map_bp.route('/nearby_blindways', methods=['GET'])
@login_required
def nearby_blindways():
    """获取附近的盲道数据（示例数据）"""
    # 在实际应用中，这里应该连接到盲道数据库或API
    # 现在返回示例数据用于演示

    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    if not lat or not lng:
        return jsonify({"status": "error", "message": "请提供位置参数"}), 400

    # 示例盲道数据（在实际应用中应从数据库获取）
    sample_blindways = [
        {
            'id': 1,
            'name': '中心广场盲道',
            'points': [
                {'lat': lat + 0.001, 'lng': lng + 0.001},
                {'lat': lat + 0.002, 'lng': lng + 0.001},
                {'lat': lat + 0.002, 'lng': lng - 0.001}
            ]
        },
        {
            'id': 2,
            'name': '南街盲道',
            'points': [
                {'lat': lat - 0.0005, 'lng': lng - 0.0005},
                {'lat': lat - 0.001, 'lng': lng - 0.001},
                {'lat': lat - 0.002, 'lng': lng - 0.001}
            ]
        }
    ]

    # 计算每条盲道到用户的距离
    user_coord = (lat, lng)
    for blindway in sample_blindways:
        min_distance = float('inf')
        for point in blindway['points']:
            point_coord = (point['lat'], point['lng'])
            distance = geopy.distance.distance(user_coord, point_coord).meters
            min_distance = min(min_distance, distance)

        blindway['distance'] = round(min_distance, 1)  # 四舍五入到小数点后1位

    # 按距离排序
    sample_blindways.sort(key=lambda x: x['distance'])

    return jsonify({
        "status": "success",
        "blindways": sample_blindways
    })


@map_bp.route('/ai_map_assistant', methods=['POST'])
@login_required
def ai_map_assistant():
    """AI地图助手接口 - ReAct模式迭代式调用"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "请求数据为空"}), 400
        
        user_message = data.get('message', '').strip()
        user_location = data.get('user_location')  # 可选的用户位置信息
        
        if not user_message:
            return jsonify({"status": "error", "message": "请输入您的问题"}), 400
        
        print(f"\n{'='*60}")
        print(f"[Agent工作流] 用户问题: {user_message}")
        print(f"{'='*60}\n")
        
        # 创建AI助手和地图服务实例
        ai_assistant = DeepSeekAI(DEEPSEEK_CONFIG['api_key'])
        baidu_mcp = BaiduMapMCP(BAIDU_MAP_CONFIG['api_key'])
        
        # 工具调用历史
        tool_history = []
        max_iterations = 10  # 最大迭代次数，防止无限循环
        
        # 迭代式调用循环
        for iteration in range(max_iterations):
            print(f"\n[Agent工作流] ========== 第 {iteration + 1} 轮思考 ==========")
            
            # AI思考下一步行动
            intent_result = ai_assistant.understand_user_intent(
                user_message, 
                user_location, 
                tool_history
            )
            
            if not intent_result['success']:
                return jsonify({
                    "status": "error", 
                    "message": "AI理解失败",
                    "details": intent_result.get('error', '未知错误'),
                    "tool_history": tool_history
                }), 400
            
            intent = intent_result['intent']
            intent_type = intent.get('type')
            
            print(f"[Agent工作流] AI决策: type={intent_type}")
            print(f"[Agent工作流] 推理: {intent.get('reasoning', '')}")
            
            # 情况1: AI给出最终答案
            if intent_type == 'answer':
                print(f"[Agent工作流] ✓ 完成！共执行 {len(tool_history)} 个工具调用")
                return jsonify({
                    "status": "success",
                    "type": "answer",
                    "content": intent.get('content', ''),
                    "reasoning": intent.get('reasoning', ''),
                    "user_question": user_message,
                    "tool_history": tool_history,
                    "iterations": iteration + 1
                })
            
            # 情况2: AI需要调用工具
            elif intent_type == 'tool_call':
                action = intent.get('action')
                params = intent.get('params', {})
                reasoning = intent.get('reasoning', '')
                
                print(f"[Agent工作流] → 调用工具: {action}")
                print(f"[Agent工作流] 参数: {params}")
                
                # 执行工具调用
                result = _execute_tool(baidu_mcp, action, params)
                
                # 记录到历史
                tool_history.append({
                    'action': action,
                    'params': params,
                    'reasoning': reasoning,
                    'result': result
                })
                
                if result.get('success'):
                    print(f"[Agent工作流] ✓ 工具执行成功")
                else:
                    print(f"[Agent工作流] ✗ 工具执行失败: {result.get('error', '')}")
                
                # 继续下一轮循环
                continue
            
            else:
                # 未知的intent类型
                return jsonify({
                    "status": "error",
                    "message": f"未知的AI决策类型: {intent_type}",
                    "tool_history": tool_history
                }), 400
        
        # 达到最大迭代次数
        print(f"[Agent工作流] ⚠ 达到最大迭代次数 {max_iterations}")
        return jsonify({
            "status": "error",
            "message": f"问题过于复杂，已达到最大处理步骤（{max_iterations}步）",
            "tool_history": tool_history
        }), 400
            
    except Exception as e:
        print(f"AI地图助手错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"服务异常: {str(e)}"}), 500


def _execute_tool(baidu_mcp, action, params):
    """执行单个工具调用"""
    try:
        if action == 'geocoding':
            return baidu_mcp.geocoding(
                params.get('address', ''), 
                params.get('city')
            )
        
        elif action == 'reverse_geocoding':
            return baidu_mcp.reverse_geocoding(
                params.get('lat'), 
                params.get('lng')
            )
        
        elif action == 'search_places':
            return baidu_mcp.search_nearby_places(
                params.get('query', ''), 
                params.get('lat'), 
                params.get('lng'), 
                params.get('radius', 1000)
            )
        
        elif action == 'route_planning':
            # 视障人士出行辅助系统 - 仅支持步行模式
            return baidu_mcp.calculate_route(
                params.get('origin_lat'), 
                params.get('origin_lng'),
                params.get('dest_lat'), 
                params.get('dest_lng'),
                mode='walking'  # 强制使用步行模式
            )
        
        else:
            return {
                'success': False,
                'error': f'不支持的工具: {action}'
            }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'工具执行异常: {str(e)}'
        }


@map_bp.route('/test_deepseek', methods=['POST'])
@login_required
def deepseek_api_test():
    """测试DeepSeek API连接"""
    try:
        data = request.get_json()
        test_message = data.get('message', '你好')
        
        ai_assistant = DeepSeekAI(DEEPSEEK_CONFIG['api_key'])
        result = ai_assistant.understand_user_intent(test_message)
        
        return jsonify({
            "status": "success" if result['success'] else "error",
            "result": result
        })
        
    except Exception as e:
        print(f"DeepSeek测试错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"测试异常: {str(e)}"}), 500


# ========== AI助手语音播报功能 ==========

@map_bp.route('/ai_speak', methods=['POST'])
@login_required
def ai_speak_api():
    """
    AI助手语音播报接口
    播放AI回复的语音
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "请求数据为空"}), 400
        
        text = data.get('text', '').strip()
        if not text:
            return jsonify({"status": "error", "message": "播报文本为空"}), 400
        
        # 从 session['user_settings'] 中获取语音设置
        stored_settings = session.get('user_settings', {})
        user_settings = {
            "voice_speed": stored_settings.get('voice_speed', '中等'),
            "voice_volume": stored_settings.get('voice_volume', '中等')
        }
        
        print(f"[AI语音API] 开始播报: '{text[:50]}...'")
        
        # 调用语音播放函数
        result = ai_speak(text, user_settings)
        
        if result:
            return jsonify({
                "status": "success",
                "message": "开始播放语音",
                "is_playing": True
            })
        else:
            return jsonify({
                "status": "error",
                "message": "语音播放启动失败"
            }), 500
            
    except Exception as e:
        print(f"AI语音播报错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"语音播报异常: {str(e)}"}), 500


@map_bp.route('/ai_speak_stop', methods=['POST'])
@login_required
def ai_speak_stop_api():
    """
    停止AI助手语音播报
    """
    try:
        print("[AI语音API] 收到停止请求")
        
        result = stop_ai_speak()
        
        return jsonify({
            "status": "success",
            "message": "语音已停止",
            "is_playing": False
        })
        
    except Exception as e:
        print(f"停止AI语音错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"停止语音异常: {str(e)}"}), 500


@map_bp.route('/ai_speak_status', methods=['GET'])
@login_required
def ai_speak_status_api():
    """
    获取AI助手语音播放状态
    """
    try:
        is_playing = is_ai_speaking()
        
        return jsonify({
            "status": "success",
            "is_playing": is_playing
        })
        
    except Exception as e:
        print(f"获取AI语音状态错误: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

