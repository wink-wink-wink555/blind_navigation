"""
设置修改Agent - 解析用户自然语言请求并修改系统设置
使用结构化提取 + 参数化SQL，避免直接txt2sql的注入风险
"""
import requests
import json
import re
from config import DEEPSEEK_CONFIG
from models.database import get_user_settings, update_user_settings_in_db


FIELD_MAP = {
    'voice_speed': {'name': '语音速度', 'values': ['慢', '中等', '快']},
    'voice_volume': {'name': '语音音量', 'values': ['低', '中等', '高']},
    'encourage': {'name': '鼓励功能', 'values': ['开', '关']},
    'user_mode': {'name': '用户模式', 'values': ['盲人端', '家属端']},
    'gender': {'name': '性别', 'values': ['男', '女', '未指定']},
    'name': {'name': '姓名', 'values': None},
    'age': {'name': '年龄段', 'values': ['青年', '中年', '老年', '未指定']},
}


class SettingsAgent:
    """设置修改Agent，从用户自然语言中提取设置修改意图并执行"""

    SETTINGS_PROMPT = """你是一个温暖、耐心的设置助手，既能帮用户查询当前设置，也能帮用户修改设置。

重要背景：你的用户是视障人士（盲人或低视力），你的回复会通过语音播报给他们。
请遵循以下原则：
- 用温暖亲切的语气回复，让用户感到被关心
- 修改成功后给予肯定和鼓励，如"已经帮您调好了"、"设置好了，希望用起来更舒服"
- 回复要简洁明了，方便语音播报时用户能快速理解
- 不要使用"看一下"等视觉相关表述

可操作的设置项及其允许值：
- voice_speed（语音速度）: 慢、中等、快
- voice_volume（语音音量）: 低、中等、高
- encourage（鼓励功能）: 开、关
- user_mode（用户模式）: 盲人端、家属端
- gender（性别）: 男、女、未指定
- name（姓名）: 任意文本
- age（年龄段）: 青年、中年、老年、未指定

判断逻辑：
1. 如果用户是在**查询**当前设置（如"现在语音速度怎么样"、"鼓励功能是开的还是关的"、"怎么称呼我"、"我的设置是什么"），请根据提供的当前用户设置回答，changes为空数组。
2. 如果用户是在**修改**设置，请提取要修改的字段和值。

修改时的映射规则：
- "把音量调大/调高" → voice_volume: "高"
- "把音量调小/调低" → voice_volume: "低"
- "音量中等/适中" → voice_volume: "中等"
- "把速度调快" → voice_speed: "快"
- "把速度调慢" → voice_speed: "慢"
- "速度中等/适中" → voice_speed: "中等"
- "开启/打开鼓励" → encourage: "开"
- "关闭/关掉鼓励" → encourage: "关"

如果用户一次要修改多个设置，返回数组。

返回JSON格式（无markdown标记）：
{"changes": [{"field": "字段名", "value": "新值"}], "response": "给用户的友好回复"}

示例：
- 用户查询"现在语音速度怎么样"，当前设置voice_speed为"中等" → {"changes": [], "response": "您当前的语音速度是「中等」。如果觉得不合适，随时告诉我帮您调整哦。"}
- 用户查询"鼓励功能开了吗" → {"changes": [], "response": "您的鼓励功能目前是「开」的状态，会在导航时给您加油打气。"}
- 用户查询"怎么称呼我" → {"changes": [], "response": "目前称呼您为「用户」。如果您告诉我您的名字，我就能更亲切地称呼您了。"}
- 用户修改"帮我把语音速度调成慢" → {"changes": [{"field": "voice_speed", "value": "慢"}], "response": "好的，已经帮您把语音速度调成「慢」了，希望听起来更舒服。"}

如果无法识别用户想查询或修改什么，返回：
{"changes": [], "response": "不好意思，我没有完全理解您的意思。您可以问我当前设置是什么，或者说"帮我把语音速度调成慢"、"关闭鼓励功能"这样的话来修改设置，我随时为您服务。"}"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()

    def process(self, user_message, user_id, chat_history=None, user_profile=""):
        """处理设置查询/修改请求，支持对话上下文"""
        try:
            print(f"[SettingsAgent] 处理请求: {user_message}")

            current_settings, _ = get_user_settings(user_id)
            context = ""
            if user_profile:
                context += f"\n\n{user_profile}"
            if current_settings:
                context += f"\n当前用户设置：{json.dumps(current_settings, ensure_ascii=False)}"

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            messages = [{'role': 'system', 'content': self.SETTINGS_PROMPT}]

            if chat_history:
                recent = chat_history[-10:]
                for item in recent:
                    role = item.get('role', 'user')
                    content = item.get('content', '')
                    if role in ('user', 'assistant') and content:
                        messages.append({'role': role, 'content': content})

            messages.append({'role': 'user', 'content': user_message + context})

            data = {
                'model': DEEPSEEK_CONFIG['model'],
                'messages': messages,
                'temperature': 0.1,
                'max_tokens': 400
            }

            response = self.session.post(
                DEEPSEEK_CONFIG['base_url'],
                headers=headers,
                json=data
            )

            if response.status_code != 200:
                return {'success': False, 'response': 'AI服务暂时不可用，请稍后再试'}

            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()

            cleaned = self._clean_json(ai_response)
            parsed = json.loads(cleaned)
            changes = parsed.get('changes', [])
            ai_reply = parsed.get('response', '')

            if not changes:
                return {'success': True, 'response': ai_reply, 'changes': []}

            if not current_settings:
                return {'success': False, 'response': '无法获取当前设置，请稍后再试'}

            applied_changes = []
            for change in changes:
                field = change.get('field')
                value = change.get('value')

                if field not in FIELD_MAP:
                    continue

                allowed = FIELD_MAP[field]['values']
                if allowed is not None and value not in allowed:
                    continue

                current_settings[field] = value
                applied_changes.append({
                    'field': field,
                    'field_name': FIELD_MAP[field]['name'],
                    'value': value
                })

            if applied_changes:
                success, msg = update_user_settings_in_db(user_id, current_settings)
                if not success:
                    return {'success': False, 'response': f'设置保存失败：{msg}'}

            print(f"[SettingsAgent] 已应用 {len(applied_changes)} 项修改")

            return {
                'success': True,
                'response': ai_reply,
                'changes': applied_changes,
                'updated_settings': current_settings
            }

        except json.JSONDecodeError:
            return {'success': False, 'response': '抱歉，设置解析失败，请再试一次'}
        except Exception as e:
            print(f"[SettingsAgent] 异常: {e}")
            return {'success': False, 'response': f'设置修改异常：{str(e)}'}

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
