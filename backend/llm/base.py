import json
import re
from collections.abc import Mapping
from typing import Any

import yaml


class LLMConfigError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


def parse_json_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        content = "\n".join(_text_from_content_part(part) for part in content)
    if not isinstance(content, str):
        raise LLMResponseError("AI 响应内容不是 JSON 文本")

    text = content.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= start:
            text = text[start : end + 1]

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("AI 响应不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise LLMResponseError("AI 响应 JSON 顶层必须是对象")
    return payload


def parse_yaml_content(content: Any) -> tuple[dict[str, Any], str]:
    text = _message_content_to_text(content).strip()
    if not text:
        raise LLMResponseError("AI 响应内容为空")

    fence_match = re.search(r"```(?:yaml|yml)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise LLMResponseError("AI 响应不是合法 YAML") from exc
    if not isinstance(payload, dict):
        raise LLMResponseError("AI 响应 YAML 顶层必须是对象")

    normalized = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return payload, normalized


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text_from_content_part(part) for part in content)
    return ""


def _text_from_content_part(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, Mapping):
        text = part.get("text", "")
        return text if isinstance(text, str) else ""
    return ""
