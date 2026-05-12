"""
LLM 响应 JSON 提取工具

部分模型（尤其是轻量版，如 deepseek-v4-flash）即便 system prompt 要求
"返回纯 JSON、无 markdown"，仍可能在 JSON 前后追加自然语言铺垫，
例如：

    好的，我先查一下这两个校区的具体位置。

    {"type":"tool_call","action":"geocoding", ...}

本模块提供一个鲁棒的提取函数，按下列顺序尝试解析，命中即返回：
  1. 整体即合法 JSON
  2. ```json ... ``` 或 ``` ... ``` markdown 代码块
  3. 括号配对扫描，抠出第一个完整的 {...} 或 [...]
     （正确处理字符串内的括号与转义）
"""
import json
import re


def extract_json_from_llm_response(text):
    """
    从 LLM 响应文本中提取出第一个完整的 JSON 字符串。

    Args:
        text: LLM 原始响应

    Returns:
        提取出的 JSON 字符串。若实在找不到，返回原文本（去首尾空白），
        交给调用方的 json.loads 抛出明确的 JSONDecodeError。
    """
    if not text:
        return text

    text = text.strip()

    # 1) 整体已是合法 JSON
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 2) Markdown 代码块（带 json 标签优先，再退化到通用三反引号）
    fenced = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if not fenced:
        fenced = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            # 代码块内仍可能包含说明文字，落到括号匹配
            text_for_brace = candidate
        else:
            return candidate
    else:
        text_for_brace = text

    # 3) 括号配对扫描第一个完整的 JSON 对象/数组
    extracted = _scan_balanced_json(text_for_brace)
    if extracted is not None:
        return extracted

    return text


def _scan_balanced_json(text):
    """
    用栈式扫描提取第一个完整的 {...} 或 [...]。
    正确处理：
      - 字符串内出现的 { } [ ] 不计入嵌套
      - 反斜杠转义的引号 \" 不会误判为字符串结束
    扫描失败返回 None。
    """
    start = -1
    open_char = ''
    for i, ch in enumerate(text):
        if ch in '{[':
            start = i
            open_char = ch
            break
    if start < 0:
        return None

    close_char = '}' if open_char == '{' else ']'
    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    return None

    return None
