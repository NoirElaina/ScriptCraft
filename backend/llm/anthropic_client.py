import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from llm.base import LLMConfigError, LLMResponseError, parse_json_content


DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicClient:
    def __init__(self, api_key: str, base_url: str, model: str, max_tokens: int, timeout: float = 60) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AnthropicClient":
        source = os.environ if env is None else env
        api_key = source.get("ANTHROPIC_API_KEY", source.get("LLM_API_KEY", "")).strip()
        base_url = source.get("ANTHROPIC_BASE_URL", source.get("LLM_BASE_URL", DEFAULT_ANTHROPIC_BASE_URL)).strip()
        model = source.get("ANTHROPIC_MODEL", source.get("LLM_MODEL", "")).strip()

        missing = [
            name
            for name, value in (
                ("ANTHROPIC_API_KEY 或 LLM_API_KEY", api_key),
                ("ANTHROPIC_MODEL 或 LLM_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise LLMConfigError(f"缺少 AI 配置：{', '.join(missing)}")

        max_tokens = int(source.get("LLM_MAX_TOKENS", "4000"))
        timeout = float(source.get("LLM_TIMEOUT_SECONDS", "60"))
        return cls(api_key=api_key, base_url=base_url, model=model, max_tokens=max_tokens, timeout=timeout)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": 0.2,
            "system": _collect_message_content(messages, "system"),
            "messages": [
                {
                    "role": message["role"],
                    "content": message["content"],
                }
                for message in messages
                if message["role"] in {"user", "assistant"}
            ],
        }
        request = urllib.request.Request(
            url=self._messages_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise LLMResponseError(f"AI 服务返回错误：{exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMResponseError(f"AI 服务请求失败：{exc.reason}") from exc

        try:
            body = json.loads(raw_body)
            content = "\n".join(
                block.get("text", "")
                for block in body["content"]
                if isinstance(block, Mapping) and block.get("type") == "text"
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise LLMResponseError("AI 响应格式不符合预期") from exc

        return parse_json_content(content)

    def _messages_url(self) -> str:
        if self.base_url.endswith("/messages"):
            return self.base_url
        return f"{self.base_url}/messages"


def _collect_message_content(messages: list[dict[str, str]], role: str) -> str:
    return "\n".join(message["content"] for message in messages if message["role"] == role)
