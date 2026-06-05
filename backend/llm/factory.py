import os
from collections.abc import Mapping

from langchain_core.language_models.chat_models import BaseChatModel

from llm.base import LLMConfigError
from llm.env_loader import load_project_env
from llm.providers.anthropic import create_anthropic_model
from llm.providers.common import required_env
from llm.providers.openai import create_openai_model


PROVIDER_FACTORIES = {
    "openai": create_openai_model,
    "anthropic": create_anthropic_model,
}


def create_chat_model_from_env(env: Mapping[str, str] | None = None) -> BaseChatModel:
    source = _runtime_env() if env is None else env
    provider = required_env(source, "LLM_PROVIDER").lower()

    try:
        factory = PROVIDER_FACTORIES[provider]
    except KeyError as exc:
        raise LLMConfigError("LLM_PROVIDER 只支持 openai 或 anthropic") from exc
    return factory(source)


def _runtime_env() -> dict[str, str]:
    values = load_project_env()
    values.update(os.environ)
    return values


create_llm_client_from_env = create_chat_model_from_env
