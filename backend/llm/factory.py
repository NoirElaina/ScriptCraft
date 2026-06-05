import os
from collections.abc import Mapping

from llm.anthropic_client import AnthropicClient
from llm.base import LLMClient, LLMConfigError
from llm.env_loader import load_project_env
from llm.openai_client import OpenAICompatibleClient


def create_llm_client_from_env(env: Mapping[str, str] | None = None) -> LLMClient:
    source = _runtime_env() if env is None else env
    provider = source.get("LLM_PROVIDER", "openai").strip().lower()

    if provider == "openai":
        return OpenAICompatibleClient.from_env(source)
    if provider == "anthropic":
        return AnthropicClient.from_env(source)
    raise LLMConfigError("LLM_PROVIDER 只支持 openai 或 anthropic")


def _runtime_env() -> dict[str, str]:
    values = load_project_env()
    values.update(os.environ)
    return values
