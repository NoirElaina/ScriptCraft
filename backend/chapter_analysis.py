import json
from collections.abc import Mapping
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_json_content


class ChapterAnalysisState(TypedDict, total=False):
    title: str
    chapter: Mapping[str, Any]
    memory: Mapping[str, Any]
    messages: list[BaseMessage]
    raw_payload: dict[str, Any]
    result: dict[str, Any]


class ChapterAnalyzer:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_chapter_analysis_graph(model)

    def analyze(
        self,
        title: str,
        chapter: Mapping[str, Any],
        memory: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self.graph.invoke(
            {
                "title": title.strip() or "未命名小说",
                "chapter": chapter,
                "memory": memory or {},
            }
        )
        return state["result"]


def build_chapter_analysis_graph(model: BaseChatModel):
    graph = StateGraph(ChapterAnalysisState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("normalize", normalize_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "normalize")
    graph.add_edge("normalize", END)
    return graph.compile()


def build_prompt_node(state: ChapterAnalysisState) -> ChapterAnalysisState:
    return {
        "messages": build_chapter_analysis_messages(
            title=state["title"],
            chapter=state["chapter"],
            memory=state.get("memory", {}),
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: ChapterAnalysisState) -> ChapterAnalysisState:
        try:
            response = model.invoke(state["messages"])
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_payload": parse_json_content(response.content)}

    return node


def normalize_node(state: ChapterAnalysisState) -> ChapterAnalysisState:
    return {"result": normalize_chapter_analysis(state["chapter"], state["raw_payload"])}


def build_chapter_analysis_messages(
    title: str,
    chapter: Mapping[str, Any],
    memory: Mapping[str, Any] | None = None,
) -> list[BaseMessage]:
    memory = memory or {}
    return [
        SystemMessage(
            content=(
                "你是专业的小说改编策划。请只分析当前单章，不要推测未提供章节。"
                "你的目标是把小说正文压缩成后续剧本生成可复用的结构化资料。"
                "只返回 JSON，不要返回 Markdown。"
            )
        ),
        HumanMessage(
            content=(
                f"作品名：{title}\n"
                f"章节ID：{chapter.get('id', '')}\n"
                f"章节序号：{chapter.get('index', '')}\n"
                f"章节标题：{chapter.get('heading', '')} {chapter.get('title', '')}".strip()
                + "\n\n"
                "请返回如下 JSON：\n"
                "{\n"
                '  "summary": "本章 80-160 字摘要",\n'
                '  "characters": [{"name": "", "aliases": [], "role_in_chapter": "", "evidence": ""}],\n'
                '  "locations": [{"name": "", "description": "", "evidence": ""}],\n'
                '  "events": [{"summary": "", "event_type": "", "involved_characters": [], "evidence": ""}],\n'
                '  "conflicts": ["本章冲突"],\n'
                '  "dialogue_candidates": ["适合改编成对白的原文或改写素材"],\n'
                '  "scene_candidates": [{"title": "", "location": "", "characters": [], "summary": "", "dramatic_purpose": "", "beats": []}],\n'
                '  "continuity_notes": ["需要在后续章节保持一致的信息"]\n'
                "}\n\n"
                "前文短记忆 JSON：\n"
                f"{json.dumps(memory, ensure_ascii=False)}\n\n"
                "章节正文：\n"
                f"{chapter.get('content', '')}"
            )
        ),
    ]


def normalize_chapter_analysis(chapter: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = _required_string(payload.get("summary"), "summary")
    return {
        "chapter_id": _string(chapter.get("id"), ""),
        "chapter_index": _int(chapter.get("index"), 0),
        "heading": _string(chapter.get("heading"), ""),
        "title": _string(chapter.get("title"), ""),
        "summary": summary,
        "characters": [
            {
                "name": _string(item.get("name"), "未命名角色"),
                "aliases": _string_list(item.get("aliases")),
                "role_in_chapter": _string(item.get("role_in_chapter"), ""),
                "evidence": _string(item.get("evidence"), ""),
            }
            for item in _object_list(payload, "characters")
        ],
        "locations": [
            {
                "name": _string(item.get("name"), "未命名地点"),
                "description": _string(item.get("description"), ""),
                "evidence": _string(item.get("evidence"), ""),
            }
            for item in _object_list(payload, "locations")
        ],
        "events": [
            {
                "summary": _string(item.get("summary"), ""),
                "event_type": _string(item.get("event_type"), ""),
                "involved_characters": _string_list(item.get("involved_characters")),
                "evidence": _string(item.get("evidence"), ""),
            }
            for item in _object_list(payload, "events")
        ],
        "conflicts": _string_list(payload.get("conflicts")),
        "dialogue_candidates": _string_list(payload.get("dialogue_candidates")),
        "scene_candidates": [
            {
                "title": _string(item.get("title"), f"场景 {index}"),
                "location": _string(item.get("location"), ""),
                "characters": _string_list(item.get("characters")),
                "summary": _string(item.get("summary"), ""),
                "dramatic_purpose": _string(item.get("dramatic_purpose"), ""),
                "beats": _string_list(item.get("beats")),
            }
            for index, item in enumerate(_object_list(payload, "scene_candidates"), start=1)
        ],
        "continuity_notes": _string_list(payload.get("continuity_notes")),
    }


def _object_list(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise LLMResponseError(f"AI 响应缺少数组字段：{key}")
    return [item for item in value if isinstance(item, Mapping)]


def _required_string(value: Any, key: str) -> str:
    text = _string(value, "")
    if not text:
        raise LLMResponseError(f"AI 响应缺少文本字段：{key}")
    return text


def _string(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
