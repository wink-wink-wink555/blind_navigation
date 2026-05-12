"""
语音识别Agent
- 云端：阿里云百炼平台（DashScope）Paraformer 模型
- 本地：OpenAI 兼容的 /v1/audio/transcriptions 接口
        （如 faster-whisper-server / openai-whisper-asr-webservice 等）
口吃纠正Agent通过统一的 ai_provider 调用当前激活的文本模型。
"""
import os
import requests
import dashscope
from http import HTTPStatus
from dashscope.audio.asr import Recognition
from config import DEEPSEEK_CONFIG


class SpeechToTextAgent:
    """
    语音转文字Agent，支持云端 DashScope 与本地 OpenAI 兼容接口。
    deployment='cloud' 时走 DashScope；'local' 时走 base_url + /v1/audio/transcriptions。
    """

    def __init__(self, api_key, model='paraformer-realtime-v2',
                 deployment='cloud', base_url=None):
        self.api_key = api_key
        self.model = model
        self.deployment = deployment or 'cloud'
        self.base_url = (base_url or '').rstrip('/')

    def transcribe(self, audio_file_path):
        """
        将音频文件转换为文字
        :param audio_file_path: 音频文件路径（支持 wav、pcm、opus、aac、amr 等格式）
        :return: dict {'success': bool, 'text': str, 'error': str}
        """
        if not os.path.exists(audio_file_path):
            return {'success': False, 'text': '', 'error': '音频文件不存在'}

        if self.deployment == 'local':
            return self._transcribe_local(audio_file_path)
        return self._transcribe_dashscope(audio_file_path)

    # -------- 云端：DashScope Paraformer --------
    def _transcribe_dashscope(self, audio_file_path):
        try:
            if not self.api_key:
                return {'success': False, 'text': '',
                        'error': '未配置 DashScope API Key，请到 AI 设置中填写'}

            dashscope.api_key = self.api_key

            recognition = Recognition(
                model=self.model,
                format='wav',
                sample_rate=16000,
                language_hints=['zh', 'en'],
                callback=None
            )

            result = recognition.call(audio_file_path)

            if result.status_code == HTTPStatus.OK:
                sentences = result.get_sentence()
                text = self._extract_text(sentences)
                print(f"[STT/cloud] 识别成功: {text}")
                return {'success': True, 'text': text, 'error': ''}
            else:
                error_msg = getattr(result, 'message', '未知错误')
                print(f"[STT/cloud] 识别失败: {error_msg}")
                return {'success': False, 'text': '', 'error': f'语音识别失败: {error_msg}'}

        except Exception as e:
            print(f"[STT/cloud] 异常: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'text': '', 'error': f'语音识别异常: {str(e)}'}

    # -------- 本地：OpenAI 兼容音频接口 --------
    def _transcribe_local(self, audio_file_path):
        if not self.base_url:
            return {'success': False, 'text': '',
                    'error': '未配置本地语音识别服务地址'}
        if not self.model:
            return {'success': False, 'text': '',
                    'error': '未选择本地语音识别模型'}

        endpoint = f"{self.base_url}/v1/audio/transcriptions"
        try:
            with open(audio_file_path, 'rb') as f:
                files = {'file': (os.path.basename(audio_file_path), f, 'audio/wav')}
                data = {'model': self.model, 'language': 'zh'}
                resp = requests.post(endpoint, files=files, data=data, timeout=120)

            if resp.status_code != 200:
                return {'success': False, 'text': '',
                        'error': f'本地语音识别失败: HTTP {resp.status_code} - {resp.text[:200]}'}

            try:
                payload = resp.json()
                text = (payload.get('text') or '').strip()
            except ValueError:
                text = resp.text.strip()

            print(f"[STT/local] 识别成功: {text}")
            return {'success': True, 'text': text, 'error': ''}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'text': '',
                    'error': '无法连接本地语音识别服务，请确认服务已启动'}
        except requests.exceptions.Timeout:
            return {'success': False, 'text': '', 'error': '本地语音识别超时'}
        except Exception as e:
            print(f"[STT/local] 异常: {e}")
            return {'success': False, 'text': '', 'error': f'本地语音识别异常: {e}'}

    @staticmethod
    def _extract_text(sentences):
        """从识别结果中提取纯文本"""
        if not sentences:
            return ''
        if isinstance(sentences, str):
            return sentences
        if isinstance(sentences, list):
            parts = []
            for s in sentences:
                if isinstance(s, dict):
                    parts.append(s.get('text', ''))
                elif hasattr(s, 'text'):
                    parts.append(s.text)
                else:
                    parts.append(str(s))
            return ''.join(parts)
        return str(sentences)


class StutterCorrectionAgent:
    """
    口吃纠正Agent - 检测并修复语音识别结果中的口吃/重复问题
    核心原则：只修复口吃，信息一点不能变
    """

    CORRECTION_PROMPT = (
        '你是语音识别后处理专家，专门修复口吃和重复。\n\n'
        '严格规则：\n'
        '1. 只修复明显的口吃和重复（如「你、你好」→「你好」，「我我想去」→「我想去」，「那个那个」→「那个」）\n'
        '2. 绝对不能改变原文的任何含义、语气、用词\n'
        '3. 不能添加原文没有的词语\n'
        '4. 不能修改语法或润色句子\n'
        '5. 不能改变标点符号的使用习惯\n'
        '6. 如果没有检测到口吃，原样返回原文\n'
        '7. 只返回修正后的文本，不要任何解释或说明\n\n'
        '口吃模式举例：\n'
        '- 字词重复：「你、你好」 → 「你好」\n'
        '- 连续重复：「我我我想」 → 「我想」\n'
        '- 短语重复：「去去商店」 → 「去商店」\n'
        '- 停顿重复：「嗯...就是...就是那个」 → 「嗯...就是那个」\n'
    )

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key or DEEPSEEK_CONFIG['api_key']
        self.base_url = base_url or DEEPSEEK_CONFIG['base_url']
        self.model = model or DEEPSEEK_CONFIG['model']

    def correct(self, text):
        """
        检测并修复文本中的口吃现象
        :param text: 原始语音识别文本
        :return: dict {'success': bool, 'original': str, 'corrected': str, 'has_stutter': bool}
        """
        if not text or not text.strip():
            return {
                'success': True,
                'original': text,
                'corrected': text,
                'has_stutter': False
            }

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            data = {
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': self.CORRECTION_PROMPT},
                    {'role': 'user', 'content': text}
                ],
                'temperature': 0.1,
                'max_tokens': 500
            }

            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=15
            )

            if response.status_code == 200:
                corrected = response.json()['choices'][0]['message']['content'].strip()
                has_stutter = corrected != text
                if has_stutter:
                    print(f"[StutterFix] 检测到口吃: '{text}' → '{corrected}'")
                else:
                    print(f"[StutterFix] 未检测到口吃，原样保留")
                return {
                    'success': True,
                    'original': text,
                    'corrected': corrected,
                    'has_stutter': has_stutter
                }
            else:
                print(f"[StutterFix] API调用失败: {response.status_code}")
                return {
                    'success': False,
                    'original': text,
                    'corrected': text,
                    'has_stutter': False
                }

        except Exception as e:
            print(f"[StutterFix] 异常: {e}")
            return {
                'success': False,
                'original': text,
                'corrected': text,
                'has_stutter': False
            }
