"""
服务模块包
"""
__all__ = ['BaiduMapMCP', 'DeepSeekAI', 'RouterAgent', 'SettingsAgent']


def __getattr__(name):
    """Keep independent navigation components importable without LLM extras."""
    if name not in __all__:
        raise AttributeError(name)
    from importlib import import_module
    module = {
        'BaiduMapMCP': 'baidu_map_mcp',
        'DeepSeekAI': 'deepseek_ai',
        'RouterAgent': 'router_agent',
        'SettingsAgent': 'settings_agent',
    }[name]
    return getattr(import_module(f'.{module}', __name__), name)

