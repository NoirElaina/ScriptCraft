import json
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from llm.base import LLMResponseError
from llm.streaming import StreamCallback, invoke_model
from .card_tools import (
    ReadStoryCardsInput,
    StoryCardStore,
    UpsertCharacterCardInput,
    UpsertEventCardInput,
    UpsertLocationCardInput,
    UpsertSceneCardInput,
    ValidateStoryCardsInput,
)
from .context_tools import ChapterContextTools, ReadCurrentChapterInput, SearchProjectChaptersInput


TOOL_CALL_LIMIT = 24
VALIDATION_REPAIR_LIMIT = 3


class StoryElementMergeState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    operation_count: int
    validation_attempts: int
    on_stream: StreamCallback
    result: dict[str, list[dict[str, Any]]]


class ChapterStoryElementMerger:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def merge(
        self,
        title: str,
        chapter: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        project_chapters: Sequence[Mapping[str, Any]],
        on_stream: StreamCallback | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        card_store = StoryCardStore.from_snapshot(snapshot, on_stream=on_stream)
        chapter_tools = ChapterContextTools(
            current_chapter=chapter,
            project_chapters=project_chapters,
            on_stream=on_stream,
        )
        tools = _build_story_card_tools(card_store, chapter_tools)
        graph = _build_story_card_graph(self.model, tools, card_store)
        state = graph.invoke({"messages": _build_messages(title, chapter, card_store.snapshot), "on_stream": on_stream})
        return state["result"]


def _build_story_card_tools(card_store: StoryCardStore, chapter_tools: ChapterContextTools) -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            name="read_current_chapter",
            description="读取当前正在处理的章节正文和章节分析。抽取本章卡片前必须调用。",
            func=chapter_tools.read_current_chapter,
            args_schema=ReadCurrentChapterInput,
        ),
        StructuredTool.from_function(
            name="search_project_chapters",
            description="按关键词搜索项目内章节，用于确认漏掉的人物、地点、事件是否在原文中出现。",
            func=chapter_tools.search_project_chapters,
            args_schema=SearchProjectChaptersInput,
        ),
        StructuredTool.from_function(
            name="read_story_cards",
            description="读取当前故事卡片库。抽取前先读取，避免重复创建角色、地点、事件和场景。",
            func=card_store.read_story_cards,
            args_schema=ReadStoryCardsInput,
        ),
        StructuredTool.from_function(
            name="upsert_character_card",
            description="新增或修正角色卡片。后文揭示新性格、身份、动机时使用该工具更新已有角色。",
            func=card_store.upsert_character_card,
            args_schema=UpsertCharacterCardInput,
        ),
        StructuredTool.from_function(
            name="upsert_location_card",
            description="新增或修正地点卡片。",
            func=card_store.upsert_location_card,
            args_schema=UpsertLocationCardInput,
        ),
        StructuredTool.from_function(
            name="upsert_event_card",
            description="新增或修正事件卡片。事件参与角色必须引用已存在角色卡。",
            func=card_store.upsert_event_card,
            args_schema=UpsertEventCardInput,
        ),
        StructuredTool.from_function(
            name="upsert_scene_card",
            description="新增或修正场景卡片。场景用于后续剧本生成，必须引用已有地点和角色卡。",
            func=card_store.upsert_scene_card,
            args_schema=UpsertSceneCardInput,
        ),
        StructuredTool.from_function(
            name="validate_story_cards",
            description="校验当前卡片库的角色、地点、事件、场景引用是否一致。",
            func=card_store.validate_story_cards,
            args_schema=ValidateStoryCardsInput,
        ),
    ]


def _build_story_card_graph(model: BaseChatModel, tools: list[StructuredTool], card_store: StoryCardStore):
    bound_model = model.bind_tools(tools)
    graph = StateGraph(StoryElementMergeState)
    graph.add_node("agent", _call_model_node(bound_model))
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("sync_tools", _sync_tool_state_node(card_store))
    graph.add_node("validate", _validate_node(card_store))
    graph.add_node("finish", _finish_node(card_store))
    graph.add_node("missing_tool", _missing_tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        _route_after_agent,
        {
            "tools": "tools",
            "validate": "validate",
            "missing_tool": "missing_tool",
        },
    )
    graph.add_edge("tools", "sync_tools")
    graph.add_conditional_edges(
        "sync_tools",
        _route_after_tools,
        {
            "agent": "agent",
            "validate": "validate",
        },
    )
    graph.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "agent": "agent",
            "finish": "finish",
        },
    )
    graph.add_edge("finish", END)
    return graph.compile()


