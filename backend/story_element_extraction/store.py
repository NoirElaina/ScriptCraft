from collections.abc import Mapping
from typing import Any

from llm.base import LLMResponseError


def empty_story_element_snapshot() -> dict[str, list[dict[str, Any]]]:
    return {"characters": [], "locations": [], "events": []}


def apply_story_element_updates(
    snapshot: Mapping[str, Any],
    updates: Mapping[str, Any],
    chapter: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    next_snapshot = {
        "characters": [dict(item) for item in _object_list(snapshot.get("characters"))],
        "locations": [dict(item) for item in _object_list(snapshot.get("locations"))],
        "events": [dict(item) for item in _object_list(snapshot.get("events"))],
    }

    for update in _object_list(updates.get("character_updates")):
        _apply_character_update(next_snapshot, update)
    for update in _object_list(updates.get("location_updates")):
        _apply_location_update(next_snapshot, update)
    for update in _object_list(updates.get("event_updates")):
        _apply_event_update(next_snapshot, update, chapter)

    return next_snapshot


def _apply_character_update(snapshot: dict[str, list[dict[str, Any]]], update: Mapping[str, Any]) -> None:
    action = _required_text(update, "action", "character_update")
    if action == "create":
        snapshot["characters"].append(
            {
                "id": _next_id(snapshot["characters"], "char"),
                "name": _required_text(update, "name", "character_update"),
                "aliases": _string_list(update.get("aliases")),
                "role": _required_text(update, "role", "character_update"),
                "description": _required_text(update, "description", "character_update"),
                "motivation": _required_text(update, "motivation", "character_update"),
            }
        )
        return

    if action == "merge":
        character = _find_by_id(snapshot["characters"], _required_text(update, "target_id", "character_update"))
        character["aliases"] = _unique_strings(
            [
                *character.get("aliases", []),
                *_string_list(update.get("aliases")),
                *_string_list(update.get("new_aliases")),
            ]
        )
        character["role"] = _string(update.get("role"), character.get("role", "supporting"))
        character["description"] = _merge_text(
            character.get("description", ""),
            _string(update.get("description_patch"), _string(update.get("description"), "")),
        )
        character["motivation"] = _merge_text(
            character.get("motivation", ""),
            _string(update.get("motivation_patch"), _string(update.get("motivation"), "")),
        )
        return

    raise LLMResponseError(f"未知角色更新动作：{action}")


def _apply_location_update(snapshot: dict[str, list[dict[str, Any]]], update: Mapping[str, Any]) -> None:
    action = _required_text(update, "action", "location_update")
    if action == "create":
        snapshot["locations"].append(
            {
                "id": _next_id(snapshot["locations"], "loc"),
                "name": _required_text(update, "name", "location_update"),
                "description": _required_text(update, "description", "location_update"),
            }
        )
        return

    if action == "merge":
        location = _find_by_id(snapshot["locations"], _required_text(update, "target_id", "location_update"))
        location["description"] = _merge_text(
            location.get("description", ""),
            _string(update.get("description_patch"), _string(update.get("description"), "")),
        )
        return

    raise LLMResponseError(f"未知地点更新动作：{action}")


def _apply_event_update(
    snapshot: dict[str, list[dict[str, Any]]],
    update: Mapping[str, Any],
    chapter: Mapping[str, Any],
) -> None:
    action = _required_text(update, "action", "event_update")
    if action == "create":
        source_chapter = _required_text(update, "source_chapter", "event_update")
        chapter_id = _required_text(chapter, "id", "当前章节")
        if source_chapter != chapter_id:
            raise LLMResponseError(f"事件 source_chapter 必须是当前章节：{chapter_id}")
        snapshot["events"].append(
            {
                "id": _next_id(snapshot["events"], "event"),
                "source_chapter": source_chapter,
                "summary": _required_text(update, "summary", "event_update"),
                "involved_characters": _resolve_character_refs(snapshot["characters"], update.get("involved_characters")),
            }
        )
        return

    if action == "merge":
        event = _find_by_id(snapshot["events"], _required_text(update, "target_id", "event_update"))
        event["summary"] = _merge_text(event.get("summary", ""), _string(update.get("summary_patch"), _string(update.get("summary"), "")))
        if "involved_characters" in update:
            event["involved_characters"] = _unique_strings(
                [
                    *event.get("involved_characters", []),
                    *_resolve_character_refs(snapshot["characters"], update.get("involved_characters")),
                ]
            )
        return

    raise LLMResponseError(f"未知事件更新动作：{action}")


def _resolve_character_refs(characters: list[dict[str, Any]], refs: Any) -> list[str]:
    resolved: list[str] = []
    for ref in _string_list(refs):
        character_id = _match_character_ref(characters, ref)
        if not character_id:
            raise LLMResponseError(f"事件引用了未知角色：{ref}")
        resolved.append(character_id)
    return _unique_strings(resolved)


def _match_character_ref(characters: list[dict[str, Any]], ref: str) -> str:
    for character in characters:
        if ref == character.get("id"):
            return str(character["id"])
        if ref == character.get("name"):
            return str(character["id"])
        if ref in _string_list(character.get("aliases")):
            return str(character["id"])
    return ""


def _find_by_id(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise LLMResponseError(f"更新引用了不存在的 ID：{item_id}")


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


def _object_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _required_text(value: Mapping[str, Any], key: str, owner: str) -> str:
    text = _string(value.get(key), "")
    if not text:
        raise LLMResponseError(f"{owner} 缺少 {key}")
    return text


def _string(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
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
