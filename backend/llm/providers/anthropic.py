from collections.abc import Mapping

from langchain_anthropic import ChatAnthropic

from llm.providers.common import required_env


def create_anthropic_model(env: Mapping[str, str]) -> ChatAnthropic:
    return ChatAnthropic(
        api_key=required_env(env, "LLM_API_KEY"),
        base_url=required_env(env, "LLM_BASE_URL"),
        model_name=required_env(env, "LLM_MODEL"),
        streaming=True,
    )
