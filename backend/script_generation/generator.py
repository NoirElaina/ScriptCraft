from collections.abc import Callable, Mapping, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from .fragment import ChapterScriptFragmentGenerator
from .memory import EMPTY_SCRIPT_MEMORY, ScriptMemoryUpdater
from .planner import ChapterScenePlanner
from .validation import normalize_script_yaml_payload

ProgressCallback = Callable[[dict[str, Any]], None]


class ScriptYamlGenerator:
    def __init__(self, model: BaseChatModel) -> None:
        self.planner = ChapterScenePlanner(model)
        self.fragment_generator = ChapterScriptFragmentGenerator(model)
        self.memory_updater = ScriptMemoryUpdater(model)

    def generate(
        self,
        title: str,
        chapters: Sequence[Mapping[str, Any]],
        characters: Sequence[Mapping[str, Any]],
        locations: Sequence[Mapping[str, Any]],
        events: Sequence[Mapping[str, Any]],
        on_progress: ProgressCallback | None = None,
    ) -> str:
        normalized_title = title.strip() or "未命名小说"
        sorted_chapters = sorted(chapters, key=lambda chapter: _int(chapter.get("index"), 0))
        chapter_total = len(sorted_chapters)
        memory: dict[str, Any] = dict(EMPTY_SCRIPT_MEMORY)
        fragments: list[dict[str, Any]] = []

        for offset, chapter in enumerate(sorted_chapters, start=1):
            chapter_events = _events_for_chapter(events, str(chapter.get("id", "")).strip())
            _report_progress(on_progress, "scene_planning", chapter, offset, chapter_total, offset - 1, len(fragments))
            plan = self.planner.plan(
                title=normalized_title,
                chapter=chapter,
                characters=characters,
                locations=locations,
                events=chapter_events,
                memory=memory,
            )
            _report_progress(on_progress, "fragment_generation", chapter, offset, chapter_total, offset - 1, len(fragments))
            fragment = self.fragment_generator.generate(
                title=normalized_title,
                chapter=chapter,
                plan=plan,
                characters=characters,
                locations=locations,
                events=chapter_events,
                memory=memory,
            )
            fragments.append(fragment)
            _report_progress(on_progress, "memory_update", chapter, offset, chapter_total, offset - 1, len(fragments))
            memory = self.memory_updater.update(
                title=normalized_title,
                chapter=chapter,
                plan=plan,
                fragment=fragment,
                previous_memory=memory,
            )
            _report_progress(on_progress, "chapter_completed", chapter, offset, chapter_total, offset, len(fragments))

        _report_progress(on_progress, "assemble", None, chapter_total, chapter_total, chapter_total, len(fragments))
        yaml_content = normalize_script_yaml_payload(
            assemble_script_yaml_payload(
                title=normalized_title,
                chapters=sorted_chapters,
                characters=characters,
                locations=locations,
                events=events,
                fragments=fragments,
                memory=memory,
            )
        )
        _report_progress(on_progress, "finished", None, chapter_total, chapter_total, chapter_total, len(fragments))
        return yaml_content


def assemble_script_yaml_payload(
    *,
    title: str,
    chapters: Sequence[Mapping[str, Any]],
    characters: Sequence[Mapping[str, Any]],
    locations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    fragments: Sequence[Mapping[str, Any]],
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    scenes: list[Mapping[str, Any]] = []
    storyboard_scenes: list[Mapping[str, Any]] = []
    for fragment in fragments:
        scenes.extend(_object_items(fragment.get("scenes")))
        storyboard = fragment.get("storyboard")
        if isinstance(storyboard, Mapping):
            storyboard_scenes.extend(_object_items(storyboard.get("scenes")))

    return {
        "schema_version": "2.0",
        "title": title,
        "metadata": {
            "source_title": title,
            "chapters_count": len(chapters),
            "adaptation_style": "长篇章节流式改编",
            "language": "zh-CN",
            "script_memory": memory,
        },
        "characters": list(characters),
        "locations": list(locations),
        "events": list(events),
        "scenes": scenes,
        "storyboard": {
            "scenes": storyboard_scenes,
        },
    }


def _events_for_chapter(events: Sequence[Mapping[str, Any]], chapter_id: str) -> list[Mapping[str, Any]]:
    matched_events = []
    for event in events:
        source_chapter = str(event.get("source_chapter", "")).strip()
        source_chapters = event.get("source_chapters")
        if source_chapter == chapter_id:
            matched_events.append(event)
        elif isinstance(source_chapters, list) and chapter_id in {str(item).strip() for item in source_chapters}:
            matched_events.append(event)
    return matched_events


def _object_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _report_progress(
    callback: ProgressCallback | None,
    phase: str,
    chapter: Mapping[str, Any] | None,
    chapter_index: int,
    chapter_total: int,
    completed_chapters: int,
    fragment_count: int,
) -> None:
    if callback is None:
        return

    current_title = ""
    current_id = ""
    if chapter is not None:
        current_title = str(chapter.get("title") or chapter.get("heading") or "").strip()
        current_id = str(chapter.get("id", "")).strip()

    callback(
        {
            "phase": phase,
            "chapter_index": chapter_index,
            "chapter_total": chapter_total,
            "completed_chapters": completed_chapters,
            "current_chapter_id": current_id,
            "current_chapter_title": current_title,
            "fragment_count": fragment_count,
            "message": _progress_message(phase, chapter_index, chapter_total, current_title),
        }
    )


def _progress_message(phase: str, chapter_index: int, chapter_total: int, chapter_title: str) -> str:
    title = f"《{chapter_title}》" if chapter_title else f"第 {chapter_index} 章"
    if phase == "scene_planning":
        return f"正在规划 {title} 的剧本场景：{chapter_index}/{chapter_total}"
    if phase == "fragment_generation":
        return f"正在生成 {title} 的 YAML 片段：{chapter_index}/{chapter_total}"
    if phase == "memory_update":
        return f"正在更新 {title} 后的剧本记忆：{chapter_index}/{chapter_total}"
    if phase == "chapter_completed":
        return f"第 {chapter_index}/{chapter_total} 章剧本片段已完成"
    if phase == "assemble":
        return "正在组装完整剧本 YAML"
    return "剧本 YAML 生成完成"


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
