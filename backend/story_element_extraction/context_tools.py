import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from llm.streaming import StreamCallback, emit_tool_event


class ReadCurrentChapterInput(BaseModel):
    include_content: bool = Field(default=True, description="是否返回当前章节正文")
    include_analysis: bool = Field(default=True, description="是否返回章节分析结果")


class SearchProjectChaptersInput(BaseModel):
    query: str = Field(description="要查找的人名、地点、事件关键词或原文片段")
    limit: int = Field(default=5, ge=1, le=8, description="最多返回的章节数量")


@dataclass
class ChapterContextTools:
    current_chapter: Mapping[str, Any]
    project_chapters: Sequence[Mapping[str, Any]]
    on_stream: StreamCallback | None = None

    def read_current_chapter(self, include_content: bool = True, include_analysis: bool = True) -> str:
        emit_tool_event(
            self.on_stream,
            node="story_cards",
            title="读取当前章节",
            content=f"读取《{self.current_chapter.get('title') or self.current_chapter.get('heading') or ''}》。",
        )
        return _json(
            {
                "ok": True,
                "chapter": _chapter_payload(
                    self.current_chapter,
                    include_content=include_content,
                    include_analysis=include_analysis,
                ),
            }
        )

    def search_project_chapters(self, query: str, limit: int = 5) -> str:
        keyword = str(query or "").strip()
        if not keyword:
            emit_tool_event(self.on_stream, node="story_cards", title="搜索章节失败", content="query 不能为空", event_type="tool_error")
            return _json({"ok": False, "error": "query 不能为空"})

        matches: list[dict[str, Any]] = []
        for chapter in self.project_chapters:
            score = _chapter_score(chapter, keyword)
            if score <= 0:
                continue
            matches.append(
                {
                    "score": score,
                    "chapter": _chapter_payload(chapter, include_content=False, include_analysis=True),
                    "evidence": _chapter_evidence(chapter, keyword),
                }
            )

        matches.sort(key=lambda item: (-item["score"], _int(item["chapter"].get("index"), 0)))
        emit_tool_event(
            self.on_stream,
            node="story_cards",
            title="搜索项目章节",
            content=f"关键词“{keyword}”命中 {len(matches[:limit])} 个章节。",
        )
        return _json({"ok": True, "query": keyword, "matches": matches[:limit]})


def _chapter_payload(
    chapter: Mapping[str, Any],
    *,
    include_content: bool,
    include_analysis: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": chapter.get("id", ""),
        "index": chapter.get("index", 0),
        "heading": chapter.get("heading", ""),
        "title": chapter.get("title", ""),
        "summary": chapter.get("summary", ""),
    }
    if include_content:
        payload["content"] = chapter.get("content", "")
    if include_analysis:
        payload["analysis"] = chapter.get("analysis", {})
    return payload


def _chapter_score(chapter: Mapping[str, Any], keyword: str) -> int:
    score = 0
    for key, weight in (("title", 8), ("heading", 6), ("summary", 4), ("content", 2)):
        text = str(chapter.get(key, ""))
        if keyword in text:
            score += weight + text.count(keyword)

    analysis_text = json.dumps(chapter.get("analysis", {}), ensure_ascii=False)
    if keyword in analysis_text:
        score += 3 + analysis_text.count(keyword)
    return score


def _chapter_evidence(chapter: Mapping[str, Any], keyword: str) -> list[str]:
    evidence: list[str] = []
    for text in (
        str(chapter.get("summary", "")),
        str(chapter.get("content", "")),
        json.dumps(chapter.get("analysis", {}), ensure_ascii=False),
    ):
        snippet = _snippet(text, keyword)
        if snippet and snippet not in evidence:
            evidence.append(snippet)
        if len(evidence) >= 3:
            break
    return evidence


def _snippet(text: str, keyword: str) -> str:
    index = text.find(keyword)
    if index < 0:
        return ""
    start = max(0, index - 60)
    end = min(len(text), index + len(keyword) + 80)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
