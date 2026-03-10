"""
意图路由器 - 对用户消息进行意图分类，分发到对应的Agent
"""
import requests
import json
import re
from config import DEEPSEEK_CONFIG


class RouterAgent:
    """意图路由器，负责将用户消息分类到对应的处理Agent"""

    ROUTER_PROMPT = """你是一个意图分类器。根据用户的输入，判断属于以下哪个类别：

1. "settings" - 用户想查询或修改系统设置，包括：语音速度（慢/中等/快）、语音音量（低/中等/高）、鼓励功能（开/关）、用户模式（盲人端/家属端）、个人信息（姓名、性别、年龄）
   修改例如："帮我把语音速度调成慢"、"关闭鼓励功能"、"把音量调大"、"切换到家属端"
   查询例如："现在语音速度怎么样"、"鼓励功能是开的还是关的"、"怎么称呼我"、"我的设置是什么"

2. "map" - 用户想查询地图信息，包括：地点搜索、路线规划、坐标查询、附近搜索
   例如："从天安门到北京大学怎么走"、"附近有什么便利店"、"天安门的坐标是多少"

3. "message" - 用户想给家属发送消息
   例如："帮我发给家属消息：我到了"、"给家属说一声我在路上"、"发消息告诉家属我快到了"

4. "chat" - 普通闲聊或其他不属于上述类别的内容
   例如："你好"、"今天天气怎么样"、"谢谢你"

请严格返回如下JSON格式（无markdown标记）：
{"intent": "分类名称", "confidence": 0.0到1.0的数值, "extracted_info": {提取的关键信息}}

extracted_info说明：
- settings类型：{"field": "要修改的字段", "value": "目标值"}
- map类型：{"query": "地图相关的查询内容"}
- message类型：{"message_content": "要发送的消息内容"}
- chat类型：{"topic": "话题简述"}"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()

    def classify_intent(self, user_message, chat_history=None):
        """分类用户意图，支持对话上下文"""
        try:
            print(f"[Router] 开始分类: {user_message}")

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            messages = [{'role': 'system', 'content': self.ROUTER_PROMPT}]

            if chat_history:
                recent = chat_history[-10:]
                for item in recent:
                    role = item.get('role', 'user')
                    content = item.get('content', '')
                    if role in ('user', 'assistant') and content:
                        messages.append({'role': role, 'content': content})

            messages.append({'role': 'user', 'content': user_message})

            data = {
                'model': DEEPSEEK_CONFIG['model'],
                'messages': messages,
                'temperature': 0.1,
                'max_tokens': 300
            }

            response = self.session.post(
                DEEPSEEK_CONFIG['base_url'],
                headers=headers,
                json=data
            )

            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()

                cleaned = self._clean_json(ai_response)
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

        except json.JSONDecodeError:
            return {'success': False, 'error': '意图解析失败'}
        except Exception as e:
            print(f"[Router] 异常: {e}")
            return {'success': False, 'error': f'路由器异常: {str(e)}'}

    @staticmethod
    def _clean_json(text):
        """清理AI返回中可能包含的Markdown格式"""
        if '```json' in text:
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return match.group(1).strip()
        elif '```' in text:
            match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return text.strip()
