from collections.abc import Callable, Mapping, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from .merger import ChapterStoryElementMerger
from .store import apply_story_element_updates, empty_story_element_snapshot

ProgressCallback = Callable[[dict[str, Any]], None]


class StoryElementExtractor:
    def __init__(self, model: BaseChatModel) -> None:
        self.merger = ChapterStoryElementMerger(model)

    def extract(
        self,
        title: str,
        chapters: Sequence[Mapping[str, Any]],
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        normalized_title = title.strip() or "未命名小说"
        snapshot = empty_story_element_snapshot()
        sorted_chapters = sorted(chapters, key=lambda item: _int(item.get("index"), 0))
        chapter_total = len(sorted_chapters)

        for offset, chapter in enumerate(sorted_chapters, start=1):
            _report_progress(on_progress, "chapter_processing", chapter, offset, chapter_total, offset - 1, snapshot)
            updates = self.merger.merge(normalized_title, chapter, snapshot)
            snapshot = apply_story_element_updates(snapshot, updates, chapter)
            _report_progress(on_progress, "chapter_completed", chapter, offset, chapter_total, offset, snapshot)

        _report_progress(on_progress, "finished", None, chapter_total, chapter_total, chapter_total, snapshot)
        return {
            "title": normalized_title,
            "characters": snapshot["characters"],
            "locations": snapshot["locations"],
            "events": snapshot["events"],
        }


def _report_progress(
    callback: ProgressCallback | None,
    phase: str,
    chapter: Mapping[str, Any] | None,
    chapter_index: int,
    chapter_total: int,
    completed_chapters: int,
    snapshot: Mapping[str, list[dict[str, Any]]],
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
            "character_count": len(snapshot["characters"]),
            "location_count": len(snapshot["locations"]),
            "event_count": len(snapshot["events"]),
            "message": _progress_message(phase, chapter_index, chapter_total, current_title),
        }
    )


def _progress_message(phase: str, chapter_index: int, chapter_total: int, chapter_title: str) -> str:
    if phase == "chapter_processing":
        title = f"《{chapter_title}》" if chapter_title else f"第 {chapter_index} 章"
        return f"正在抽取 {title} 的角色、地点和事件：{chapter_index}/{chapter_total}"
    if phase == "chapter_completed":
        return f"第 {chapter_index}/{chapter_total} 章故事元素已合并"
    return "故事元素抽取完成"


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
