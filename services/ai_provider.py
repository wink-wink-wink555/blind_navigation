"""
AI Provider - 统一的 AI 模型调用入口
根据用户的 AI 设置（云端/本地）自动路由到 DeepSeek / OpenAI 兼容 / Ollama
后端业务代码只需要调用 chat_completion(...) 与 transcribe(...) 即可。
"""
import os
import requests
from typing import Optional, Dict, List

from config import DEEPSEEK_CONFIG, DASHSCOPE_CONFIG
from models.database import get_user_ai_settings
from services.ollama_client import OllamaClient, DEFAULT_OLLAMA_BASE_URL


# ---- 云端可选模型预设（前端下拉用） ----
CLOUD_TEXT_PRESETS = [
    {
        'provider': 'deepseek',
        'label': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/chat/completions',
        'models': ['deepseek-chat', 'deepseek-reasoner'],
        'api_key_url': 'https://platform.deepseek.com/api_keys'
    },
    {
        'provider': 'openai',
        'label': 'OpenAI',
        'base_url': 'https://api.openai.com/v1/chat/completions',
        'models': ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'],
        'api_key_url': 'https://platform.openai.com/api-keys'
    },
    {
        'provider': 'dashscope',
        'label': '阿里云百炼（兼容OpenAI）',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'models': ['qwen-turbo', 'qwen-plus', 'qwen-max'],
        'api_key_url': 'https://bailian.console.aliyun.com/'
    },
    {
        'provider': 'custom',
        'label': '自定义（OpenAI 兼容）',
        'base_url': '',
        'models': [],
        'api_key_url': ''
    },
]

CLOUD_STT_PRESETS = [
    {
        'provider': 'dashscope',
        'label': '阿里云百炼 Paraformer',
        'models': ['paraformer-realtime-v2', 'paraformer-realtime-8k-v2', 'paraformer-v2'],
        'api_key_url': 'https://bailian.console.aliyun.com/'
    },
]


def _default_ai_config() -> Dict:
    """构造一份默认 AI 配置（首次调用、用户未设置时用）。"""
    return {
        'text': {
            'deployment': 'cloud',
            'cloud': {
                'provider': 'deepseek',
                'base_url': DEEPSEEK_CONFIG.get('base_url', 'https://api.deepseek.com/chat/completions'),
                'api_key': DEEPSEEK_CONFIG.get('api_key', ''),
                'model': DEEPSEEK_CONFIG.get('model', 'deepseek-chat')
            },
            'local': {
                'base_url': DEFAULT_OLLAMA_BASE_URL,
                'model': ''
            }
        },
        'stt': {
            'deployment': 'cloud',
            'cloud': {
                'provider': 'dashscope',
                'api_key': DASHSCOPE_CONFIG.get('api_key', ''),
                'model': DASHSCOPE_CONFIG.get('stt_model', 'paraformer-realtime-v2')
            },
            'local': {
                'base_url': DEFAULT_OLLAMA_BASE_URL,
                'model': ''
            }
        }
    }


def _merge_with_default(user_cfg: Optional[Dict]) -> Dict:
    """
    把用户配置与默认配置深度合并，保证字段齐全。
    安全策略：cloud 字段始终以 config.py 为唯一真源，
    数据库中即使残留了 cloud 字段也会被忽略，避免敏感信息被前端写入。
    """
    base = _default_ai_config()
    if not user_cfg or not isinstance(user_cfg, dict):
        return base
    for top_key in ('text', 'stt'):
        sec = user_cfg.get(top_key)
        if not isinstance(sec, dict):
            continue
        # 只接受 deployment + local，cloud 永远走 config.py
        if sec.get('deployment') in ('cloud', 'local'):
            base[top_key]['deployment'] = sec['deployment']
        local = sec.get('local')
        if isinstance(local, dict):
            base[top_key]['local'].update(local)
    return base


def get_ai_config(user_id: Optional[int]) -> Dict:
    """获取某个用户当前激活的 AI 配置（已与默认合并）。"""
    if not user_id:
        return _default_ai_config()
    cfg, _ = get_user_ai_settings(user_id)
    return _merge_with_default(cfg)


def get_default_ai_config() -> Dict:
    """对外暴露默认配置（前端首次进入用）"""
    return _default_ai_config()


# =============== 文本模型统一入口 ===============

