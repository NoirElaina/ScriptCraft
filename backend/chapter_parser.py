import re
from dataclasses import dataclass


class ChapterParseError(ValueError):
    pass


@dataclass(frozen=True)
class Chapter:
    id: str
    index: int
    heading: str
    title: str
    content: str


CHAPTER_HEADING_PATTERN = re.compile(
    r"^\s*(?P<heading>("
    r"第[0-9一二三四五六七八九十百千万]+[章节回部卷集]"
    r"|Chapter\s+[0-9]+"
    r"))\s*(?P<title>.*)$",
    re.IGNORECASE,
)


class ChapterParser:
    def parse(self, text: str) -> list[Chapter]:
        normalized_text = text.strip()
        if not normalized_text:
            raise ChapterParseError("小说文本不能为空")

        headings = self._find_headings(normalized_text)
        if len(headings) < 3:
            raise ChapterParseError("至少需要 3 个章节")

        chapters: list[Chapter] = []
        for index, (line_start, content_start, heading, title) in enumerate(headings, start=1):
            next_line_start = headings[index][0] if index < len(headings) else len(normalized_text)
            content = normalized_text[content_start:next_line_start].strip()
            chapters.append(
                Chapter(
                    id=f"chapter_{index:03d}",
                    index=index,
                    heading=heading.strip(),
                    title=title.strip() or heading.strip(),
                    content=content,
                )
            )

        return chapters

    def _find_headings(self, text: str) -> list[tuple[int, int, str, str]]:
        headings: list[tuple[int, int, str, str]] = []
        cursor = 0
        for line in text.splitlines(keepends=True):
            stripped_line = line.strip()
            match = CHAPTER_HEADING_PATTERN.match(stripped_line)
            if match:
                line_start = cursor
                content_start = cursor + len(line)
                headings.append(
                    (
                        line_start,
                        content_start,
                        match.group("heading"),
                        match.group("title"),
                    )
                )
            cursor += len(line)
        return headings
