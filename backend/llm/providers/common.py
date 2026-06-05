from collections.abc import Mapping

from llm.base import LLMConfigError


def required_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise LLMConfigError(f"缺少 AI 配置：{name}")
    return value
