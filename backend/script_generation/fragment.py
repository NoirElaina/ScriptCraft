import json
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from llm.base import LLMResponseError, parse_yaml_content
from llm.streaming import StreamCallback, invoke_model
from .validation import validate_script_yaml_fragment

SCRIPT_FRAGMENT_REPAIR_LIMIT = 2


class ChapterScriptFragmentState(TypedDict, total=False):
    title: str
    chapter: Mapping[str, Any]
    plan: Mapping[str, Any]
    characters: Sequence[Mapping[str, Any]]
    locations: Sequence[Mapping[str, Any]]
    events: Sequence[Mapping[str, Any]]
    scene_cards: Sequence[Mapping[str, Any]]
    memory: Mapping[str, Any]
    messages: list[BaseMessage]
    on_stream: StreamCallback
    raw_yaml: Any
    result: dict[str, Any]
    repair_attempts: int
    validation_error: str


class ChapterScriptFragmentGenerator:
    def __init__(self, model: BaseChatModel) -> None:
        self.graph = build_chapter_script_fragment_graph(model)

    def generate(
        self,
        *,
        title: str,
        chapter: Mapping[str, Any],
        plan: Mapping[str, Any],
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
                "plan": plan,
                "characters": characters,
                "locations": locations,
                "events": events,
                "scene_cards": scene_cards,
                "memory": memory,
                "on_stream": on_stream,
            }
        )
        return state["result"]


def build_chapter_script_fragment_graph(model: BaseChatModel):
    graph = StateGraph(ChapterScriptFragmentState)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("call_model", call_model_node(model))
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "build_prompt")
    graph.add_edge("build_prompt", "call_model")
    graph.add_edge("call_model", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "retry": "call_model",
            "finish": END,
        },
    )
    return graph.compile()


def build_prompt_node(state: ChapterScriptFragmentState) -> ChapterScriptFragmentState:
    return {
        "messages": build_chapter_script_fragment_messages(
            title=state["title"],
            chapter=state["chapter"],
            plan=state["plan"],
            characters=state["characters"],
            locations=state["locations"],
            events=state["events"],
            scene_cards=state["scene_cards"],
            memory=state["memory"],
        )
    }


def call_model_node(model: BaseChatModel):
    def node(state: ChapterScriptFragmentState) -> ChapterScriptFragmentState:
        try:
            response = invoke_model(
                model,
                state["messages"],
                on_stream=state.get("on_stream"),
                node="yaml_writer",
                title="章节 YAML 模型输出",
            )
        except Exception as exc:
            raise LLMResponseError(f"AI 服务调用失败：{exc}") from exc
        return {"raw_yaml": response.content}

    return node


def validate_node(state: ChapterScriptFragmentState) -> ChapterScriptFragmentState:
    try:
        payload, _ = parse_yaml_content(state["raw_yaml"])
        validate_script_yaml_fragment(
            payload,
            title=state["title"],
            chapter_count=1,
            characters=state["characters"],
            locations=state["locations"],
            events=state["events"],
        )
        return {"result": payload}
    except LLMResponseError as exc:
        repair_attempts = int(state.get("repair_attempts", 0))
        if repair_attempts >= SCRIPT_FRAGMENT_REPAIR_LIMIT:
            raise
        return {
            "messages": build_chapter_script_fragment_repair_messages(
                current_messages=state["messages"],
                raw_yaml=state["raw_yaml"],
                validation_error=str(exc),
            ),
            "repair_attempts": repair_attempts + 1,
            "validation_error": str(exc),
        }


def route_after_validation(state: ChapterScriptFragmentState) -> str:
    return "finish" if state.get("result") else "retry"


