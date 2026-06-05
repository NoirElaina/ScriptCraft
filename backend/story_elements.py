from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_json_content


class StoryElementState(TypedDict, total=False):
    title: str
    chapters: Sequence[Mapping[str, Any]]
    messages: list[BaseMessage]
    raw_payload: dict[str, Any]
    result: dict[str, Any]


class StoryElementExtractor:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_story_element_graph(model)

    def extract(self, title: str, chapters: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        normalized_title = title.strip() or "未命名小说"
        state = self.graph.invoke({"title": normalized_title, "chapters": chapters})
        return state["result"]


def build_story_element_graph(model: BaseChatModel):
    graph = StateGraph(StoryElementState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("normalize", normalize_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "normalize")
    graph.add_edge("normalize", END)
    return graph.compile()


def build_prompt_node(state: StoryElementState) -> StoryElementState:
    return {
        "messages": build_story_element_messages(
            title=state["title"],
            chapters=state["chapters"],
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: StoryElementState) -> StoryElementState:
        try:
            response = model.invoke(state["messages"])
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_payload": parse_json_content(response.content)}

    return node


def normalize_node(state: StoryElementState) -> StoryElementState:
    return {"result": normalize_story_elements(state["title"], state["raw_payload"])}


def build_story_element_messages(title: str, chapters: Sequence[Mapping[str, Any]]) -> list[BaseMessage]:
    chapter_blocks = []
    for chapter in chapters:
        chapter_blocks.append(
            "\n".join(
                [
                    f"章节ID：{chapter.get('id', '')}",
                    f"章节标题：{chapter.get('heading', '')} {chapter.get('title', '')}".strip(),
                    f"章节正文：{chapter.get('content', '')}",
                ]
            )
        )

    return [
        SystemMessage(
            content=(
                "你是专业的小说改编剧本策划。请从小说章节中抽取角色、地点和关键剧情事件。"
                "只返回 JSON，不要返回 Markdown。"
            )
        ),
        HumanMessage(
            content=(
                f"作品名：{title}\n\n"
                "请返回如下 JSON：\n"
                "{\n"
                '  "characters": [{"id": "char_001", "name": "", "aliases": [], "role": "", "description": "", "motivation": ""}],\n'
                '  "locations": [{"id": "loc_001", "name": "", "description": ""}],\n'
                '  "events": [{"id": "event_001", "source_chapter": "chapter_001", "summary": "", "involved_characters": ["char_001"]}]\n'
                "}\n\n"
                "章节内容：\n"
                + "\n\n---\n\n".join(chapter_blocks)
            )
        ),
    ]


def normalize_story_elements(title: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": title,
        "characters": [
            {
                "id": _string(item.get("id"), f"char_{index:03d}"),
                "name": _string(item.get("name"), "未命名角色"),
                "aliases": _string_list(item.get("aliases")),
                "role": _string(item.get("role"), "supporting"),
                "description": _string(item.get("description"), ""),
                "motivation": _string(item.get("motivation"), ""),
            }
            for index, item in enumerate(_object_list(payload, "characters"), start=1)
        ],
        "locations": [
            {
                "id": _string(item.get("id"), f"loc_{index:03d}"),
                "name": _string(item.get("name"), "未命名地点"),
                "description": _string(item.get("description"), ""),
            }
            for index, item in enumerate(_object_list(payload, "locations"), start=1)
        ],
        "events": [
            {
                "id": _string(item.get("id"), f"event_{index:03d}"),
                "source_chapter": _string(item.get("source_chapter"), ""),
                "summary": _string(item.get("summary"), ""),
                "involved_characters": _string_list(item.get("involved_characters")),
            }
            for index, item in enumerate(_object_list(payload, "events"), start=1)
        ],
    }


def _object_list(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise LLMResponseError(f"AI 响应缺少数组字段：{key}")
    return [item for item in value if isinstance(item, Mapping)]


def _string(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
