"""
本地 Ollama 客户端 - 探测本地 Ollama 服务、列出已安装模型、调用本地模型推理
仅依赖标准 requests，避免引入额外依赖。
"""
import requests
from typing import List, Dict, Optional


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

# Ollama 内常见的语音/多模态模型关键字（仅用于在前端做"是否STT能力"分类提示）
_STT_KEYWORDS = ('whisper', 'voice', 'asr', 'speech', 'audio', 'paraformer')


class OllamaClient:
    """本地 Ollama 服务客户端"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = (base_url or DEFAULT_OLLAMA_BASE_URL).rstrip('/')
        self.timeout = timeout

    # ---------- 探测 ----------
    def ping(self) -> Dict:
        """探测 Ollama 是否在线。返回 {'online': bool, 'version': str|None, 'error': str|None}"""
        try:
            resp = requests.get(f"{self.base_url}/api/version", timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json() if resp.text else {}
                return {
                    'online': True,
                    'version': data.get('version', 'unknown'),
                    'error': None
                }
            return {'online': False, 'version': None, 'error': f"HTTP {resp.status_code}"}
        except requests.exceptions.ConnectionError:
            return {'online': False, 'version': None,
                    'error': '无法连接到本地 Ollama 服务，请确认已启动 (ollama serve)'}
        except requests.exceptions.Timeout:
            return {'online': False, 'version': None, 'error': 'Ollama 服务响应超时'}
        except Exception as e:
            return {'online': False, 'version': None, 'error': f'探测异常: {e}'}

    # ---------- 模型列表 ----------
    def list_models(self) -> Dict:
        """
        获取 Ollama 已安装模型。
        返回 {'success': bool, 'models': [{'name','size','modified_at','is_stt'}], 'error': str|None}
        """
        ping_result = self.ping()
        if not ping_result['online']:
            return {'success': False, 'models': [], 'error': ping_result['error']}

        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            if resp.status_code != 200:
                return {'success': False, 'models': [],
                        'error': f"获取模型列表失败: HTTP {resp.status_code}"}
            data = resp.json()
            raw_models = data.get('models', []) or []

            models = []
            for m in raw_models:
                name = m.get('name') or m.get('model') or ''
                if not name:
                    continue
                lower = name.lower()
                models.append({
                    'name': name,
                    'size': m.get('size', 0),
                    'modified_at': m.get('modified_at', ''),
                    'is_stt': any(kw in lower for kw in _STT_KEYWORDS)
                })

            return {'success': True, 'models': models, 'error': None}
        except Exception as e:
            return {'success': False, 'models': [], 'error': f'获取模型列表异常: {e}'}

    # ---------- 文本推理（OpenAI 兼容接口） ----------
    def chat_completion(self, model: str, messages: list,
                        temperature: float = 0.7, max_tokens: int = 500,
                        timeout: float = 120.0) -> Dict:
        """
        通过 Ollama 的 OpenAI 兼容接口调用文本生成。
        返回 {'success', 'content', 'error'}
        """
        try:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'stream': False
            }
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code != 200:
                return {
                    'success': False,
                    'content': '',
                    'error': f"Ollama 调用失败: HTTP {resp.status_code} - {resp.text[:200]}"
                }
            data = resp.json()
            choices = data.get('choices', [])
            if not choices:
                return {'success': False, 'content': '', 'error': 'Ollama 未返回任何内容'}
            content = choices[0].get('message', {}).get('content', '').strip()
            return {'success': True, 'content': content, 'error': None}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'content': '',
                    'error': '无法连接本地 Ollama 服务，请确认已启动 (ollama serve)'}
        except requests.exceptions.Timeout:
            return {'success': False, 'content': '', 'error': 'Ollama 推理超时'}
        except Exception as e:
            return {'success': False, 'content': '', 'error': f'Ollama 推理异常: {e}'}
