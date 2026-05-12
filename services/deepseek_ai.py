"""
DeepSeek AI助手类，用于理解用户自然语言并调用MCP功能
"""
import requests
import json
from config import DEEPSEEK_CONFIG
from utils.json_extractor import extract_json_from_llm_response


class DeepSeekAI:
    """DeepSeek AI助手类，用于理解用户自然语言并调用MCP功能"""
    
    def __init__(self, api_key, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or DEEPSEEK_CONFIG['base_url']
        self.model = model or DEEPSEEK_CONFIG['model']
        self.session = requests.Session()
        self.system_prompt = """你是地图服务Agent，采用ReAct模式迭代调用工具。

重要背景：你的用户是视障人士（盲人或低视力），出行方式只有步行，你的回答将通过语音播报。

⚠️ 回答长度要求：
- 最终answer的content字段控制在2~5句话，不超过100字
- 路线规划：说总距离、大致时间、最关键的转弯（最多3~4步），不逐步列举
- 附近搜索：推荐最近的2~3个，每个说名称和大致距离
- 禁止排比句、长列举、铺垫

⚠️ 视障用户专属规则（极其重要，必须严格遵守）：
- 本系统只支持步行导航，绝对不要建议用户"坐公交"、"坐地铁"、"打车"、"开车"或任何非步行出行方式
- 不要说"我帮您查找公交站/地铁站"之类的话
- 如果步行距离超过5公里（约1小时以上），用温和的方式告知距离较远、步行需要较长时间，需要明确指出并说明强烈不推荐步行，同时可以建议：
  · 请家属或朋友协助前往
  · 询问用户是否仍希望获取步行路线
- 不管距离多远，只要用户确认要走，就正常提供步行路线信息
- 回复要体现关怀，但不要居高临下或否定用户的出行能力

语言规则：
- 禁止"向北/南/东/西"等绝对方位，只用左转、右转、向前走
- 禁止"看到/看一下"等视觉表述，用"经过/到达/路过"代替
- 语气温暖自然，每次回复的措辞要有变化，不要总是相同句式
- 称呼用户时使用对话上下文中提供的用户称呼

工具列表：
1. geocoding: 地址→坐标(BD-09)
   参数: {"address": "地址", "city": "城市"}
   ⚠️ 从地址中提取城市名传入city参数！

2. reverse_geocoding: 坐标→地址
   参数: {"lat": 纬度, "lng": 经度}

3. search_places: 搜索附近地点
   参数: {"query": "关键词", "lat": 纬度, "lng": 经度, "radius": 半径}

4. route_planning: 路线规划（仅支持步行）
   参数: {"origin_lat": 起点纬, "origin_lng": 起点经, "dest_lat": 终点纬, "dest_lng": 终点经}

返回格式（纯JSON，无markdown）：
调用工具：{"type":"tool_call","action":"工具名","params":{参数},"reasoning":"原因"}
给出答案：{"type":"answer","content":"简短回答","reasoning":"原因"}

规则：
- 路线规划前必须先用geocoding获取坐标
- 调用geocoding时必须提取并传入city参数
- 一次一个工具，观察结果再决定下一步
- 避免重复调用

⚠️ 输出格式硬性要求（必须严格遵守，否则系统无法解析）：
- 你的回复必须是一个完整的JSON对象，第一个字符必须是 `{`，最后一个字符必须是 `}`
- 不要在JSON前后添加任何说明文字、铺垫、前缀、后缀
- 不要使用markdown代码块包裹
- 即使是给出最终answer，也必须用 {"type":"answer","content":"...","reasoning":"..."} 的JSON格式包裹自然语言回复
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
                'model': self.model,
                'messages': messages,
                'temperature': 0.1,
                'max_tokens': 500
            }
            
            print(f"[DeepSeek调试] 请求URL: {self.base_url}")
            print(f"[DeepSeek调试] 请求数据: {data}")
            
            response = self.session.post(self.base_url, headers=headers, json=data)
            
            print(f"[DeepSeek调试] 响应状态码: {response.status_code}")
            print(f"[DeepSeek调试] 响应内容: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
                
                print(f"[DeepSeek调试] AI回复: {ai_response}")
                
                try:
                    # 容忍 markdown 代码块、前置铺垫文字等情况，提取首个完整 JSON
                    cleaned_response = extract_json_from_llm_response(ai_response)

                    print(f"[DeepSeek调试] 清理后的JSON: {cleaned_response}")

                    intent_data = json.loads(cleaned_response)
                    print(f"[DeepSeek调试] 解析成功: {intent_data}")
                    return {
                        'success': True,
                        'intent': intent_data
                    }
                except json.JSONDecodeError as je:
                    print(f"[DeepSeek调试] JSON解析失败: {je}")

                    # 兜底：deepseek-v4-flash 等轻量模型在工具链末尾经常无视 JSON 约束、
                    # 直接吐出最终口播内容。如果响应里完全没有 '{'，几乎可以确定它不是想
                    # 继续调用工具，而是在用自然语言总结。直接当作 answer 播报，避免把已
                    # 经成功的一串工具调用浪费掉。
                    if '{' not in ai_response:
                        fallback_content = ai_response.strip()
                        if fallback_content:
                            print(f"[DeepSeek调试] 兜底为最终answer: {fallback_content}")
                            return {
                                'success': True,
                                'intent': {
                                    'type': 'answer',
                                    'content': fallback_content,
                                    'reasoning': '模型未返回JSON，已将自然语言回复兜底为最终answer'
                                }
                            }

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