def build_chapter_script_fragment_messages(
    *,
    title: str,
    chapter: Mapping[str, Any],
    plan: Mapping[str, Any],
    characters: Sequence[Mapping[str, Any]],
    locations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    scene_cards: Sequence[Mapping[str, Any]],
    memory: Mapping[str, Any],
) -> list[BaseMessage]:
    chapter_index = _int(chapter.get("index"), 0)
    beat_prefix = f"beat_{chapter_index:03d}_"
    shot_prefix = f"shot_{chapter_index:03d}_"
    source = {
        "title": title,
        "current_chapter": chapter,
        "chapter_scene_plan": plan,
        "characters": characters,
        "locations": locations,
        "current_chapter_events": events,
        "current_chapter_scene_cards": scene_cards,
        "script_memory": memory,
    }

    return [
        SystemMessage(
            content=(
                "你是中文剧本改编师和分镜导演。你只生成当前章节的 YAML 片段，"
                "不要生成完整剧本顶层 metadata/characters/locations/events。只返回 YAML，不要 Markdown。"
            )
        ),
        HumanMessage(
            content=(
                "请严格返回如下章节 YAML 片段顶层字段：scenes、storyboard。\n"
                "scenes 必须完全覆盖输入 chapter_scene_plan.scenes。\n"
                "每个 scene 必须包含 id、title、source_chapters、source_events、location_id、time_of_day、characters、dramatic_purpose、summary、beats。\n"
                "每个 beat 必须包含 id、type、content；type 只能使用 action、dialogue、narration、transition、sound；dialogue 必须包含 speaker_id。\n"
                "storyboard 必须包含 scenes 数组，每个 storyboard scene 必须包含 scene_id、setting、cast、timeline。\n"
                "setting 必须包含 mood、weather、lighting、background。\n"
                "cast 中每个角色必须包含 character_id、position、pose；position 只能使用 left、center、right、back_left、back_right；环境空镜、旁白、转场或声音场可以使用空 cast。\n"
                "timeline 中每个 shot 必须包含 id、source_beat_id、type、duration_ms、camera、actions，可包含 dialogue、effects、props。\n"
                "camera 必须包含 shot、target、movement；shot 使用 wide、medium、close、insert；movement 使用 cut、slow_push、pan、shake、hold。\n"
                "actions 中每个动作必须包含 actor、motion、from、to、emotion；from/to 可以使用 left、center、right、back_left、back_right、offscreen_left、offscreen_right。\n"
                "dialogue 类型 shot 必须包含 dialogue.speaker_id 和 dialogue.text。\n"
                "凡是出现在 dialogue.speaker_id 或 actions.actor 中的角色，都必须写入当前 storyboard scene.cast，并分配画布内 position。\n"
                "旁白、叙述者、画外音不要作为角色加入 characters 或 storyboard.cast；旁白内容必须使用 narration 类型 beat/shot，不要使用 dialogue.speaker_id。\n"
                "action 类型 shot 必须至少包含 actions、effects 或 props 中的一项。\n"
                f"beat.id 必须使用 {beat_prefix}<场序号>_<拍序号>，shot.id 必须使用 {shot_prefix}<场序号>_<镜头序号>。\n"
                "只使用输入中的角色、地点、事件 ID，不要新增 ID。\n\n"
                "优先复用 current_chapter_scene_cards 的场景划分、戏剧目的、关键节拍和角色出场信息。\n\n"
                "输入数据 JSON：\n"
                f"{json.dumps(source, ensure_ascii=False)}"
            )
        ),
    ]


def build_chapter_script_fragment_repair_messages(
    *,
    current_messages: list[BaseMessage],
    raw_yaml: Any,
    validation_error: str,
) -> list[BaseMessage]:
    return [
        *current_messages,
        HumanMessage(
            content=(
                "你刚才输出的章节 YAML 片段没有通过结构校验。请只修复当前章节片段，并返回完整片段。\n"
                "不要返回 Markdown，不要解释，不要生成完整剧本顶层 metadata/characters/locations/events。\n"
                "如果 dialogue.speaker_id 或 actions.actor 未出现在 cast 中，请把该角色加入当前 storyboard scene.cast 并分配站位。\n"
                "如果 action 类型 shot 没有 actions、effects 或 props，请补充符合该 beat 的舞台动作、效果或道具。\n\n"
                "如果内容是旁白、叙述者或画外音，请改成 narration 类型，不要把旁白加入 cast 或作为 dialogue.speaker_id。\n\n"
                f"校验错误：{validation_error}\n\n"
                "需要修复的章节 YAML 片段：\n"
                f"{raw_yaml}"
            )
        ),
    ]


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
