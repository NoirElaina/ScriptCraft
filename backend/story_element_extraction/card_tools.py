import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from llm.base import LLMResponseError
from llm.streaming import StreamCallback, emit_tool_event


class ReadStoryCardsInput(BaseModel):
    target: Literal["all", "characters", "locations", "events", "scenes"] = Field(
        default="all",
        description="要读取的卡片范围",
    )


class ValidateStoryCardsInput(BaseModel):
    include_cards: bool = Field(default=False, description="是否同时返回当前卡片库")


class UpsertCharacterCardInput(BaseModel):
    name: str = Field(description="角色姓名或稳定称呼")
    aliases: list[str] = Field(default_factory=list, description="角色别名")
    role: str = Field(description="角色身份或叙事功能")
    description: str = Field(description="角色当前已知设定")
    motivation: str = Field(default="", description="角色动机或阶段性目标")
    source_chapter: str = Field(description="证据来源章节 ID")
    evidence: str = Field(default="", description="来自当前章节的依据")
    target_id: str | None = Field(default=None, description="已有角色 ID；为空时按姓名/别名匹配或创建")


class UpsertLocationCardInput(BaseModel):
    name: str = Field(description="地点名称")
    description: str = Field(description="地点当前已知设定")
    source_chapter: str = Field(description="证据来源章节 ID")
    evidence: str = Field(default="", description="来自当前章节的依据")
    target_id: str | None = Field(default=None, description="已有地点 ID；为空时按名称匹配或创建")


class UpsertEventCardInput(BaseModel):
    summary: str = Field(description="事件摘要")
    source_chapter: str = Field(description="事件所属章节 ID")
    involved_characters: list[str] = Field(default_factory=list, description="参与角色的 ID、姓名或别名")
    evidence: str = Field(default="", description="来自当前章节的依据")
    target_id: str | None = Field(default=None, description="已有事件 ID；为空时创建新事件")


class UpsertSceneCardInput(BaseModel):
    title: str = Field(description="场景标题")
    source_chapter: str = Field(description="场景所属章节 ID")
    location: str = Field(description="地点 ID 或地点名称")
    characters: list[str] = Field(default_factory=list, description="出场角色的 ID、姓名或别名")
    summary: str = Field(description="场景摘要")
    dramatic_purpose: str = Field(description="场景在剧本中的戏剧作用")
    key_beats: list[str] = Field(default_factory=list, description="场景关键节拍")
    source_events: list[str] = Field(default_factory=list, description="关联事件 ID")
    time_of_day: str = Field(default="unknown", description="day/night/dusk/dawn/unknown")
    target_id: str | None = Field(default=None, description="已有场景 ID；为空时按章节和标题匹配或创建")


