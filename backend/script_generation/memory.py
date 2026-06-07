import json
from collections.abc import Mapping
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_json_content
from llm.streaming import StreamCallback, invoke_model


EMPTY_SCRIPT_MEMORY = {
    "story_so_far": "",
    "character_state": [],
    "open_threads": [],
    "used_events": [],
    "last_scene_summary": "",
}


class ScriptMemoryState(TypedDict, total=False):
    title: str
    chapter: Mapping[str, Any]
    plan: Mapping[str, Any]
    fragment: Mapping[str, Any]
    previous_memory: Mapping[str, Any]
    messages: list[BaseMessage]
    on_stream: StreamCallback
    raw_payload: dict[str, Any]
    result: dict[str, Any]


class ScriptMemoryUpdater:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_script_memory_graph(model)

    def update(
        self,
        *,
        title: str,
        chapter: Mapping[str, Any],
        plan: Mapping[str, Any],
        fragment: Mapping[str, Any],
        previous_memory: Mapping[str, Any],
        on_stream: StreamCallback | None = None,
    ) -> dict[str, Any]:
        state = self.graph.invoke(
            {
                "title": title,
                "chapter": chapter,
                "plan": plan,
                "fragment": fragment,
                "previous_memory": previous_memory,
                "on_stream": on_stream,
            }
        )
        return state["result"]


def build_script_memory_graph(model: BaseChatModel):
    graph = StateGraph(ScriptMemoryState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("normalize", normalize_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "normalize")
    graph.add_edge("normalize", END)
    return graph.compile()


def build_prompt_node(state: ScriptMemoryState) -> ScriptMemoryState:
    return {
        "messages": build_script_memory_messages(
            title=state["title"],
            chapter=state["chapter"],
            plan=state["plan"],
            fragment=state["fragment"],
            previous_memory=state["previous_memory"],
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: ScriptMemoryState) -> ScriptMemoryState:
        try:
            response = invoke_model(
                model,
                state["messages"],
                on_stream=state.get("on_stream"),
                node="script_memory",
                title="剧本记忆模型输出",
            )
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_payload": parse_json_content(response.content)}

    return node


def normalize_node(state: ScriptMemoryState) -> ScriptMemoryState:
    return {"result": normalize_script_memory(state["raw_payload"])}


def build_script_memory_messages(
    *,
    title: str,
    chapter: Mapping[str, Any],
    plan: Mapping[str, Any],
    fragment: Mapping[str, Any],
    previous_memory: Mapping[str, Any],
) -> list[BaseMessage]:
    source = {
        "title": title,
        "current_chapter": chapter,
        "chapter_scene_plan": plan,
        "generated_chapter_yaml_fragment": fragment,
        "previous_script_memory": previous_memory,
    }

    return [
        SystemMessage(
            content=(
                "你是长篇剧本连续性编辑。请把当前章节生成结果压缩为下一章可用的短记忆。"
                "只返回 JSON，不要 Markdown，不要复述完整章节。"
            )
        ),
        HumanMessage(
            content=(
                "请返回如下 JSON：\n"
                "{\n"
                '  "story_so_far": "截至当前章的 120-240 字剧情摘要",\n'
                '  "character_state": [{"character_id": "", "current_goal": "", "relationship_changes": []}],\n'
                '  "open_threads": ["尚未解决的伏笔或冲突"],\n'
                '  "used_events": ["已经改编进剧本的 event.id"],\n'
                '  "last_scene_summary": "当前章最后一个场景的结果"\n'
                "}\n\n"
                "规则：\n"
                "- character_id 和 used_events 必须来自输入里已有 ID。\n"
                "- 不要保存完整正文，只保存后续章节必须知道的信息。\n\n"
                "输入数据 JSON：\n"
                f"{json.dumps(source, ensure_ascii=False)}"
            )
        ),
    ]


def normalize_script_memory(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "story_so_far": _required_text(payload, "story_so_far", "script_memory"),
        "character_state": [
            {
                "character_id": _required_text(item, "character_id", "character_state"),
                "current_goal": _required_text(item, "current_goal", "character_state"),
                "relationship_changes": _string_list(item.get("relationship_changes")),
            }
            for item in _object_list(payload.get("character_state"), "character_state")
        ],
        "open_threads": _string_list(payload.get("open_threads")),
        "used_events": _string_list(payload.get("used_events")),
        "last_scene_summary": _required_text(payload, "last_scene_summary", "script_memory"),
    }


def _object_list(value: Any, owner: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise LLMResponseError(f"{owner} 必须是数组")
    return [item for item in value if isinstance(item, Mapping)]


def _required_text(value: Mapping[str, Any], key: str, owner: str) -> str:
    text = str(value.get(key, "")).strip()
    if not text:
        raise LLMResponseError(f"{owner} 缺少 {key}")
    return text


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
