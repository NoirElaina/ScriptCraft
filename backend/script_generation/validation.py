from collections.abc import Mapping, Sequence
import re
from typing import Any

import yaml

from llm.base import LLMResponseError, parse_yaml_content


def normalize_script_yaml_content(content: Any) -> str:
    payload, normalized_yaml = parse_yaml_content(content)
    validate_script_yaml_payload(payload)
    return normalized_yaml


def normalize_script_yaml_payload(payload: Mapping[str, Any]) -> str:
    validate_script_yaml_payload(payload)
    return yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False)


def validate_script_yaml_fragment(
    payload: Mapping[str, Any],
    *,
    title: str,
    chapter_count: int,
    characters: Sequence[Mapping[str, Any]],
    locations: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> None:
    required_keys = ("scenes", "storyboard")
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise LLMResponseError(f"章节 YAML 片段缺少字段：{', '.join(missing)}")

    full_payload = {
        "schema_version": "2.0",
        "title": title,
        "metadata": {
            "source_title": title,
            "chapters_count": chapter_count,
            "adaptation_style": "长篇章节流式改编",
            "language": "zh-CN",
        },
        "characters": list(characters),
        "locations": list(locations),
        "events": list(events),
        "scenes": payload["scenes"],
        "storyboard": payload["storyboard"],
    }
    validate_script_yaml_payload(full_payload)


def validate_script_yaml_payload(payload: Mapping[str, Any]) -> None:
    required_keys = ("schema_version", "title", "metadata", "characters", "locations", "events", "scenes", "storyboard")
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise LLMResponseError(f"AI 剧本 YAML 缺少字段：{', '.join(missing)}")
    if str(payload.get("schema_version", "")).strip() != "2.0":
        raise LLMResponseError("AI 剧本 YAML 的 schema_version 必须是 2.0")
    if not isinstance(payload.get("scenes"), list) or not payload["scenes"]:
        raise LLMResponseError("AI 剧本 YAML 必须包含 scenes")

    character_ids = _collect_unique_ids(payload.get("characters"), "character")
    location_ids = _collect_unique_ids(payload.get("locations"), "location")
    event_ids = _collect_unique_ids(payload.get("events"), "event")
    character_labels = _id_labels(payload.get("characters"), _character_label)
    location_labels = _id_labels(payload.get("locations"), _named_item_label)
    event_labels = _id_labels(payload.get("events"), _event_label)
    narrator_character_ids = _narrator_character_ids(payload.get("characters"))
    if narrator_character_ids:
        raise LLMResponseError(
            f"characters 包含旁白类角色：{_labels_for_ids(narrator_character_ids, character_labels)}；旁白必须使用 narration 类型，不进入 characters"
        )
    scene_ids: set[str] = set()
    scene_beat_ids: dict[str, set[str]] = {}

    for index, scene in enumerate(payload["scenes"], start=1):
        if not isinstance(scene, Mapping):
            raise LLMResponseError(f"第 {index} 个 scene 不是对象")
        scene_id = _required_text(scene, "id", f"第 {index} 个 scene")
        if scene_id in scene_ids:
            raise LLMResponseError(f"scene.id 重复：{scene_id}")
        scene_ids.add(scene_id)

        location_id = _required_text(scene, "location_id", scene_id)
        if location_id not in location_ids:
            raise LLMResponseError(f"{scene_id} 引用了不存在的 location_id：{_label_id(location_id, location_labels)}")

        for character_id in _string_list(scene.get("characters")):
            if character_id not in character_ids:
                raise LLMResponseError(f"{scene_id} 引用了不存在的角色：{_label_id(character_id, character_labels)}")
            if character_id in narrator_character_ids:
                raise LLMResponseError(f"{scene_id} 把旁白作为角色引用：{_label_id(character_id, character_labels)}；旁白必须使用 narration 类型，不进入 scene.characters")

        for event_id in _string_list(scene.get("source_events")):
            if event_id not in event_ids:
                raise LLMResponseError(f"{scene_id} 引用了不存在的事件：{_label_id(event_id, event_labels)}")

        if not isinstance(scene.get("beats"), list) or not scene["beats"]:
            raise LLMResponseError(f"第 {index} 个 scene 缺少 beats")
        beat_ids: set[str] = set()
        for beat_index, beat in enumerate(scene["beats"], start=1):
            if not isinstance(beat, Mapping):
                raise LLMResponseError(f"{scene_id} 的第 {beat_index} 个 beat 不是对象")
            beat_id = _required_text(beat, "id", f"{scene_id} 的第 {beat_index} 个 beat")
            if beat_id in beat_ids:
                raise LLMResponseError(f"{scene_id} 的 beat.id 重复：{beat_id}")
            beat_ids.add(beat_id)
            beat_type = _required_text(beat, "type", beat_id)
            _required_text(beat, "content", beat_id)
            if beat_type == "dialogue":
                speaker_id = _required_text(beat, "speaker_id", beat_id)
                if speaker_id not in character_ids:
                    raise LLMResponseError(f"{beat_id} 引用了不存在的 speaker_id：{_label_id(speaker_id, character_labels)}")
                if speaker_id in narrator_character_ids:
                    raise LLMResponseError(f"{beat_id} 把旁白作为 dialogue.speaker_id：{_label_id(speaker_id, character_labels)}；旁白必须使用 narration 类型")
        scene_beat_ids[scene_id] = beat_ids

    storyboard = payload.get("storyboard")
    if not isinstance(storyboard, Mapping):
        raise LLMResponseError("storyboard 必须是对象")
    storyboard_scenes = storyboard.get("scenes")
    if not isinstance(storyboard_scenes, list) or not storyboard_scenes:
        raise LLMResponseError("storyboard.scenes 必须是非空数组")

    storyboard_scene_ids: set[str] = set()
    for index, storyboard_scene in enumerate(storyboard_scenes, start=1):
        if not isinstance(storyboard_scene, Mapping):
            raise LLMResponseError(f"第 {index} 个 storyboard scene 不是对象")
        scene_id = _required_text(storyboard_scene, "scene_id", f"第 {index} 个 storyboard scene")
        if scene_id not in scene_ids:
            raise LLMResponseError(f"storyboard 引用了不存在的 scene_id：{scene_id}")
        if scene_id in storyboard_scene_ids:
            raise LLMResponseError(f"storyboard.scene_id 重复：{scene_id}")
        storyboard_scene_ids.add(scene_id)

        if not isinstance(storyboard_scene.get("setting"), Mapping):
            raise LLMResponseError(f"{scene_id} 缺少 storyboard.setting")

        cast = storyboard_scene.get("cast")
        if not isinstance(cast, list):
            raise LLMResponseError(f"{scene_id} 的 storyboard.cast 必须是数组")
        cast_ids: set[str] = set()
        for cast_index, member in enumerate(cast, start=1):
            if not isinstance(member, Mapping):
                raise LLMResponseError(f"{scene_id} 的第 {cast_index} 个 cast 不是对象")
            character_id = _required_text(member, "character_id", f"{scene_id} cast[{cast_index}]")
            if character_id not in character_ids:
                raise LLMResponseError(f"{scene_id} 的 cast 引用了不存在的角色：{_label_id(character_id, character_labels)}")
            if character_id in narrator_character_ids:
                raise LLMResponseError(f"{scene_id} 的 cast 包含旁白角色：{_label_id(character_id, character_labels)}；旁白不进入 storyboard.cast")
            position = _required_text(member, "position", f"{scene_id} cast[{cast_index}]")
            if position.startswith("offscreen"):
                raise LLMResponseError(f"{scene_id} 的 cast.position 不能使用场外位置：{position}")
            cast_ids.add(character_id)

        timeline = storyboard_scene.get("timeline")
        if not isinstance(timeline, list) or not timeline:
            raise LLMResponseError(f"{scene_id} 缺少 storyboard.timeline")
        for shot_index, shot in enumerate(timeline, start=1):
            if not isinstance(shot, Mapping):
                raise LLMResponseError(f"{scene_id} 的第 {shot_index} 个 shot 不是对象")
            shot_id = _required_text(shot, "id", f"{scene_id} shot[{shot_index}]")
            shot_type = _required_text(shot, "type", shot_id)
            source_beat_id = _required_text(shot, "source_beat_id", shot_id)
            if source_beat_id not in scene_beat_ids[scene_id]:
                raise LLMResponseError(f"{shot_id} 引用了不存在的 source_beat_id：{source_beat_id}")
            if not _is_positive_number(shot.get("duration_ms")):
                raise LLMResponseError(f"{shot_id} 的 duration_ms 必须大于 0")
            if not isinstance(shot.get("camera"), Mapping):
                raise LLMResponseError(f"{shot_id} 缺少 camera")
            actions = shot.get("actions")
            if not isinstance(actions, list):
                raise LLMResponseError(f"{shot_id} 的 actions 必须是数组")
            if shot_type == "action" and not actions and not shot.get("effects") and not shot.get("props"):
                raise LLMResponseError(f"{shot_id} 是 action 类型，必须包含 actions、effects 或 props")
            for action_index, action in enumerate(actions, start=1):
                if not isinstance(action, Mapping):
                    raise LLMResponseError(f"{shot_id} 的第 {action_index} 个 action 不是对象")
                actor_id = _required_text(action, "actor", f"{shot_id} action[{action_index}]")
                if actor_id not in character_ids:
                    raise LLMResponseError(f"{shot_id} 的 action 引用了不存在的角色：{_label_id(actor_id, character_labels)}")
                if actor_id in narrator_character_ids:
                    raise LLMResponseError(f"{shot_id} 的 action 把旁白作为 actor：{_label_id(actor_id, character_labels)}；旁白必须使用 narration 类型")
                if actor_id not in cast_ids:
                    raise LLMResponseError(
                        f"{shot_id} 的 action 角色未出现在 cast 中：{_label_id(actor_id, character_labels)}；"
                        f"当前 cast：{_labels_for_ids(cast_ids, character_labels)}。请把该角色加入当前 storyboard scene.cast 并分配站位"
                    )
            if shot_type == "dialogue":
                dialogue = shot.get("dialogue")
                if not isinstance(dialogue, Mapping):
                    raise LLMResponseError(f"{shot_id} 是 dialogue 类型，必须包含 dialogue")
                speaker_id = _required_text(dialogue, "speaker_id", f"{shot_id}.dialogue")
                _required_text(dialogue, "text", f"{shot_id}.dialogue")
                if speaker_id not in character_ids:
                    raise LLMResponseError(f"{shot_id} 的 dialogue 引用了不存在的角色：{_label_id(speaker_id, character_labels)}")
                if speaker_id in narrator_character_ids:
                    raise LLMResponseError(f"{shot_id} 的 dialogue 把旁白作为 speaker_id：{_label_id(speaker_id, character_labels)}；旁白必须使用 narration 类型，不进入主场景")
                if speaker_id not in cast_ids:
                    raise LLMResponseError(
                        f"{shot_id} 的 dialogue 角色未出现在 cast 中：{_label_id(speaker_id, character_labels)}；"
                        f"当前 cast：{_labels_for_ids(cast_ids, character_labels)}。请把该角色加入当前 storyboard scene.cast 并分配站位"
                    )

    missing_storyboard_scenes = sorted(scene_ids - storyboard_scene_ids)
    if missing_storyboard_scenes:
        raise LLMResponseError(f"storyboard 缺少场景调度：{', '.join(missing_storyboard_scenes)}")


def _collect_unique_ids(value: Any, label: str) -> set[str]:
    if not isinstance(value, list):
        raise LLMResponseError(f"{label}s 必须是数组")

    ids: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping):
            raise LLMResponseError(f"第 {index} 个 {label} 不是对象")
        item_id = _required_text(item, "id", f"第 {index} 个 {label}")
        if item_id in ids:
            raise LLMResponseError(f"{label}.id 重复：{item_id}")
        ids.add(item_id)
    return ids


