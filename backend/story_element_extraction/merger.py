import json
from collections.abc import Mapping
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_json_content


class StoryElementMergeState(TypedDict, total=False):
    title: str
    chapter: Mapping[str, Any]
    snapshot: Mapping[str, Any]
    messages: list[BaseMessage]
    raw_payload: dict[str, Any]
    result: dict[str, Any]


class ChapterStoryElementMerger:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_story_element_merge_graph(model)

    def merge(self, title: str, chapter: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
        state = self.graph.invoke({"title": title, "chapter": chapter, "snapshot": snapshot})
        return state["result"]


def build_story_element_merge_graph(model: BaseChatModel):
    graph = StateGraph(StoryElementMergeState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("normalize", normalize_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "normalize")
    graph.add_edge("normalize", END)
    return graph.compile()


def build_prompt_node(state: StoryElementMergeState) -> StoryElementMergeState:
    return {
        "messages": build_story_element_merge_messages(
            title=state["title"],
            chapter=state["chapter"],
            snapshot=state["snapshot"],
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: StoryElementMergeState) -> StoryElementMergeState:
        try:
            response = model.invoke(state["messages"])
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_payload": parse_json_content(response.content)}

    return node


def normalize_node(state: StoryElementMergeState) -> StoryElementMergeState:
    return {"result": normalize_story_element_updates(state["raw_payload"])}


def build_story_element_merge_messages(title: str, chapter: Mapping[str, Any], snapshot: Mapping[str, Any]) -> list[BaseMessage]:
    source = {
        "title": title,
        "current_chapter": chapter,
        "current_story_elements": snapshot,
    }

    return [
        SystemMessage(
            content=(
                "你是长篇小说剧本资料管理员。你每次只处理当前章节分析，"
                "把新出现或变化的角色、地点、事件转成更新指令。只返回 JSON，不要 Markdown。"
            )
        ),
        HumanMessage(
            content=(
                "请返回如下 JSON：\n"
                "{\n"
                '  "character_updates": [\n'
                '    {"action": "create", "name": "", "aliases": [], "role": "", "description": "", "motivation": ""},\n'
                '    {"action": "merge", "target_id": "char_001", "name": "", "new_aliases": [], "role": "", "description_patch": "", "motivation_patch": ""}\n'
                "  ],\n"
                '  "location_updates": [\n'
                '    {"action": "create", "name": "", "description": ""},\n'
                '    {"action": "merge", "target_id": "loc_001", "description_patch": ""}\n'
                "  ],\n"
                '  "event_updates": [\n'
                '    {"action": "create", "source_chapter": "当前章节ID", "summary": "", "involved_characters": ["已有角色ID或本章新建角色名"]},\n'
                '    {"action": "merge", "target_id": "event_001", "summary_patch": "", "involved_characters": ["已有角色ID或角色名"]}\n'
                "  ]\n"
                "}\n\n"
                "规则：\n"
                "- 只处理 current_chapter，不要引用未提供章节。\n"
                "- 如果角色/地点已在 current_story_elements 中存在，使用 merge，不要 create 重复项。\n"
                "- create 不需要填写 id，后端会分配稳定 ID。\n"
                "- event_updates 的 source_chapter 必须是当前章节 ID。\n"
                "- involved_characters 可以使用已有角色 ID，也可以使用本章 character_updates 中 create 的角色名。\n"
                "- 没有更新时返回空数组。\n\n"
                "输入数据 JSON：\n"
                f"{json.dumps(source, ensure_ascii=False)}"
            )
        ),
    ]


def normalize_story_element_updates(payload: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "character_updates": [_normalize_update(item, "character_update") for item in _required_list(payload, "character_updates")],
        "location_updates": [_normalize_update(item, "location_update") for item in _required_list(payload, "location_updates")],
        "event_updates": [_normalize_update(item, "event_update") for item in _required_list(payload, "event_updates")],
    }


def _normalize_update(item: Any, owner: str) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise LLMResponseError(f"{owner} 必须是对象")
    action = _required_text(item, "action", owner)
    if action not in {"create", "merge"}:
        raise LLMResponseError(f"{owner}.action 只能是 create 或 merge")
    if action == "merge":
        _required_text(item, "target_id", owner)
    return dict(item)


def _required_list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise LLMResponseError(f"AI 响应缺少数组字段：{key}")
    return value


def _required_text(value: Mapping[str, Any], key: str, owner: str) -> str:
    text = str(value.get(key, "")).strip()
    if not text:
        raise LLMResponseError(f"{owner} 缺少 {key}")
    return text
