import json
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_json_content
from llm.streaming import StreamCallback, invoke_model


class ChapterScenePlanState(TypedDict, total=False):
    title: str
    chapter: Mapping[str, Any]
    characters: Sequence[Mapping[str, Any]]
    locations: Sequence[Mapping[str, Any]]
    events: Sequence[Mapping[str, Any]]
    scene_cards: Sequence[Mapping[str, Any]]
    memory: Mapping[str, Any]
    messages: list[BaseMessage]
    on_stream: StreamCallback
    raw_payload: dict[str, Any]
    result: dict[str, Any]


class ChapterScenePlanner:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_chapter_scene_plan_graph(model)

    def plan(
        self,
        *,
        title: str,
        chapter: Mapping[str, Any],
        characters: Sequence[Mapping[str, Any]],
        locations: Sequence[Mapping[str, Any]],
        events: Sequence[Mapping[str, Any]],
        scene_cards: Sequence[Mapping[str, Any]],
        memory: Mapping[str, Any],
        on_stream: StreamCallback | None = None,
    ) -> dict[str, Any]:
        state = self.graph.invoke(
            {
                "title": title,
                "chapter": chapter,
                "characters": characters,
                "locations": locations,
                "events": events,
                "scene_cards": scene_cards,
                "memory": memory,
                "on_stream": on_stream,
            }
        )
        return state["result"]


