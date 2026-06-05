import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from llm.base import LLMConfigError, LLMResponseError, parse_json_content


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAICompatibleClient:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 60) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "OpenAICompatibleClient":
        source = os.environ if env is None else env
        api_key = source.get("LLM_API_KEY", "").strip()
        base_url = source.get("LLM_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip()
        model = source.get("LLM_MODEL", "").strip()

        missing = [
            name
            for name, value in (
                ("LLM_API_KEY", api_key),
                ("LLM_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise LLMConfigError(f"缺少 AI 配置：{', '.join(missing)}")

        timeout = float(source.get("LLM_TIMEOUT_SECONDS", "60"))
        return cls(api_key=api_key, base_url=base_url, model=model, timeout=timeout)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            url=self._chat_completions_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
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
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMResponseError("AI 响应格式不符合预期") from exc

        return parse_json_content(content)

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"
