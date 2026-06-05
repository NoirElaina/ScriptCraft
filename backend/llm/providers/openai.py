from collections.abc import Mapping

from langchain_openai import ChatOpenAI

from llm.providers.common import required_env


def create_openai_model(env: Mapping[str, str]) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=required_env(env, "LLM_API_KEY"),
        base_url=required_env(env, "LLM_BASE_URL"),
        model=required_env(env, "LLM_MODEL"),
    )
