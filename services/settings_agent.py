"""
设置修改Agent - 解析用户自然语言请求并修改系统设置
使用结构化提取 + 参数化SQL，避免直接txt2sql的注入风险
"""
import requests
import json
from config import DEEPSEEK_CONFIG
from models.database import get_user_settings, update_user_settings_in_db
from utils.json_extractor import extract_json_from_llm_response


FIELD_MAP = {
    'voice_speed': {'name': '语音速度', 'values': ['慢', '中等', '快']},
    'voice_volume': {'name': '语音音量', 'values': ['低', '中等', '高']},
    'encourage': {'name': '鼓励功能', 'values': ['开', '关']},
    'user_mode': {'name': '用户模式', 'values': ['盲人端', '家属端']},
    'gender': {'name': '性别', 'values': ['男', '女', '未指定']},
    'name': {'name': '姓名', 'values': None},
    'age': {'name': '年龄段', 'values': ['青年', '中年', '老年', '未指定']},
}

VALUE_NORMALIZE_MAP = {
    'voice_speed': {
        '慢速': '慢', '很慢': '慢', '缓慢': '慢', '低速': '慢', '最慢': '慢',
        '中速': '中等', '正常': '中等', '默认': '中等', '适中': '中等',
        '快速': '快', '很快': '快', '高速': '快', '最快': '快', '加速': '快',
    },
    'voice_volume': {
        '小': '低', '小声': '低', '很低': '低', '最低': '低', '低音': '低', '轻声': '低', '安静': '低',
        '正常': '中等', '默认': '中等', '适中': '中等', '中间': '中等',
        '大': '高', '大声': '高', '很高': '高', '最高': '高', '高音': '高', '响': '高', '最大': '高',
    },
    'encourage': {
        '开启': '开', '打开': '开', '启用': '开', '是': '开', '要': '开',
        '关闭': '关', '关掉': '关', '禁用': '关', '否': '关', '不要': '关',
    },
}


class SettingsAgent:
    """设置修改Agent，从用户自然语言中提取设置修改意图并执行"""

    SETTINGS_PROMPT = """你是视障导航系统的设置助手，回复会被语音播报。

⚠️ 最重要的规则：
1. response字段必须在1~2句话以内，不超过30个字
2. value字段必须严格使用下方列出的精确值，不能用任何近义词或变体

设置项及【唯一允许的值】：
- voice_speed（语音速度）: 只能是 "慢" 或 "中等" 或 "快"
- voice_volume（语音音量）: 只能是 "低" 或 "中等" 或 "高"
- encourage（鼓励功能）: 只能是 "开" 或 "关"
- user_mode（用户模式）: 只能是 "盲人端" 或 "家属端"
- gender（性别）: 只能是 "男" 或 "女" 或 "未指定"
- name（姓名）: 任意文本
- age（年龄段）: 只能是 "青年" 或 "中年" 或 "老年" 或 "未指定"

映射规则（用户口语 → 精确值）：
- "调大/调高音量" → voice_volume: "高"
- "调小/调低音量" → voice_volume: "低"
- "调快速度" → voice_speed: "快"
- "调慢速度" → voice_speed: "慢"
- "打开/开启鼓励" → encourage: "开"
- "关闭/关掉鼓励" → encourage: "关"

判断逻辑：
1. 查询设置 → changes为空数组，response简短告知当前值
2. 修改设置 → changes填入字段和精确值

返回JSON（无markdown）：
{"changes": [{"field": "字段名", "value": "精确值"}], "response": "简短回复"}

示例：
- 查询速度 → {"changes": [], "response": "当前语音速度是「中等」。"}
- 调慢速度 → {"changes": [{"field": "voice_speed", "value": "慢"}], "response": "已帮您调成慢速了。"}
- 关鼓励 → {"changes": [{"field": "encourage", "value": "关"}], "response": "鼓励功能已关闭。"}"""

    def __init__(self, api_key, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or DEEPSEEK_CONFIG['base_url']
        self.model = model or DEEPSEEK_CONFIG['model']
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
                'model': self.model,
                'messages': messages,
                'temperature': 0.1,
                'max_tokens': 250
            }

            response = self.session.post(
                self.base_url,
                headers=headers,
                json=data
            )

            if response.status_code != 200:
                return {'success': False, 'response': 'AI服务暂时不可用，请稍后再试'}

            result = response.json()
            ai_response = result['choices'][0]['message']['content'].strip()

            cleaned = extract_json_from_llm_response(ai_response)
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

                if not field or not isinstance(field, str) or field not in FIELD_MAP:
                    continue

                if value is None:
                    continue

                value = str(value).strip()

                allowed = FIELD_MAP[field]['values']
                if allowed is not None and value not in allowed:
                    value = self._normalize_value(field, value)
                    if value is None:
                        print(f"[SettingsAgent] 拒绝非法值: {field}={change.get('value')}")
                        continue

                if field == 'name':
                    if len(value) > 20 or not value:
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

        except json.JSONDecodeError as je:
            print(f"[SettingsAgent] JSON解析失败: {je}")
            return {'success': False, 'response': '抱歉，设置解析失败，请再试一次'}
        except Exception as e:
            print(f"[SettingsAgent] 异常: {e}")
            return {'success': False, 'response': f'设置修改异常：{str(e)}'}

    @staticmethod
    def _normalize_value(field, value):
        """尝试将AI返回的非标准值归一化为合法值，失败返回None"""
        normalize_map = VALUE_NORMALIZE_MAP.get(field)
        if normalize_map and value in normalize_map:
            normalized = normalize_map[value]
            print(f"[SettingsAgent] 值归一化: {field} '{value}' → '{normalized}'")
            return normalized

        allowed = FIELD_MAP[field]['values']
        if allowed:
            for valid_val in allowed:
                if valid_val in value or value in valid_val:
                    print(f"[SettingsAgent] 模糊匹配: {field} '{value}' → '{valid_val}'")
                    return valid_val

        return None
