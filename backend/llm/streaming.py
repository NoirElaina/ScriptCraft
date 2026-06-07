from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage


StreamCallback = Callable[[dict[str, Any]], None]


class _TokenStreamHandler(BaseCallbackHandler):
    def __init__(self, on_stream: StreamCallback, node: str, title: str) -> None:
        self.on_stream = on_stream
        self.node = node
        self.title = title
        self.buffer: list[str] = []
        self.has_emitted = False

    def on_llm_new_token(self, token: str, **_: Any) -> None:
        if not token:
            return
        self.buffer.append(token)
        if sum(len(item) for item in self.buffer) >= 120:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        self.has_emitted = True
        self.on_stream(
            {
                "type": "assistant",
                "node": self.node,
                "title": self.title,
                "content": "".join(self.buffer),
                "append": True,
            }
        )
        self.buffer = []


def invoke_model(
    model: BaseChatModel,
    messages: Sequence[BaseMessage],
    *,
    on_stream: StreamCallback | None = None,
    node: str,
    title: str,
) -> BaseMessage:
    if on_stream is None:
        return model.invoke(messages)

    on_stream({"type": "model_start", "node": node, "title": title, "content": "开始请求模型。"})
    handler = _TokenStreamHandler(on_stream, node, title)
    response = model.invoke(messages, config={"callbacks": [handler]})
    handler.flush()

    content = message_content_to_text(response.content)
    if content and not handler.has_emitted:
        on_stream({"type": "assistant", "node": node, "title": title, "content": content})

    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        on_stream(
            {
                "type": "tool_call",
                "node": node,
                "title": "准备调用工具",
                "content": format_tool_calls(tool_calls),
            }
        )
    return response


def emit_tool_event(
    on_stream: StreamCallback | None,
    *,
    node: str,
    title: str,
    content: str,
    event_type: str = "tool_result",
) -> None:
    if on_stream is None:
        return
    on_stream({"type": event_type, "node": node, "title": title, "content": content})


def format_tool_calls(tool_calls: Any) -> str:
    if not isinstance(tool_calls, list):
        return str(tool_calls)

    lines: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            lines.append(str(call))
            continue
        name = str(call.get("name") or call.get("tool") or "tool")
        args = call.get("args")
        lines.append(f"- {name}: {_compact(args)}")
    return "\n".join(lines)


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip() if content is not None else ""


def _compact(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 180 else text[:177] + "..."
