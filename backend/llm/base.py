import json
import re
from typing import Any, Protocol


class LLMConfigError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        pass


def parse_json_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
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
