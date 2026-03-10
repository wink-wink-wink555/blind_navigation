"""
DeepSeek AI助手类，用于理解用户自然语言并调用MCP功能
"""
import requests
import json
import re
from config import DEEPSEEK_CONFIG


class DeepSeekAI:
    """DeepSeek AI助手类，用于理解用户自然语言并调用MCP功能"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.system_prompt = """你是地图服务Agent，采用ReAct模式迭代调用工具。

重要背景：你的用户是视障人士（盲人或低视力），你的回答将通过语音播报给他们。
因此在给出最终answer时，请严格遵循以下原则：
- 用温暖、清晰的语气回答，让用户感到安心
- **绝对不要使用"向北"、"向南"、"向东"、"向西"、"东北"、"西南"等绝对方位词**，视障用户无法判断东南西北。必须改用相对方向：左转、右转、向前走、往回走等
- 描述路线时用简洁、明确的相对方向指引（如"向前走约200米，然后左转"），每一步都要清晰
- 不要使用"看到"、"看一下"等视觉表述，改用"经过"、"到达"、"路过"、"会听到"等
- 提供距离和大致步行时间，帮助用户做好心理准备
- 如果路线中有明显的声音或触感标志物（如"经过一个十字路口"、"路边有栏杆"），可以提及帮助定位
- 适时给予鼓励，如"这段路不远，很方便到达"、"放心，路线很简单"

工具列表：
1. geocoding: 地址→坐标(BD-09)
   参数: {"address": "地址", "city": "城市"}
   ⚠️ 从地址中提取城市名传入city参数！例："上海人民广场"→{"address":"人民广场","city":"上海"}

2. reverse_geocoding: 坐标→地址
   参数: {"lat": 纬度, "lng": 经度}

3. search_places: 搜索附近地点
   参数: {"query": "关键词", "lat": 纬度, "lng": 经度, "radius": 半径}

4. route_planning: 路线规划（仅支持步行，面向视障人士）
   参数: {"origin_lat": 起点纬, "origin_lng": 起点经, "dest_lat": 终点纬, "dest_lng": 终点经}
   ⚠️ 本系统专为视障人士设计，路线规划仅支持步行模式，不支持驾车、骑行等其他方式

返回格式（纯JSON，无markdown）：
调用工具：{"type":"tool_call","action":"工具名","params":{参数},"reasoning":"原因"}
给出答案：{"type":"answer","content":"回答内容","reasoning":"原因"}

规则：
- 路线规划前必须先用geocoding获取坐标
- 调用geocoding时必须提取并传入city参数
- confidence<40时在reasoning中提示"置信度低"
- 一次一个工具，观察结果再决定下一步
- 避免重复调用

示例：
用户："从上海人民广场到上海博物馆怎么走？"
步骤1：{"type":"tool_call","action":"geocoding","params":{"address":"人民广场","city":"上海"},"reasoning":"获取起点坐标"}
步骤2：{"type":"tool_call","action":"geocoding","params":{"address":"博物馆","city":"上海"},"reasoning":"获取终点坐标"}
步骤3：{"type":"tool_call","action":"route_planning","params":{"origin_lat":31.23,"origin_lng":121.47,"dest_lat":31.23,"dest_lng":121.48},"reasoning":"规划步行路线"}
步骤4：{"type":"answer","content":"从人民广场到上海博物馆步行约500米，大概需要6分钟。出发后向前走约300米，然后左转再走200米就到了，这段路不远，很方便到达。","reasoning":"路线规划完成"}
"""
    
    def understand_user_intent(self, user_message, user_location=None, tool_history=None):
        """
        理解用户意图并返回相应的MCP操作
        
        Args:
            user_message: 用户的问题
            user_location: 用户位置 {"lat": 纬度, "lng": 经度}
            tool_history: 工具调用历史 [{"action": "工具名", "params": {...}, "result": {...}}, ...]
        """
        try:
            print(f"[Agent调试] 开始处理用户消息: {user_message}")
            
            # 构建包含用户位置信息的消息
            context_message = user_message
            if user_location:
                context_message += f"\n\n[用户当前位置: 纬度{user_location['lat']}, 经度{user_location['lng']}]"
            
            # 构建对话历史
            messages = [{'role': 'system', 'content': self.system_prompt}]
            
            # 添加初始用户问题
            messages.append({'role': 'user', 'content': context_message})
            
            # 如果有工具调用历史，添加到对话中
            if tool_history and len(tool_history) > 0:
                print(f"[Agent调试] 工具调用历史: {len(tool_history)}条记录")
                
                for i, history_item in enumerate(tool_history):
                    # AI的工具调用决策
                    ai_decision = {
                        "type": "tool_call",
                        "action": history_item['action'],
                        "params": history_item['params'],
                        "reasoning": history_item.get('reasoning', '')
                    }
                    messages.append({'role': 'assistant', 'content': json.dumps(ai_decision, ensure_ascii=False)})
                    
                    # 工具执行结果
                    tool_result_message = f"工具 {history_item['action']} 执行结果：\n{json.dumps(history_item['result'], ensure_ascii=False, indent=2)}"
                    messages.append({'role': 'user', 'content': tool_result_message})
                    
                    print(f"[Agent调试] 第{i+1}步: {history_item['action']} -> 成功={history_item['result'].get('success', False)}")
            
            print(f"[Agent调试] 构建的对话消息数: {len(messages)}")
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': DEEPSEEK_CONFIG['model'],
                'messages': messages,
                'temperature': 0.1,
                'max_tokens': 800
            }
            
            print(f"[DeepSeek调试] 请求URL: {DEEPSEEK_CONFIG['base_url']}")
            print(f"[DeepSeek调试] 请求数据: {data}")
            
            response = self.session.post(DEEPSEEK_CONFIG['base_url'], headers=headers, json=data)
            
            print(f"[DeepSeek调试] 响应状态码: {response.status_code}")
            print(f"[DeepSeek调试] 响应内容: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
                
                print(f"[DeepSeek调试] AI回复: {ai_response}")
                
                try:
                    # 解析AI返回的JSON，先清理Markdown格式
                    # 移除Markdown代码块标记
                    cleaned_response = ai_response
                    if '```json' in ai_response:
                        # 提取```json和```之间的内容
                        json_match = re.search(r'```json\s*(.*?)\s*```', ai_response, re.DOTALL)
                        if json_match:
                            cleaned_response = json_match.group(1).strip()
                    elif '```' in ai_response:
                        # 提取```和```之间的内容
                        json_match = re.search(r'```\s*(.*?)\s*```', ai_response, re.DOTALL)
                        if json_match:
                            cleaned_response = json_match.group(1).strip()
                    
                    print(f"[DeepSeek调试] 清理后的JSON: {cleaned_response}")
                    
                    intent_data = json.loads(cleaned_response)
                    print(f"[DeepSeek调试] 解析成功: {intent_data}")
                    return {
                        'success': True,
                        'intent': intent_data
                    }
                except json.JSONDecodeError as je:
                    print(f"[DeepSeek调试] JSON解析失败: {je}")
                    return {
                        'success': False,
                        'error': 'AI回复格式解析失败',
                        'raw_response': ai_response
                    }
            else:
                return {
                    'success': False,
                    'error': f'DeepSeek API调用失败: {response.status_code}',
                    'details': response.text
                }
                
        except Exception as e:
            print(f"[DeepSeek调试] 异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f'AI意图理解异常: {str(e)}'
            }