@dataclass
class StoryCardStore:
    snapshot: dict[str, list[dict[str, Any]]]
    operations: list[dict[str, Any]]
    on_stream: StreamCallback | None = None

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any], on_stream: StreamCallback | None = None) -> "StoryCardStore":
        return cls(
            snapshot={
                "characters": [dict(item) for item in _object_list(snapshot.get("characters"))],
                "locations": [dict(item) for item in _object_list(snapshot.get("locations"))],
                "events": [dict(item) for item in _object_list(snapshot.get("events"))],
                "scenes": [dict(item) for item in _object_list(snapshot.get("scenes"))],
            },
            operations=[],
            on_stream=on_stream,
        )

    def read_story_cards(self, target: str = "all") -> str:
        self._emit("读取故事卡片", f"读取范围：{target}")
        if target == "all":
            return _json({"cards": self.snapshot})
        if target not in self.snapshot:
            return _json({"ok": False, "error": f"未知卡片范围：{target}"})
        return _json({"cards": self.snapshot[target]})

    def validate_story_cards(self, include_cards: bool = False) -> str:
        errors = self.validate_snapshot()
        self._emit("校验故事卡片", "校验通过" if not errors else "发现引用问题：" + "；".join(errors[:3]))
        payload: dict[str, Any] = {"ok": not errors, "errors": errors}
        if include_cards:
            payload["cards"] = self.snapshot
        return _json(payload)

    def upsert_character_card(
        self,
        name: str,
        aliases: list[str],
        role: str,
        description: str,
        motivation: str,
        source_chapter: str,
        evidence: str = "",
        target_id: str | None = None,
    ) -> str:
        card = self._find_character(target_id or name)
        operation = "update"
        if card is None:
            operation = "create"
            card = {
                "id": _next_id(self.snapshot["characters"], "char"),
                "name": _required(name, "name"),
                "aliases": [],
                "role": "",
                "description": "",
                "motivation": "",
                "source_chapters": [],
                "evidence": [],
            }
            self.snapshot["characters"].append(card)

        card["aliases"] = _unique([*card.get("aliases", []), *aliases])
        card["role"] = _merge_text(card.get("role", ""), role)
        card["description"] = _merge_text(card.get("description", ""), description)
        card["motivation"] = _merge_text(card.get("motivation", ""), motivation)
        card["source_chapters"] = _unique([*card.get("source_chapters", []), source_chapter])
        if evidence:
            card["evidence"] = _unique([*card.get("evidence", []), evidence])

        self.operations.append({"tool": "upsert_character_card", "operation": operation, "id": card["id"]})
        self._emit("写入角色卡", f"{operation} {card['id']}：{card.get('name', '')}")
        return _json({"ok": True, "operation": operation, "card": card})

    def upsert_location_card(
        self,
        name: str,
        description: str,
        source_chapter: str,
        evidence: str = "",
        target_id: str | None = None,
    ) -> str:
        card = self._find_location(target_id or name)
        operation = "update"
        if card is None:
            operation = "create"
            card = {
                "id": _next_id(self.snapshot["locations"], "loc"),
                "name": _required(name, "name"),
                "description": "",
                "source_chapters": [],
                "evidence": [],
            }
            self.snapshot["locations"].append(card)

        card["description"] = _merge_text(card.get("description", ""), description)
        card["source_chapters"] = _unique([*card.get("source_chapters", []), source_chapter])
        if evidence:
            card["evidence"] = _unique([*card.get("evidence", []), evidence])

        self.operations.append({"tool": "upsert_location_card", "operation": operation, "id": card["id"]})
        self._emit("写入地点卡", f"{operation} {card['id']}：{card.get('name', '')}")
        return _json({"ok": True, "operation": operation, "card": card})

    def upsert_event_card(
        self,
        summary: str,
        source_chapter: str,
        involved_characters: list[str],
        evidence: str = "",
        target_id: str | None = None,
    ) -> str:
        try:
            resolved_characters = self._resolve_character_refs(involved_characters)
            card = self._find_by_id("events", target_id) if target_id else None
            operation = "update"
            if card is None:
                operation = "create"
                card = {
                    "id": _next_id(self.snapshot["events"], "event"),
                    "source_chapter": _required(source_chapter, "source_chapter"),
                    "summary": "",
                    "involved_characters": [],
                    "evidence": [],
                }
                self.snapshot["events"].append(card)

            card["summary"] = _merge_text(card.get("summary", ""), summary)
            card["source_chapter"] = source_chapter
            card["involved_characters"] = _unique(
                [*card.get("involved_characters", []), *resolved_characters]
            )
            if evidence:
                card["evidence"] = _unique([*card.get("evidence", []), evidence])
        except LLMResponseError as exc:
            self._emit("事件卡写入失败", str(exc), event_type="tool_error")
            return _tool_error(exc, "请先读取角色卡；如果这是新角色，先调用 upsert_character_card 创建角色卡，再重新写入事件。")

        self.operations.append({"tool": "upsert_event_card", "operation": operation, "id": card["id"]})
        self._emit("写入事件卡", f"{operation} {card['id']}：{card.get('summary', '')}")
        return _json({"ok": True, "operation": operation, "card": card})

    def upsert_scene_card(
        self,
        title: str,
        source_chapter: str,
        location: str,
        characters: list[str],
        summary: str,
        dramatic_purpose: str,
        key_beats: list[str],
        source_events: list[str],
        time_of_day: str = "unknown",
        target_id: str | None = None,
    ) -> str:
        try:
            location_card = self._find_location(location)
            if location_card is None:
                raise LLMResponseError(f"场景引用了未知地点：{location}")
            resolved_characters = self._resolve_character_refs(characters)
            resolved_events = self._resolve_event_refs(source_events)
            card = self._find_by_id("scenes", target_id) if target_id else self._find_scene(source_chapter, title)
            operation = "update"
            if card is None:
                operation = "create"
                card = {
                    "id": _next_id(self.snapshot["scenes"], "scene_card"),
                    "title": _required(title, "title"),
                    "source_chapter": _required(source_chapter, "source_chapter"),
                    "location_id": "",
                    "characters": [],
                    "source_events": [],
                    "summary": "",
                    "dramatic_purpose": "",
                    "key_beats": [],
                    "time_of_day": "unknown",
                }
                self.snapshot["scenes"].append(card)

            card["location_id"] = location_card["id"]
            card["characters"] = _unique([*card.get("characters", []), *resolved_characters])
            card["source_events"] = _unique([*card.get("source_events", []), *resolved_events])
            card["summary"] = _merge_text(card.get("summary", ""), summary)
            card["dramatic_purpose"] = _merge_text(card.get("dramatic_purpose", ""), dramatic_purpose)
            card["key_beats"] = _unique([*card.get("key_beats", []), *key_beats])
            card["time_of_day"] = time_of_day.strip() or card.get("time_of_day", "unknown")
        except LLMResponseError as exc:
            self._emit("场景卡写入失败", str(exc), event_type="tool_error")
            return _tool_error(exc, "请先读取卡片；缺角色就创建角色卡，缺地点就创建地点卡，缺事件就先写事件卡，再重新写入场景。")

        self.operations.append({"tool": "upsert_scene_card", "operation": operation, "id": card["id"]})
        self._emit("写入场景卡", f"{operation} {card['id']}：{card.get('title', '')}")
        return _json({"ok": True, "operation": operation, "card": card})

    def validate_snapshot(self) -> list[str]:
        errors: list[str] = []
        character_ids = {str(card.get("id", "")) for card in self.snapshot["characters"]}
        location_ids = {str(card.get("id", "")) for card in self.snapshot["locations"]}
        event_ids = {str(card.get("id", "")) for card in self.snapshot["events"]}

        for event in self.snapshot["events"]:
            event_id = str(event.get("id", ""))
            for character_id in _string_list(event.get("involved_characters")):
                if character_id not in character_ids:
                    errors.append(f"事件 {event_id} 引用了未知角色：{character_id}")

        for scene in self.snapshot["scenes"]:
            scene_id = str(scene.get("id", ""))
            location_id = str(scene.get("location_id", ""))
            if location_id and location_id not in location_ids:
                errors.append(f"场景 {scene_id} 引用了未知地点：{location_id}")
            for character_id in _string_list(scene.get("characters")):
                if character_id not in character_ids:
                    errors.append(f"场景 {scene_id} 引用了未知角色：{character_id}")
            for event_id in _string_list(scene.get("source_events")):
                if event_id not in event_ids:
                    errors.append(f"场景 {scene_id} 引用了未知事件：{event_id}")

        return errors

    def _find_character(self, ref: str | None) -> dict[str, Any] | None:
        if not ref:
            return None
        for card in self.snapshot["characters"]:
            if ref == card.get("id") or ref == card.get("name") or ref in _string_list(card.get("aliases")):
                return card
        return None

    def _find_location(self, ref: str | None) -> dict[str, Any] | None:
        if not ref:
            return None
        for card in self.snapshot["locations"]:
            if ref == card.get("id") or ref == card.get("name"):
                return card
        return None

    def _find_scene(self, source_chapter: str, title: str) -> dict[str, Any] | None:
        for card in self.snapshot["scenes"]:
            if card.get("source_chapter") == source_chapter and card.get("title") == title:
                return card
        return None

    def _find_by_id(self, collection: str, item_id: str | None) -> dict[str, Any] | None:
        if not item_id:
            return None
        for card in self.snapshot[collection]:
            if card.get("id") == item_id:
                return card
        raise LLMResponseError(f"卡片不存在：{item_id}")

    def _resolve_character_refs(self, refs: list[str]) -> list[str]:
        resolved: list[str] = []
        for ref in refs:
            card = self._find_character(ref)
            if card is None:
                raise LLMResponseError(f"引用了未知角色：{ref}")
            resolved.append(str(card["id"]))
        return _unique(resolved)

    def _resolve_event_refs(self, refs: list[str]) -> list[str]:
        resolved: list[str] = []
        for ref in refs:
            card = self._find_by_id("events", ref)
            if card is not None:
                resolved.append(str(card["id"]))
        return _unique(resolved)

    def _emit(self, title: str, content: str, event_type: str = "tool_result") -> None:
        emit_tool_event(self.on_stream, node="story_cards", title=title, content=content, event_type=event_type)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _tool_error(error: LLMResponseError, hint: str) -> str:
    return _json({"ok": False, "error": str(error), "hint": hint})


def _object_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _required(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LLMResponseError(f"卡片缺少 {field}")
    return text


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _merge_text(current: str, patch: str) -> str:
    current = str(current or "").strip()
    patch = str(patch or "").strip()
    if not patch or patch in current:
        return current
    if not current:
        return patch
    return f"{current} {patch}"


def _next_id(items: list[dict[str, Any]], prefix: str) -> str:
    max_index = 0
    for item in items:
        raw_id = str(item.get("id", ""))
        if raw_id.startswith(f"{prefix}_"):
            try:
                max_index = max(max_index, int(raw_id.rsplit("_", 1)[1]))
            except ValueError:
                pass
    return f"{prefix}_{max_index + 1:03d}"
