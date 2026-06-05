import json
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_yaml_content


class ScriptYamlState(TypedDict, total=False):
    title: str
    chapters: Sequence[Mapping[str, Any]]
    characters: Sequence[Mapping[str, Any]]
    locations: Sequence[Mapping[str, Any]]
    events: Sequence[Mapping[str, Any]]
    messages: list[BaseMessage]
    raw_yaml: str
    result: str


class ScriptYamlGenerator:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_script_yaml_graph(model)

    def generate(
        self,
        title: str,
        chapters: Sequence[Mapping[str, Any]],
        characters: Sequence[Mapping[str, Any]],
        locations: Sequence[Mapping[str, Any]],
        events: Sequence[Mapping[str, Any]],
    ) -> str:
        state = self.graph.invoke(
            {
                "title": title.strip() or "未命名小说",
                "chapters": chapters,
                "characters": characters,
                "locations": locations,
                "events": events,
            }
        )
        return state["result"]


def build_script_yaml_graph(model: BaseChatModel):
    graph = StateGraph(ScriptYamlState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("validate_yaml", validate_yaml_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "validate_yaml")
    graph.add_edge("validate_yaml", END)
    return graph.compile()


def build_prompt_node(state: ScriptYamlState) -> ScriptYamlState:
    return {
        "messages": build_script_yaml_messages(
            title=state["title"],
            chapters=state["chapters"],
            characters=state["characters"],
            locations=state["locations"],
            events=state["events"],
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: ScriptYamlState) -> ScriptYamlState:
        try:
            response = model.invoke(state["messages"])
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_yaml": response.content}

    return node


def validate_yaml_node(state: ScriptYamlState) -> ScriptYamlState:
    payload, normalized_yaml = parse_yaml_content(state["raw_yaml"])
    _validate_script_yaml(payload)
    return {"result": normalized_yaml}


def build_script_yaml_messages(
    title: str,
    chapters: Sequence[Mapping[str, Any]],
    characters: Sequence[Mapping[str, Any]],
    locations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> list[BaseMessage]:
    source = {
        "title": title,
        "chapters": chapters,
        "characters": characters,
        "locations": locations,
        "events": events,
    }

    return [
        SystemMessage(
            content=(
                "你是专业的中文剧本改编师。请把小说章节改编成可编辑的剧本 YAML 初稿。"
                "只返回 YAML，不要返回 Markdown，不要解释。"
            )
        ),
        HumanMessage(
            content=(
                "请严格输出以下顶层字段：schema_version、title、metadata、characters、locations、events、scenes。\n"
                "metadata 必须包含 source_title、chapters_count、adaptation_style、language。\n"
                "每个 scene 必须包含 id、title、source_chapters、source_events、location_id、time_of_day、characters、dramatic_purpose、summary、beats。\n"
                "每个 beat 必须包含 type 和 content；type 只能使用 action、dialogue、narration、transition、sound；dialogue 必须包含 speaker_id。\n"
                "请保留输入中的角色、地点和事件 ID，不要凭空改变已有 ID。每章至少生成 1 个 scene，每个 scene 至少 3 个 beats。\n\n"
                "输入数据 JSON：\n"
                f"{json.dumps(source, ensure_ascii=False)}"
            )
        ),
    ]


def _validate_script_yaml(payload: Mapping[str, Any]) -> None:
    required_keys = ("schema_version", "title", "metadata", "characters", "locations", "events", "scenes")
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise LLMResponseError(f"AI 剧本 YAML 缺少字段：{', '.join(missing)}")
    if not isinstance(payload.get("scenes"), list) or not payload["scenes"]:
        raise LLMResponseError("AI 剧本 YAML 必须包含 scenes")

    for index, scene in enumerate(payload["scenes"], start=1):
        if not isinstance(scene, Mapping):
            raise LLMResponseError(f"第 {index} 个 scene 不是对象")
        if not isinstance(scene.get("beats"), list) or not scene["beats"]:
            raise LLMResponseError(f"第 {index} 个 scene 缺少 beats")