def _id_labels(value: Any, labeler) -> dict[str, str]:
    if not isinstance(value, list):
        return {}
    labels: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("id", "")).strip()
        if item_id:
            labels[item_id] = labeler(item)
    return labels


def _narrator_character_ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    ids: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("id", "")).strip()
        if item_id and _is_narrator_character(item):
            ids.add(item_id)
    return ids


def _is_narrator_character(item: Mapping[str, Any]) -> bool:
    aliases = item.get("aliases")
    alias_text = " ".join(str(alias) for alias in aliases) if isinstance(aliases, list) else ""
    text = " ".join(
        str(value)
        for value in [
            item.get("name", ""),
            item.get("role", ""),
            item.get("description", ""),
            alias_text,
        ]
    )
    return bool(re.search(r"旁白|叙述者|画外音|narrator", text, re.IGNORECASE))


def _character_label(item: Mapping[str, Any]) -> str:
    item_id = str(item.get("id", "")).strip()
    name = str(item.get("name", "")).strip()
    role = str(item.get("role", "")).strip()
    aliases = [str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip()] if isinstance(item.get("aliases"), list) else []
    details = [value for value in [name, f"别名：{'、'.join(aliases)}" if aliases else "", role] if value]
    return f"{item_id}（{' / '.join(details)}）" if details else item_id


def _named_item_label(item: Mapping[str, Any]) -> str:
    item_id = str(item.get("id", "")).strip()
    name = str(item.get("name", "")).strip()
    return f"{item_id}（{name}）" if name else item_id


def _event_label(item: Mapping[str, Any]) -> str:
    item_id = str(item.get("id", "")).strip()
    summary = str(item.get("summary", "")).strip()
    if len(summary) > 36:
        summary = f"{summary[:36]}..."
    return f"{item_id}（{summary}）" if summary else item_id


def _label_id(item_id: str, labels: Mapping[str, str]) -> str:
    normalized_id = str(item_id or "").strip()
    return labels.get(normalized_id, normalized_id or "空")


def _labels_for_ids(item_ids: set[str], labels: Mapping[str, str]) -> str:
    if not item_ids:
        return "空"
    return "、".join(_label_id(item_id, labels) for item_id in sorted(item_ids))


def _required_text(value: Mapping[str, Any], key: str, owner: str) -> str:
    text = str(value.get(key, "")).strip()
    if not text:
        raise LLMResponseError(f"{owner} 缺少 {key}")
    return text


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_positive_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return value > 0
    return False