def build_chapter_scene_plan_graph(model: BaseChatModel):
    graph = StateGraph(ChapterScenePlanState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("normalize", normalize_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "normalize")
    graph.add_edge("normalize", END)
    return graph.compile()


def build_prompt_node(state: ChapterScenePlanState) -> ChapterScenePlanState:
    return {
        "messages": build_chapter_scene_plan_messages(
            title=state["title"],
            chapter=state["chapter"],
            characters=state["characters"],
            locations=state["locations"],
            events=state["events"],
            scene_cards=state["scene_cards"],
            memory=state["memory"],
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: ChapterScenePlanState) -> ChapterScenePlanState:
        try:
            response = invoke_model(
                model,
                state["messages"],
                on_stream=state.get("on_stream"),
                node="scene_planning",
                title="场景规划模型输出",
            )
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_payload": parse_json_content(response.content)}

    return node


def normalize_node(state: ChapterScenePlanState) -> ChapterScenePlanState:
    return {
        "result": normalize_chapter_scene_plan(
            payload=state["raw_payload"],
            chapter=state["chapter"],
            characters=state["characters"],
            locations=state["locations"],
            events=state["events"],
        )
    }


def build_chapter_scene_plan_messages(
    *,
    title: str,
    chapter: Mapping[str, Any],
    characters: Sequence[Mapping[str, Any]],
    locations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    scene_cards: Sequence[Mapping[str, Any]],
    memory: Mapping[str, Any],
) -> list[BaseMessage]:
    chapter_index = _int(chapter.get("index"), 0)
    scene_prefix = f"scene_{chapter_index:03d}_"
    source = {
        "title": title,
        "current_chapter": chapter,
        "characters": characters,
        "locations": locations,
        "current_chapter_events": events,
        "current_chapter_scene_cards": scene_cards,
        "script_memory": memory,
    }

    return [
        SystemMessage(
            content=(
                "你是长篇小说剧本统筹。你每次只规划当前章节，不要要求或引用未提供章节正文。"
                "请根据当前章节分析和短记忆，把当前章拆成剧本场景计划。只返回 JSON，不要 Markdown。"
            )
        ),
        HumanMessage(
            content=(
                "请返回如下 JSON：\n"
                "{\n"
                f'  "chapter_id": "{chapter.get("id", "")}",\n'
                '  "scenes": [\n'
                "    {\n"
                f'      "id": "{scene_prefix}001",\n'
                '      "title": "",\n'
                '      "source_chapters": ["当前章节ID"],\n'
                '      "source_events": ["已有 event.id，可为空数组"],\n'
                '      "location_id": "已有 loc_xxx",\n'
                '      "time_of_day": "day/night/dusk/dawn/unknown",\n'
                '      "characters": ["已有 char_xxx"],\n'
                '      "dramatic_purpose": "",\n'
                '      "summary": "",\n'
                '      "key_beats": ["", "", ""]\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                "规则：\n"
                f"- 只规划当前章节：{chapter.get('id', '')}。\n"
                f"- scene.id 必须使用 {scene_prefix} 开头，按 001、002 递增。\n"
                "- source_chapters 只能包含当前章节 ID。\n"
                "- location_id 只能使用输入 locations 中已有 ID。\n"
                "- characters 只能使用输入 characters 中已有 ID。\n"
                "- source_events 只能使用 current_chapter_events 中已有 ID，可为空。\n"
                "- 每章至少 1 个场景，不写完整对白，不写 storyboard。\n\n"
                "- 优先复用 current_chapter_scene_cards 的场景标题、地点、出场角色、戏剧目的和关键节拍。\n\n"
                "输入数据 JSON：\n"
                f"{json.dumps(source, ensure_ascii=False)}"
            )
        ),
    ]


def normalize_chapter_scene_plan(
    *,
    payload: Mapping[str, Any],
    chapter: Mapping[str, Any],
    characters: Sequence[Mapping[str, Any]],
    locations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    chapter_id = _required_text(chapter, "id", "当前章节")
    if _required_text(payload, "chapter_id", "场景计划") != chapter_id:
        raise LLMResponseError("场景计划 chapter_id 必须等于当前章节 ID")

    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise LLMResponseError("场景计划必须包含非空 scenes")

    character_ids = {str(item.get("id", "")).strip() for item in characters if isinstance(item, Mapping)}
    location_ids = {str(item.get("id", "")).strip() for item in locations if isinstance(item, Mapping)}
    event_ids = {str(item.get("id", "")).strip() for item in events if isinstance(item, Mapping)}
    normalized_scenes: list[dict[str, Any]] = []
    used_scene_ids: set[str] = set()

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, Mapping):
            raise LLMResponseError(f"场景计划第 {index} 个 scene 不是对象")
        scene_id = _required_text(scene, "id", f"场景计划 scene[{index}]")
        if scene_id in used_scene_ids:
            raise LLMResponseError(f"场景计划 scene.id 重复：{scene_id}")
        used_scene_ids.add(scene_id)

        source_chapters = _required_string_list(scene.get("source_chapters"), f"{scene_id}.source_chapters")
        if source_chapters != [chapter_id]:
            raise LLMResponseError(f"{scene_id}.source_chapters 只能包含当前章节：{chapter_id}")

        location_id = _required_text(scene, "location_id", scene_id)
        if location_id not in location_ids:
            raise LLMResponseError(f"{scene_id} 引用了不存在的 location_id：{location_id}")

        scene_characters = _required_string_list(scene.get("characters"), f"{scene_id}.characters")
        for character_id in scene_characters:
            if character_id not in character_ids:
                raise LLMResponseError(f"{scene_id} 引用了不存在的角色：{character_id}")

        source_events = _string_list(scene.get("source_events"))
        for event_id in source_events:
            if event_id not in event_ids:
                raise LLMResponseError(f"{scene_id} 引用了不属于当前章的事件：{event_id}")

        key_beats = _required_string_list(scene.get("key_beats"), f"{scene_id}.key_beats")
        normalized_scenes.append(
            {
                "id": scene_id,
                "title": _required_text(scene, "title", scene_id),
                "source_chapters": source_chapters,
                "source_events": source_events,
                "location_id": location_id,
                "time_of_day": _required_text(scene, "time_of_day", scene_id),
                "characters": scene_characters,
                "dramatic_purpose": _required_text(scene, "dramatic_purpose", scene_id),
                "summary": _required_text(scene, "summary", scene_id),
                "key_beats": key_beats,
            }
        )

    return {"chapter_id": chapter_id, "scenes": normalized_scenes}


def _required_text(value: Mapping[str, Any], key: str, owner: str) -> str:
    text = str(value.get(key, "")).strip()
    if not text:
        raise LLMResponseError(f"{owner} 缺少 {key}")
    return text


def _required_string_list(value: Any, owner: str) -> list[str]:
    items = _string_list(value)
    if not items:
        raise LLMResponseError(f"{owner} 必须是非空文本数组")
    return items


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
