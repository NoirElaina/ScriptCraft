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
    r"第(?P<cn_index>[0-9一二三四五六七八九十百千万]+)[章节回部卷集]"
    r"|Chapter\s+(?P<en_index>[0-9]+)"
    r"))\s*(?P<title>.*)$",
    re.IGNORECASE,
)


class ChapterParser:
    def parse(self, text: str) -> list[Chapter]:
        normalized_text = text.strip()
        if not normalized_text:
            raise ChapterParseError("小说文本不能为空")

        headings = self._find_headings(normalized_text)
        if not headings:
            return [
                Chapter(
                    id="chapter_001",
                    index=1,
                    heading="第1章",
                    title="未命名章节",
                    content=normalized_text,
                )
            ]

        chapters: list[Chapter] = []
        used_indexes: set[int] = set()
        for fallback_index, (line_start, content_start, heading, title, parsed_index) in enumerate(headings, start=1):
            chapter_index = _unique_chapter_index(parsed_index or fallback_index, used_indexes)
            next_line_start = headings[fallback_index][0] if fallback_index < len(headings) else len(normalized_text)
            content = normalized_text[content_start:next_line_start].strip()
            chapters.append(
                Chapter(
                    id=f"chapter_{chapter_index:03d}",
                    index=chapter_index,
                    heading=heading.strip(),
                    title=title.strip() or heading.strip(),
                    content=content,
                )
            )

        return chapters

    def _find_headings(self, text: str) -> list[tuple[int, int, str, str, int]]:
        headings: list[tuple[int, int, str, str, int]] = []
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
                        _parse_chapter_index(match.group("cn_index") or match.group("en_index") or ""),
                    )
                )
            cursor += len(line)
        return headings


def _unique_chapter_index(preferred_index: int, used_indexes: set[int]) -> int:
    chapter_index = max(1, preferred_index)
    while chapter_index in used_indexes:
        chapter_index += 1
    used_indexes.add(chapter_index)
    return chapter_index


def _parse_chapter_index(value: str) -> int:
    text = value.strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return _parse_chinese_number(text)


def parse_chapter_heading_index(heading: str) -> int:
    match = CHAPTER_HEADING_PATTERN.match(heading.strip())
    if not match:
        return 0
    return _parse_chapter_index(match.group("cn_index") or match.group("en_index") or "")


def _parse_chinese_number(text: str) -> int:
    digits = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    section = 0
    number = 0

    for char in text:
        if char in digits:
            number = digits[char]
            continue
        unit = units.get(char)
        if unit is None:
            return 0
        if unit == 10000:
            section = (section + number) * unit
            total += section
            section = 0
        else:
            section += (number or 1) * unit
        number = 0

    return total + section + number