def chat_completion(user_id: Optional[int],
                    messages: List[Dict],
                    temperature: float = 0.7,
                    max_tokens: int = 500,
                    timeout: float = 60.0) -> Dict:
    """
    统一文本生成入口。
    返回 {'success': bool, 'content': str, 'error': str|None,
          'provider': str, 'model': str, 'deployment': 'cloud'|'local'}
    """
    cfg = get_ai_config(user_id)
    text_cfg = cfg['text']
    deployment = text_cfg.get('deployment', 'cloud')

    if deployment == 'local':
        local = text_cfg.get('local', {})
        base_url = local.get('base_url') or DEFAULT_OLLAMA_BASE_URL
        model = (local.get('model') or '').strip()
        if not model:
            return {
                'success': False, 'content': '',
                'error': '尚未选择本地文本模型，请先到 AI 设置选择 Ollama 模型',
                'provider': 'ollama', 'model': '', 'deployment': 'local'
            }
        client = OllamaClient(base_url=base_url)
        result = client.chat_completion(model, messages,
                                        temperature=temperature,
                                        max_tokens=max_tokens,
                                        timeout=timeout)
        return {
            **result,
            'provider': 'ollama',
            'model': model,
            'deployment': 'local'
        }

    # ----- 云端 -----
    cloud = text_cfg.get('cloud', {})
    provider = cloud.get('provider', 'deepseek')
    base_url = cloud.get('base_url') or DEEPSEEK_CONFIG['base_url']
    api_key = cloud.get('api_key') or DEEPSEEK_CONFIG['api_key']
    model = cloud.get('model') or DEEPSEEK_CONFIG['model']

    if not api_key:
        return {
            'success': False, 'content': '',
            'error': f'未配置 {provider} 的 API Key，请到 AI 设置中填写',
            'provider': provider, 'model': model, 'deployment': 'cloud'
        }

    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {
                'success': False, 'content': '',
                'error': f'{provider} 调用失败: HTTP {resp.status_code} - {resp.text[:200]}',
                'provider': provider, 'model': model, 'deployment': 'cloud'
            }
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()
        return {
            'success': True, 'content': content, 'error': None,
            'provider': provider, 'model': model, 'deployment': 'cloud'
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'content': '', 'error': f'{provider} 调用超时',
                'provider': provider, 'model': model, 'deployment': 'cloud'}
    except Exception as e:
        return {'success': False, 'content': '', 'error': f'{provider} 调用异常: {e}',
                'provider': provider, 'model': model, 'deployment': 'cloud'}


# =============== 文本模型 -- 兼容旧 Agent 的"配置字典"入口 ===============

def get_text_llm_config(user_id: Optional[int]) -> Dict:
    """
    返回一份对老 Agent 友好的字典（即使本地部署也封成同样字段）：
        {'deployment': 'cloud'|'local',
         'provider': str, 'base_url': str, 'api_key': str, 'model': str}
    本地部署时 base_url 指 Ollama 的 OpenAI 兼容 endpoint，api_key 填占位 'ollama'。
    """
    cfg = get_ai_config(user_id)
    text_cfg = cfg['text']
    deployment = text_cfg.get('deployment', 'cloud')

    if deployment == 'local':
        local = text_cfg.get('local', {})
        base = (local.get('base_url') or DEFAULT_OLLAMA_BASE_URL).rstrip('/')
        return {
            'deployment': 'local',
            'provider': 'ollama',
            'base_url': f"{base}/v1/chat/completions",
            'api_key': 'ollama',
            'model': local.get('model', '') or ''
        }

    cloud = text_cfg.get('cloud', {})
    return {
        'deployment': 'cloud',
        'provider': cloud.get('provider', 'deepseek'),
        'base_url': cloud.get('base_url') or DEEPSEEK_CONFIG['base_url'],
        'api_key': cloud.get('api_key') or DEEPSEEK_CONFIG['api_key'],
        'model': cloud.get('model') or DEEPSEEK_CONFIG['model']
    }


# =============== 语音模型统一配置 ===============

def get_stt_config(user_id: Optional[int]) -> Dict:
    """
    返回 STT 配置：
        {'deployment': 'cloud'|'local',
         'provider': str, 'api_key': str, 'model': str, 'base_url': str}
    """
    cfg = get_ai_config(user_id)
    stt_cfg = cfg['stt']
    deployment = stt_cfg.get('deployment', 'cloud')

    if deployment == 'local':
        local = stt_cfg.get('local', {})
        return {
            'deployment': 'local',
            'provider': 'ollama',
            'base_url': (local.get('base_url') or DEFAULT_OLLAMA_BASE_URL).rstrip('/'),
            'api_key': '',
            'model': local.get('model', '') or ''
        }

    cloud = stt_cfg.get('cloud', {})
    return {
        'deployment': 'cloud',
        'provider': cloud.get('provider', 'dashscope'),
        'base_url': '',
        'api_key': cloud.get('api_key') or DASHSCOPE_CONFIG['api_key'],
        'model': cloud.get('model') or DASHSCOPE_CONFIG['stt_model']
    }
