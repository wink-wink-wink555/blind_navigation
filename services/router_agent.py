"""
意图路由器 - 对用户消息进行意图分类，分发到对应的Agent
"""
import requests
import json
from config import DEEPSEEK_CONFIG
from utils.json_extractor import extract_json_from_llm_response


class RouterAgent:
    """意图路由器，负责将用户消息分类到对应的处理Agent"""

    ROUTER_PROMPT = """你是一个意图分类器，服务于视障导航系统。

⚠️ 核心原则：你只需要对【最新一条用户消息】进行分类。对话历史仅用于辅助理解指代和上下文（如"那里"指哪里、"也帮我查查"接续什么话题），绝不能因为之前聊了闲天就把当前消息也归为闲聊。

意图类别：

1. "settings" - 查询或修改系统设置
   涵盖：语音速度、语音音量、鼓励功能、用户模式、姓名、性别、年龄
   例："帮我把语音调快"、"关闭鼓励"、"音量调大"、"切换家属端"、"现在什么设置"、"怎么称呼我"

2. "map" - 地图/导航/地点/路线相关
   涵盖：问路、找地点、附近搜索、距离查询、怎么走、去哪里
   例："从这里到学校怎么走"、"附近有便利店吗"、"离地铁站多远"、"帮我导航到医院"、"我想去公园"

3. "message" - 给家属发消息
   例："帮我给家属发消息说我到了"、"告诉家人我在路上"

4. "chat" - 纯粹的闲聊、情感交流、与上述三类无关的话题
   例："你好"、"谢谢你"、"我心情不好"、"给我讲个笑话"

分类优先级：settings > map > message > chat
当消息同时可能属于多个类别时，优先选择功能性更强的类别。只有确实与前三类完全无关时才归为chat。

返回纯JSON（无markdown标记）：
{"intent": "分类名称", "confidence": 0.0到1.0, "extracted_info": {关键信息}}

extracted_info：
- settings: {"field": "字段", "value": "目标值"}
- map: {"query": "地图查询内容"}
- message: {"recipient": "收件人称呼（如妈妈、爸爸，没指定则为空字符串）", "message_content": "消息内容"}
- chat: {"topic": "话题"}"""

    def __init__(self, api_key, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or DEEPSEEK_CONFIG['base_url']
        self.model = model or DEEPSEEK_CONFIG['model']
        self.session = requests.Session()

    def classify_intent(self, user_message, chat_history=None):
        """分类用户意图，支持对话上下文"""
        try:
            print(f"[Router] 开始分类: {user_message} (provider={self.base_url}, model={self.model})")

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            messages = [{'role': 'system', 'content': self.ROUTER_PROMPT}]

            if chat_history:
                context_lines = []
                recent = chat_history[-8:]
                for item in recent:
                    role = item.get('role', 'user')
                    content = item.get('content', '')
                    if content:
                        label = "用户" if role == 'user' else "助手"
                        context_lines.append(f"{label}: {content[:80]}")
                if context_lines:
                    context_block = "\n".join(context_lines)
                    messages.append({
                        'role': 'user',
                        'content': f"[以下是近期对话摘要，仅供理解上下文指代，不影响分类]\n{context_block}"
                    })
                    messages.append({
                        'role': 'assistant',
                        'content': '好的，我会根据最新一条用户消息独立判断意图。'
                    })

            messages.append({'role': 'user', 'content': f"请对以下【最新消息】进行意图分类：\n{user_message}"})

            data = {
                'model': self.model,
                'messages': messages,
                'temperature': 0.1,
                'max_tokens': 300
            }

            response = self.session.post(
                self.base_url,
                headers=headers,
                json=data
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()

                cleaned = extract_json_from_llm_response(ai_response)
                intent_data = json.loads(cleaned)

                intent = intent_data.get('intent', 'chat')
                confidence = intent_data.get('confidence', 0.5)
                extracted_info = intent_data.get('extracted_info', {})

                print(f"[Router] 分类结果: intent={intent}, confidence={confidence}")

                return {
                    'success': True,
                    'intent': intent,
                    'confidence': confidence,
                    'extracted_info': extracted_info
                }
            else:
                return {
                    'success': False,
                    'error': f'API调用失败: {response.status_code}'
                }

        except json.JSONDecodeError as je:
            print(f"[Router] JSON解析失败: {je}")
            return {'success': False, 'error': '意图解析失败'}
        except Exception as e:
            print(f"[Router] 异常: {e}")
            return {'success': False, 'error': f'路由器异常: {str(e)}'}
