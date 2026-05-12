"""
AI 设置路由 - 管理用户的文本/语音模型配置（云端 or 本地 Ollama）
"""
from flask import Blueprint, request, session, jsonify
from utils.decorators import login_required
from models.database import get_user_ai_settings, save_user_ai_settings
from services.ai_provider import (
    get_ai_config,
    CLOUD_TEXT_PRESETS,
    CLOUD_STT_PRESETS,
)
from services.ollama_client import OllamaClient, DEFAULT_OLLAMA_BASE_URL

ai_settings_bp = Blueprint('ai_settings', __name__)


# ----------- 预设元信息（前端下拉用） -----------
@ai_settings_bp.route('/ai_settings/presets', methods=['GET'])
@login_required
def get_presets():
    """获取云端模型预设、默认 Ollama endpoint 等元信息"""
    return jsonify({
        'status': 'success',
        'text_presets': CLOUD_TEXT_PRESETS,
        'stt_presets': CLOUD_STT_PRESETS,
        'default_ollama_url': DEFAULT_OLLAMA_BASE_URL
    })


# ----------- 获取当前用户的 AI 配置 -----------
@ai_settings_bp.route('/ai_settings', methods=['GET'])
@login_required
def get_settings():
    """
    获取当前用户的 AI 配置。
    安全策略：云端 cloud 字段中的 api_key 一律脱敏，不暴露完整密钥到前端。
    """
    user_id = session.get('user_id')
    cfg = get_ai_config(user_id)

    saved_cfg, _ = get_user_ai_settings(user_id)
    has_custom = bool(saved_cfg)

    masked = _mask_cloud_keys(cfg)

    return jsonify({
        'status': 'success',
        'config': masked,
        'has_custom': has_custom
    })


# ----------- 保存/更新 AI 配置 -----------
@ai_settings_bp.route('/ai_settings', methods=['POST'])
@login_required
def update_settings():
    """
    更新当前用户的 AI 配置。
    payload 期望与 get_ai_config 返回的 config 同构，但允许部分字段：
        - cloud.api_key 为空字符串视为"保留原值"
    """
    user_id = session.get('user_id')
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': '请求体必须为 JSON 对象'}), 400

    new_cfg = data.get('config')
    if not isinstance(new_cfg, dict):
        return jsonify({'status': 'error', 'message': 'config 字段缺失或格式错误'}), 400

    # 安全策略：前端发来的 cloud 字段一律忽略，云端配置完全由服务器 config.py 控制。
    # 数据库中只存 deployment + local，避免任何敏感凭证被前端写入或回传。
    sanitized = _strip_cloud(new_cfg)

    ok, msg = _validate_local_only(sanitized)
    if not ok:
        return jsonify({'status': 'error', 'message': msg}), 400

    success, save_msg = save_user_ai_settings(user_id, sanitized)
    if not success:
        return jsonify({'status': 'error', 'message': save_msg}), 500

    # 返回脱敏后的最新合并配置
    merged = get_ai_config(user_id)
    return jsonify({
        'status': 'success',
        'message': 'AI 设置已保存',
        'config': _mask_cloud_keys(merged)
    })


# ----------- 探测本地 Ollama，列出可用模型 -----------
@ai_settings_bp.route('/ai_settings/ollama_probe', methods=['POST'])
@login_required
def probe_ollama():
    """
    探测指定 Ollama endpoint，返回是否在线 + 已安装模型列表。
    payload: {"base_url": "http://localhost:11434"}
    """
    data = request.get_json(silent=True) or {}
    base_url = (data.get('base_url') or DEFAULT_OLLAMA_BASE_URL).strip()

    client = OllamaClient(base_url=base_url, timeout=4.0)
    ping = client.ping()

    if not ping['online']:
        return jsonify({
            'status': 'success',
            'online': False,
            'version': None,
            'models': [],
            'text_models': [],
            'stt_models': [],
            'message': ping['error'] or '本地 Ollama 未运行',
            'hint': '请先安装并启动 Ollama (https://ollama.com/)，然后执行 `ollama pull qwen2.5:7b` 等命令拉取模型。'
        })

    listed = client.list_models()
    if not listed['success']:
        return jsonify({
            'status': 'success',
            'online': True,
            'version': ping['version'],
            'models': [],
            'text_models': [],
            'stt_models': [],
            'message': listed['error'] or '已连接到 Ollama，但未能获取模型列表',
            'hint': '请执行 `ollama list` 检查是否已拉取模型，或运行 `ollama pull qwen2.5:7b`。'
        })

    models = listed['models']
    text_models = [m for m in models if not m['is_stt']]
    stt_models = [m for m in models if m['is_stt']]

    if not models:
        message = '已连接到本地 Ollama，但当前未安装任何模型。'
        hint = '请使用 `ollama pull qwen2.5:7b` 拉取一个文本模型；语音识别可拉取 `ollama pull dimavz/whisper-tiny` 等。'
    else:
        message = f"已检测到 {len(models)} 个本地模型"
        hint = ''

    return jsonify({
        'status': 'success',
        'online': True,
        'version': ping['version'],
        'models': models,
        'text_models': text_models,
        'stt_models': stt_models,
        'message': message,
        'hint': hint
    })


# =================== 工具函数 ===================

def _strip_cloud(incoming: dict) -> dict:
    """
    只保留 deployment + local 两个字段；cloud 字段一律不接受前端写入。
    保证敏感信息（api_key、base_url 等）不会出现在数据库的用户级配置中。
    """
    out = {}
    for top in ('text', 'stt'):
        sec = incoming.get(top) or {}
        if not isinstance(sec, dict):
            sec = {}
        deployment = sec.get('deployment')
        if deployment not in ('cloud', 'local'):
            deployment = 'cloud'
        local = sec.get('local') or {}
        if not isinstance(local, dict):
            local = {}
        out[top] = {
            'deployment': deployment,
            'local': {
                'base_url': str(local.get('base_url') or '').strip(),
                'model': str(local.get('model') or '').strip(),
            }
        }
    return out


def _validate_local_only(cfg: dict):
    """只对 local 模式做必填校验。云端模式跳过（云端由 config.py 决定）。"""
    for top in ('text', 'stt'):
        sub = cfg.get(top) or {}
        if sub.get('deployment') != 'local':
            continue
        local = sub.get('local') or {}
        if not local.get('base_url'):
            return False, f'{ "文本" if top == "text" else "语音"}模型本地服务地址不能为空'
        if not local.get('model'):
            return False, f'{ "文本" if top == "text" else "语音"}模型本地模式必须选择一个已安装的模型'
    return True, ''


def _mask_api_key(key: str) -> str:
    """脱敏 API Key：仅保留首尾少量字符。"""
    if not key:
        return ''
    s = str(key)
    if len(s) <= 10:
        return '*' * len(s)
    return f'{s[:4]}{"*" * (len(s) - 8)}{s[-4:]}'


def _mask_cloud_keys(cfg: dict) -> dict:
    """返回一份 cloud.api_key 已脱敏的副本，避免明文传到前端。"""
    import copy
    out = copy.deepcopy(cfg)
    for top in ('text', 'stt'):
        cloud = out.get(top, {}).get('cloud') or {}
        if 'api_key' in cloud:
            cloud['api_key'] = _mask_api_key(cloud.get('api_key', ''))
    return out