def _call_model_node(model: BaseChatModel):
    def node(state: StoryElementMergeState) -> StoryElementMergeState:
        try:
            response = invoke_model(
                model,
                state["messages"],
                on_stream=state.get("on_stream"),
                node="story_cards",
                title="故事卡片 Agent 输出",
            )
        except Exception as exc:
            raise LLMResponseError(f"AI 故事卡片工具流调用失败：{exc}") from exc
        return {"messages": [response]}

    return node


def _sync_tool_state_node(card_store: StoryCardStore):
    def node(state: StoryElementMergeState) -> StoryElementMergeState:
        return {"operation_count": len(card_store.operations)}

    return node


def _finish_node(card_store: StoryCardStore):
    def node(state: StoryElementMergeState) -> StoryElementMergeState:
        return {"result": state.get("result") or card_store.snapshot}

    return node


def _validate_node(card_store: StoryCardStore):
    def node(state: StoryElementMergeState) -> StoryElementMergeState:
        errors = card_store.validate_snapshot()
        if not errors:
            return {"result": card_store.snapshot}

        attempts = int(state.get("validation_attempts", 0)) + 1
        if attempts > VALIDATION_REPAIR_LIMIT:
            raise LLMResponseError("故事元素校验失败：" + "；".join(errors))

        return {
            "validation_attempts": attempts,
            "messages": [
                HumanMessage(
                    content=(
                        "卡片库结构校验失败，请读取当前章节、搜索项目章节、读取卡片并用工具修复，不要输出 JSON 或 YAML。\n"
                        f"修复轮次：{attempts}/{VALIDATION_REPAIR_LIMIT}\n"
                        "错误列表：\n"
                        + "\n".join(f"- {error}" for error in errors)
                    )
                )
            ],
        }

    return node


def _missing_tool_node(state: StoryElementMergeState) -> StoryElementMergeState:
    raise LLMResponseError("故事元素抽取必须调用卡片工具，不能只输出文本")


def _route_after_agent(state: StoryElementMergeState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "validate" if int(state.get("operation_count", 0)) > 0 else "missing_tool"


def _route_after_tools(state: StoryElementMergeState) -> str:
    return "validate" if int(state.get("operation_count", 0)) >= TOOL_CALL_LIMIT else "agent"


def _route_after_validate(state: StoryElementMergeState) -> str:
    return "finish" if state.get("result") else "agent"


def _build_messages(title: str, chapter: Mapping[str, Any], snapshot: Mapping[str, Any]) -> list[BaseMessage]:
    source = {
        "title": title,
        "current_chapter": chapter,
        "current_cards": snapshot,
    }
    chapter_id = str(chapter.get("id", "")).strip()

    return [
        SystemMessage(
            content=(
                "你是长篇小说资料管理员 Agent。你不能直接输出故事元素结果，必须通过工具维护卡片库。"
                "每次只处理当前章节，但要读取已有卡片，修正后文对前文角色、地点、事件、场景的影响。"
            )
        ),
        HumanMessage(
            content=(
                "请按以下顺序工作：\n"
                "1. 调用 read_current_chapter 读取当前章节正文和章节分析。\n"
                "2. 调用 read_story_cards 读取当前卡片库。\n"
                "3. 根据当前章节原文和分析，抽取新增或变化的角色、地点、事件、场景。\n"
                "4. 使用 upsert_character_card、upsert_location_card、upsert_event_card、upsert_scene_card 写入卡片。\n"
                "5. 如果后文揭示角色身份、性格、动机变化，必须更新已有角色卡，不要创建重复角色。\n"
                "6. 场景卡必须引用已有角色和地点；如果缺少角色或地点，先创建/更新对应卡片。\n"
                "7. 如果任意工具返回 ok=false 或 error，必须用 read_current_chapter 或 search_project_chapters 找证据，先补齐缺失卡片，再重新调用失败的工具。\n"
                "8. 调用 validate_story_cards 校验引用一致性。\n"
                "9. 完成工具写入后，回复一句“完成”。\n\n"
                "硬性规则：\n"
                f"- 本轮事件和场景的 source_chapter 必须是：{chapter_id}。\n"
                "- 不要把旁白、叙述者、画外音创建成角色卡。\n"
                "- 所有事件 involved_characters 必须能解析到角色卡。\n"
                "- 所有场景 characters/location/source_events 必须能解析到已有卡片。\n"
                "- 创建或更新卡片必须能在当前章节或 search_project_chapters 的证据中找到依据。\n"
                "- 不要输出 JSON 或 YAML，必须调用工具。\n\n"
                "输入数据 JSON：\n"
                f"{json.dumps(source, ensure_ascii=False)}"
            )
        ),
    ]
