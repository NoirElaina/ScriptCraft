import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from llm.base import LLMResponseError, parse_yaml_content
from .validation import normalize_script_yaml_payload


REPAIR_LIMIT = 3
TOOL_CALL_LIMIT = 10


class ReadYamlInput(BaseModel):
    target: str = Field(description="YAML 路径或对象 ID，例如 characters、shot_001_001_03、storyboard_scene:scene_001")


class ReadYamlContextInput(BaseModel):
    target: str = Field(description="需要定位上下文的 YAML 对象 ID，例如 shot_001_001_03、beat_001_001_02、scene_001")


class WriteYamlInput(BaseModel):
    target: str = Field(description="YAML 路径或对象 ID，例如 shot_001_001_03、storyboard_scene:scene_001")
    operation: Literal["set_field", "append_to_list", "replace_node", "remove_field"] = Field(
        description="局部写入操作"
    )
    key: str | None = Field(
        default=None,
        description="set_field/remove_field/append_to_list 使用的字段名或相对路径，例如 timeline[2].actions",
    )
    value: Any = Field(default=None, description="写入的新值，必须是合法 JSON/YAML 值")


class AppendShotActionInput(BaseModel):
    shot_id: str = Field(description="需要补充动作的 shot.id")
    action: dict[str, Any] = Field(
        description="动作对象，必须包含 actor、motion、from、to、emotion，actor 必须是已有 character.id"
    )


class EnsureCastMemberInput(BaseModel):
    scene_id: str = Field(description="storyboard scene 的 scene_id")
    character_id: str = Field(description="需要加入 cast 的已有 character.id")
    position: Literal["left", "center", "right", "back_left", "back_right"] = Field(
        default="center",
        description="角色在画布中的站位",
    )
    pose: str = Field(default="idle", description="角色初始姿态")


class SetShotFieldInput(BaseModel):
    shot_id: str = Field(description="需要修改的 shot.id")
    key: Literal["type", "source_beat_id", "duration_ms", "camera", "dialogue", "actions", "effects", "props"] = Field(
        description="允许修改的 shot 字段"
    )
    value: Any = Field(description="字段的新值")


@dataclass(frozen=True)
class ScriptYamlRepairResult:
    yaml_content: str
    operations: list[dict[str, Any]]


class ScriptYamlRepairState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    validation_error: str
    repair_attempts: int
    operation_count: int
    last_validated_operation_count: int
    result: ScriptYamlRepairResult


@dataclass
class _ResolvedTarget:
    path: str
    value: Any
    parent: Any | None = None
    key: str | int | None = None


@dataclass
class _YamlDocumentTools:
    payload: dict[str, Any]
    operations: list[dict[str, Any]] = field(default_factory=list)

    def read_yaml(self, target: str) -> str:
        resolved = self._resolve(target)
        return _json_result({"path": resolved.path, "value": resolved.value})

    def read_yaml_context(self, target: str) -> str:
        resolved = self._resolve(target)
        node = resolved.value if isinstance(resolved.value, Mapping) else {}
        scene = self._scene_for_node(node)
        storyboard_scene = self._storyboard_scene_for_node(node, scene)
        shot = self._shot_for_node(node, storyboard_scene)
        beat = self._beat_for_shot_or_node(shot, node, scene)
        return _json_result(
            {
                "target_path": resolved.path,
                "target": resolved.value,
                "scene": scene,
                "storyboard_scene": storyboard_scene,
                "shot": shot,
                "beat": beat,
                "entity_index": self.entity_index(),
                "cast_with_names": self._cast_context(storyboard_scene),
                "referenced_characters": self._referenced_character_context(
                    [resolved.value, scene, storyboard_scene, shot, beat]
                ),
                "allowed_positions": ["left", "center", "right", "back_left", "back_right"],
            }
        )

    def write_yaml(self, target: str, operation: str, key: str | None = None, value: Any = None) -> str:
        resolved = self._resolve(target)

        if operation == "set_field":
            if not key:
                raise LLMResponseError("set_field 必须提供 key")
            parent, field_key, changed_path = self._resolve_relative_parent(resolved, key)
            if isinstance(field_key, int):
                if not isinstance(parent, list) or field_key < 0 or field_key >= len(parent):
                    raise LLMResponseError(f"{changed_path} 不是可写入的数组位置")
                parent[field_key] = value
            else:
                if not isinstance(parent, dict):
                    raise LLMResponseError(f"{resolved.path} 不是对象，无法 set_field")
                parent[field_key] = value
        elif operation == "append_to_list":
            list_target = self._resolve_relative(resolved, key) if key else resolved
            target_list = list_target.value
            changed_path = list_target.path
            if not isinstance(target_list, list):
                raise LLMResponseError(f"{changed_path} 不是数组，无法 append_to_list")
            target_list.append(value)
            changed_path = f"{changed_path}[{len(target_list) - 1}]"
        elif operation == "replace_node":
            if resolved.parent is None:
                if not isinstance(value, dict):
                    raise LLMResponseError("替换根节点时 value 必须是对象")
                self.payload.clear()
                self.payload.update(value)
            else:
                resolved.parent[resolved.key] = value
            changed_path = resolved.path
        elif operation == "remove_field":
            if not key:
                raise LLMResponseError("remove_field 必须提供 key")
            parent, field_key, changed_path = self._resolve_relative_parent(resolved, key)
            if isinstance(field_key, int):
                if not isinstance(parent, list) or field_key < 0 or field_key >= len(parent):
                    raise LLMResponseError(f"{changed_path} 不是可删除的数组位置")
                parent.pop(field_key)
            else:
                if not isinstance(parent, dict):
                    raise LLMResponseError(f"{resolved.path} 不是对象，无法 remove_field")
                parent.pop(field_key, None)
        else:
            raise LLMResponseError(f"未知写入操作：{operation}")

        record = {"operation": operation, "target": target, "path": changed_path}
        if key:
            record["key"] = key
        self.operations.append(record)
        return _json_result({"ok": True, "changed_path": changed_path})

    def append_shot_action(self, shot_id: str, action: dict[str, Any]) -> str:
        resolved = self._resolve_identifier(shot_id)
        if not isinstance(resolved.value, dict):
            raise LLMResponseError(f"{resolved.path} 不是 shot 对象")
        if not _looks_like_shot(resolved.value):
            raise LLMResponseError(f"{resolved.path} 不是 storyboard shot")

        normalized_action = _normalize_action(action)
        self._require_existing_character(normalized_action["actor"])

        actions = resolved.value.get("actions")
        if actions is None:
            actions = []
            resolved.value["actions"] = actions
        if not isinstance(actions, list):
            raise LLMResponseError(f"{shot_id}.actions 不是数组")

        actions.append(normalized_action)
        changed_path = f"{resolved.path}.actions[{len(actions) - 1}]"
        self.operations.append(
            {
                "operation": "append_shot_action",
                "target": shot_id,
                "path": changed_path,
                "actor": normalized_action["actor"],
            }
        )
        return _json_result(
            {
                "ok": True,
                "changed_path": changed_path,
                "actor": self._character_context(normalized_action["actor"]),
            }
        )

    def ensure_cast_member(
        self,
        scene_id: str,
        character_id: str,
        position: str = "center",
        pose: str = "idle",
    ) -> str:
        self._require_existing_character(character_id)
        if position not in {"left", "center", "right", "back_left", "back_right"}:
            raise LLMResponseError(f"cast.position 不合法：{position}")

        resolved = self._resolve_identifier(f"storyboard_scene:{scene_id}")
        if not isinstance(resolved.value, dict):
            raise LLMResponseError(f"{resolved.path} 不是 storyboard scene 对象")

        cast = resolved.value.get("cast")
        if cast is None:
            cast = []
            resolved.value["cast"] = cast
        if not isinstance(cast, list):
            raise LLMResponseError(f"{scene_id}.cast 不是数组")

        for index, member in enumerate(cast):
            if isinstance(member, Mapping) and member.get("character_id") == character_id:
                member["position"] = position
                member["pose"] = pose.strip() or "idle"
                changed_path = f"{resolved.path}.cast[{index}]"
                self.operations.append(
                    {
                        "operation": "ensure_cast_member",
                        "target": f"storyboard_scene:{scene_id}",
                        "path": changed_path,
                        "character_id": character_id,
                    }
                )
                return _json_result(
                    {
                        "ok": True,
                        "changed_path": changed_path,
                        "already_present": True,
                        "character": self._character_context(character_id),
                        "cast_with_names": self._cast_context(resolved.value),
                    }
                )

        cast.append({"character_id": character_id, "position": position, "pose": pose.strip() or "idle"})
        changed_path = f"{resolved.path}.cast[{len(cast) - 1}]"
        self.operations.append(
            {
                "operation": "ensure_cast_member",
                "target": f"storyboard_scene:{scene_id}",
                "path": changed_path,
                "character_id": character_id,
            }
        )
        return _json_result(
            {
                "ok": True,
                "changed_path": changed_path,
                "already_present": False,
                "character": self._character_context(character_id),
                "cast_with_names": self._cast_context(resolved.value),
            }
        )

    def set_shot_field(self, shot_id: str, key: str, value: Any) -> str:
        resolved = self._resolve_identifier(shot_id)
        if not isinstance(resolved.value, dict):
            raise LLMResponseError(f"{resolved.path} 不是 shot 对象")
        if not _looks_like_shot(resolved.value):
            raise LLMResponseError(f"{resolved.path} 不是 storyboard shot")
        if key not in {"type", "source_beat_id", "duration_ms", "camera", "dialogue", "actions", "effects", "props"}:
            raise LLMResponseError(f"不允许修改 shot 字段：{key}")

        resolved.value[key] = value
        changed_path = f"{resolved.path}.{key}"
        self.operations.append({"operation": "set_shot_field", "target": shot_id, "path": changed_path, "key": key})
        return _json_result({"ok": True, "changed_path": changed_path})

    def outline(self) -> dict[str, Any]:
        scenes = self.payload.get("scenes")
        storyboard = self.payload.get("storyboard")
        storyboard_scenes = storyboard.get("scenes") if isinstance(storyboard, Mapping) else None
        return {
            "schema_version": self.payload.get("schema_version"),
            "title": self.payload.get("title"),
            "entity_index": self.entity_index(),
            "scenes": _scene_outline_items(scenes, self.payload),
            "storyboard_scenes": _storyboard_outline_items(storyboard_scenes, self.payload),
        }

    def entity_index(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "characters": _id_name_items(self.payload.get("characters")),
            "locations": _id_name_items(self.payload.get("locations")),
            "events": _id_summary_items(self.payload.get("events")),
        }

    def _resolve(self, target: str) -> _ResolvedTarget:
        normalized = target.strip()
        if not normalized:
            return _ResolvedTarget(path="$", value=self.payload)
        if _looks_like_path(normalized):
            return self._resolve_path(normalized)
        return self._resolve_identifier(normalized)

    def _resolve_path(self, path: str) -> _ResolvedTarget:
        current: Any = self.payload
        parent: Any | None = None
        parent_key: str | int | None = None
        resolved_path = "$"

        for token in _path_tokens(path):
            parent = current
            parent_key = token
            if isinstance(token, int):
                if not isinstance(current, list) or token < 0 or token >= len(current):
                    raise LLMResponseError(f"YAML 路径不存在：{path}")
                current = current[token]
                resolved_path += f"[{token}]"
            else:
                if not isinstance(current, Mapping) or token not in current:
                    raise LLMResponseError(f"YAML 路径不存在：{path}")
                current = current[token]
                resolved_path += f".{token}"

        return _ResolvedTarget(path=resolved_path, value=current, parent=parent, key=parent_key)

    def _resolve_relative(self, base: _ResolvedTarget, key_path: str) -> _ResolvedTarget:
        current: Any = base.value
        parent: Any | None = base.parent
        parent_key: str | int | None = base.key
        resolved_path = base.path

        for token in _path_tokens(key_path):
            parent = current
            parent_key = token
            if isinstance(token, int):
                if not isinstance(current, list) or token < 0 or token >= len(current):
                    raise LLMResponseError(f"YAML 相对路径不存在：{base.path}.{key_path}")
                current = current[token]
            else:
                if not isinstance(current, Mapping) or token not in current:
                    raise LLMResponseError(f"YAML 相对路径不存在：{base.path}.{key_path}")
                current = current[token]
            resolved_path = _append_path_token(resolved_path, token)

        return _ResolvedTarget(path=resolved_path, value=current, parent=parent, key=parent_key)

    def _resolve_relative_parent(self, base: _ResolvedTarget, key_path: str) -> tuple[Any, str | int, str]:
        tokens = _path_tokens(key_path)
        if not tokens:
            raise LLMResponseError(f"YAML 相对路径格式无效：{key_path}")

        parent = base.value
        parent_path = base.path
        for token in tokens[:-1]:
            if isinstance(token, int):
                if not isinstance(parent, list) or token < 0 or token >= len(parent):
                    raise LLMResponseError(f"YAML 相对路径不存在：{base.path}.{key_path}")
                parent = parent[token]
            else:
                if not isinstance(parent, Mapping) or token not in parent:
                    raise LLMResponseError(f"YAML 相对路径不存在：{base.path}.{key_path}")
                parent = parent[token]
            parent_path = _append_path_token(parent_path, token)

        field_key = tokens[-1]
        return parent, field_key, _append_path_token(parent_path, field_key)

    def _resolve_identifier(self, target: str) -> _ResolvedTarget:
        prefix, _, raw_identifier = target.partition(":")
        identifier = raw_identifier.strip() if raw_identifier else target.strip()
        kind = prefix.strip() if raw_identifier else ""

        if kind == "storyboard_scene":
            return self._find_mapping(lambda item: item.get("scene_id") == identifier, f"storyboard_scene:{identifier}")
        if kind == "scene":
            return self._find_mapping(lambda item: item.get("id") == identifier, f"scene:{identifier}")
        if kind in {"character", "location", "event"}:
            return self._find_mapping(lambda item: item.get("id") == identifier, f"{kind}:{identifier}")

        return self._find_mapping(
            lambda item: item.get("id") == identifier or item.get("scene_id") == identifier,
            identifier,
        )

    def _find_mapping(self, predicate, target: str) -> _ResolvedTarget:
        stack: list[tuple[str, Any, Any | None, str | int | None]] = [("$", self.payload, None, None)]
        while stack:
            path, value, parent, key = stack.pop()
            if isinstance(value, Mapping):
                if predicate(value):
                    return _ResolvedTarget(path=path, value=value, parent=parent, key=key)
                for item_key, item_value in reversed(list(value.items())):
                    stack.append((f"{path}.{item_key}", item_value, value, item_key))
            elif isinstance(value, list):
                for index in range(len(value) - 1, -1, -1):
                    stack.append((f"{path}[{index}]", value[index], value, index))

        raise LLMResponseError(f"YAML 对象不存在：{target}")

    def _scene_for_node(self, node: Mapping[str, Any]) -> Mapping[str, Any] | None:
        scene_id = str(node.get("scene_id") or "").strip()
        if not scene_id and node.get("id"):
            node_id = str(node.get("id"))
            for scene in _object_items(self.payload.get("scenes")):
                if scene.get("id") == node_id:
                    return scene
                for beat in _object_items(scene.get("beats")):
                    if beat.get("id") == node_id:
                        return scene
            for storyboard_scene in _object_items(_storyboard_scenes(self.payload)):
                for shot in _object_items(storyboard_scene.get("timeline")):
                    if shot.get("id") == node_id:
                        scene_id = str(storyboard_scene.get("scene_id") or "").strip()
                        break
                if scene_id:
                    break
        if scene_id:
            for scene in _object_items(self.payload.get("scenes")):
                if scene.get("id") == scene_id:
                    return scene
        return None

    def _storyboard_scene_for_node(
        self,
        node: Mapping[str, Any],
        scene: Mapping[str, Any] | None,
    ) -> Mapping[str, Any] | None:
        if node.get("scene_id") and node.get("timeline") is not None:
            return node
        scene_id = str(scene.get("id") or "").strip() if scene else ""
        node_id = str(node.get("id") or "").strip()
        for storyboard_scene in _object_items(_storyboard_scenes(self.payload)):
            if scene_id and storyboard_scene.get("scene_id") == scene_id:
                return storyboard_scene
            for shot in _object_items(storyboard_scene.get("timeline")):
                if shot.get("id") == node_id:
                    return storyboard_scene
        return None

    def _shot_for_node(
        self,
        node: Mapping[str, Any],
        storyboard_scene: Mapping[str, Any] | None,
    ) -> Mapping[str, Any] | None:
        if node.get("source_beat_id") and node.get("camera") is not None:
            return node
        node_id = str(node.get("id") or "").strip()
        for shot in _object_items((storyboard_scene or {}).get("timeline")):
            if shot.get("id") == node_id:
                return shot
        return None

    def _beat_for_shot_or_node(
        self,
        shot: Mapping[str, Any] | None,
        node: Mapping[str, Any],
        scene: Mapping[str, Any] | None,
    ) -> Mapping[str, Any] | None:
        beat_id = str((shot or {}).get("source_beat_id") or node.get("id") or "").strip()
        if not beat_id or scene is None:
            return None
        for beat in _object_items(scene.get("beats")):
            if beat.get("id") == beat_id:
                return beat
        return None

    def _require_existing_character(self, character_id: str) -> None:
        normalized_id = str(character_id or "").strip()
        if not normalized_id:
            raise LLMResponseError("character_id 不能为空")
        if normalized_id not in {str(item.get("id")) for item in _object_items(self.payload.get("characters"))}:
            available = "、".join(_character_display(item) for item in _object_items(self.payload.get("characters")))
            raise LLMResponseError(f"角色不存在：{normalized_id}；可用角色：{available}")

    def _character_context(self, character_id: str) -> dict[str, Any]:
        normalized_id = str(character_id or "").strip()
        for item in _object_items(self.payload.get("characters")):
            if str(item.get("id", "")).strip() == normalized_id:
                return _character_item(item)
        return {"id": normalized_id, "name": normalized_id}

    def _cast_context(self, storyboard_scene: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        if storyboard_scene is None:
            return []
        cast = storyboard_scene.get("cast")
        if not isinstance(cast, list):
            return []

        cast_context: list[dict[str, Any]] = []
        for member in cast:
            if not isinstance(member, Mapping):
                continue
            character = self._character_context(str(member.get("character_id", "")).strip())
            cast_context.append(
                {
                    **character,
                    "position": member.get("position"),
                    "pose": member.get("pose"),
                }
            )
        return cast_context

    def _referenced_character_context(self, values: list[Any]) -> list[dict[str, Any]]:
        character_ids: set[str] = set()
        for value in values:
            character_ids.update(_collect_character_refs(value))
        return [self._character_context(character_id) for character_id in sorted(character_ids)]


class ScriptYamlToolRepairer:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    def repair(self, yaml_content: str, validation_error: str) -> ScriptYamlRepairResult:
        payload, _ = parse_yaml_content(yaml_content)
        document_tools = _YamlDocumentTools(payload)
        tools = self._build_tools(document_tools)
        graph = self._build_graph(document_tools, tools)
        final_state = graph.invoke(
            {
                "messages": _build_repair_messages(document_tools, validation_error),
                "validation_error": validation_error,
                "repair_attempts": 0,
                "operation_count": 0,
                "last_validated_operation_count": 0,
            },
            {"recursion_limit": TOOL_CALL_LIMIT * 4},
        )
        result = final_state.get("result")
        if result is None:
            raise LLMResponseError("AI YAML 修复未产生可保存结果")
        return result

    def _build_tools(self, document_tools: _YamlDocumentTools) -> list[StructuredTool]:
        read_tool = StructuredTool.from_function(
            name="read_yaml",
            description="读取当前 YAML 的局部节点。target 可以是路径、对象 id、scene:<id> 或 storyboard_scene:<scene_id>。",
            func=document_tools.read_yaml,
            args_schema=ReadYamlInput,
        )
        read_context_tool = StructuredTool.from_function(
            name="read_yaml_context",
            description=(
                "读取目标节点的上下文。适合修复 shot/beat/scene：会返回所属 scene、storyboard_scene、shot、beat、cast 和可用 ID。"
            ),
            func=document_tools.read_yaml_context,
            args_schema=ReadYamlContextInput,
        )
        write_tool = StructuredTool.from_function(
            name="write_yaml",
            description="对当前 YAML 执行局部写入。只能修改必要节点，不允许重写整份 YAML。",
            func=document_tools.write_yaml,
            args_schema=WriteYamlInput,
        )
        append_shot_action_tool = StructuredTool.from_function(
            name="append_shot_action",
            description=(
                "给指定 storyboard shot 追加一个动作。用于修复 action 类型 shot 缺少 actions 的问题，"
                "action 必须包含 actor、motion、from、to、emotion。"
            ),
            func=document_tools.append_shot_action,
            args_schema=AppendShotActionInput,
        )
        ensure_cast_member_tool = StructuredTool.from_function(
            name="ensure_cast_member",
            description=(
                "确保指定 storyboard scene.cast 中包含某个已有角色，并分配 left/center/right/back_left/back_right 站位。"
                "用于修复 dialogue/actions 角色未出现在 cast 中的问题。"
            ),
            func=document_tools.ensure_cast_member,
            args_schema=EnsureCastMemberInput,
        )
        set_shot_field_tool = StructuredTool.from_function(
            name="set_shot_field",
            description="修改指定 shot 的一个允许字段。用于修复 shot 局部字段，不允许重写整份 YAML。",
            func=document_tools.set_shot_field,
            args_schema=SetShotFieldInput,
        )
        return [
            read_tool,
            read_context_tool,
            append_shot_action_tool,
            ensure_cast_member_tool,
            set_shot_field_tool,
            write_tool,
        ]

    def _build_graph(self, document_tools: _YamlDocumentTools, tools: list[StructuredTool]):
        bound_model = self.model.bind_tools(tools)
        graph = StateGraph(ScriptYamlRepairState)
        graph.add_node("agent", _call_model_node(bound_model))
        graph.add_node("tools", ToolNode(tools))
        graph.add_node("sync_tools", _sync_tool_state_node(document_tools))
        graph.add_node("validate", _validate_yaml_node(document_tools))
        graph.add_node("missing_tool", _missing_tool_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges(
            "agent",
            _route_after_agent,
            {
                "tools": "tools",
                "missing_tool": "missing_tool",
            },
        )
        graph.add_edge("tools", "sync_tools")
        graph.add_conditional_edges(
            "sync_tools",
            _route_after_tools,
            {
                "validate": "validate",
                "agent": "agent",
            },
        )
        graph.add_conditional_edges(
            "validate",
            _route_after_validation,
            {
                "finish": END,
                "agent": "agent",
            },
        )
        return graph.compile()


def _call_model_node(model: BaseChatModel):
    def node(state: ScriptYamlRepairState) -> ScriptYamlRepairState:
        try:
            response = model.invoke(state["messages"])
        except Exception as exc:
            raise LLMResponseError(f"AI YAML 修复服务调用失败：{exc}") from exc
        return {"messages": [response]}

    return node


def _sync_tool_state_node(document_tools: _YamlDocumentTools):
    def node(state: ScriptYamlRepairState) -> ScriptYamlRepairState:
        return {"operation_count": len(document_tools.operations)}

    return node


def _validate_yaml_node(document_tools: _YamlDocumentTools):
    def node(state: ScriptYamlRepairState) -> ScriptYamlRepairState:
        operation_count = int(state.get("operation_count", 0))
        try:
            yaml_content = normalize_script_yaml_payload(document_tools.payload)
            return {
                "result": ScriptYamlRepairResult(yaml_content=yaml_content, operations=document_tools.operations),
                "last_validated_operation_count": operation_count,
            }
        except LLMResponseError as exc:
            repair_attempts = int(state.get("repair_attempts", 0)) + 1
            if repair_attempts >= REPAIR_LIMIT:
                raise LLMResponseError(f"AI YAML 修复后仍未通过校验：{exc}") from exc
            return {
                "validation_error": str(exc),
                "repair_attempts": repair_attempts,
                "last_validated_operation_count": operation_count,
                "messages": [
                    HumanMessage(
                        content=(
                            "工具写入后仍未通过结构校验。继续使用 read_yaml_context、read_yaml、"
                            "append_shot_action、ensure_cast_member、set_shot_field 或 write_yaml "
                            "做局部修复，不要输出完整 YAML。\n"
                            f"最新校验错误：{exc}"
                        )
                    )
                ],
            }

    return node


def _missing_tool_node(state: ScriptYamlRepairState) -> ScriptYamlRepairState:
    raise LLMResponseError("AI YAML 修复没有调用 YAML 读取或写入工具")


def _route_after_agent(state: ScriptYamlRepairState) -> str:
    last_message = state["messages"][-1]
    return "tools" if getattr(last_message, "tool_calls", None) else "missing_tool"


def _route_after_tools(state: ScriptYamlRepairState) -> str:
    operation_count = int(state.get("operation_count", 0))
    last_validated_operation_count = int(state.get("last_validated_operation_count", 0))
    return "validate" if operation_count > last_validated_operation_count else "agent"


def _route_after_validation(state: ScriptYamlRepairState) -> str:
    return "finish" if state.get("result") else "agent"


def _build_repair_messages(document_tools: _YamlDocumentTools, validation_error: str) -> list[BaseMessage]:
    return [
        SystemMessage(
            content=(
                "你是 ScriptCraft 的 YAML 修复 Agent。你必须通过工具修复当前 YAML，不能直接输出完整 YAML。"
                "你可以调用 read_yaml_context 读取目标上下文，调用 read_yaml 读取局部节点。"
                "修复 action 缺少动作时优先调用 append_shot_action。"
                "修复角色未进入分镜 cast 时优先调用 ensure_cast_member。"
                "修复 shot 局部字段时优先调用 set_shot_field。"
                "write_yaml 只用于上述工具无法表达的局部修改。"
                "每次只改必要字段；不要新增不存在的角色、地点或事件 ID；不要删除整份结构。"
                "char_xxx、loc_xxx、event_xxx 只是内部稳定 ID，不代表语义。"
                "你必须先用 read_yaml_context 或 read_yaml 读取 entity_index，通过真实姓名、别名、角色描述、地点名和事件摘要判断对象。"
                "理解时使用真实姓名和语义，写回时仍然使用对应的稳定 ID。"
                "如果错误是 dialogue/actions 角色没有出现在 storyboard scene.cast 中，"
                "先 read_yaml_context 读取对应 shot 上下文，再把角色加入 cast 并分配 left/center/right/back_left/back_right。"
                "但如果该角色的真实姓名、别名或角色描述是旁白、叙述者、画外音或 narrator，"
                "不要把它加入 cast；应把对应 shot/beat 改为 narration，并移除 dialogue.speaker_id。"
                "如果 action 类型 shot 缺少 actions/effects/props，先 read_yaml_context 读取对应 shot 和 beat，"
                "再调用 append_shot_action 给该 shot 添加动作。"
                "如果引用了不存在的 ID，先读取 characters/locations/events，改成最接近的已有 ID 或移除该引用。"
            )
        ),
        HumanMessage(
            content=(
                "当前完整 YAML 已加载到工具文档中，请用 read_yaml_context/read_yaml/write_yaml 修复它。\n"
                f"当前校验错误：{validation_error}\n"
                "文档概要 JSON：\n"
                f"{json.dumps(document_tools.outline(), ensure_ascii=False)}"
            )
        ),
    ]


def _path_tokens(path: str) -> list[str | int]:
    normalized = path.strip()
    if normalized.startswith("$."):
        normalized = normalized[2:]
    elif normalized == "$":
        return []

    tokens: list[str | int] = []
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]", normalized):
        name, index = match.groups()
        tokens.append(name if name is not None else int(index))
    if not tokens:
        raise LLMResponseError(f"YAML 路径格式无效：{path}")
    return tokens


def _append_path_token(path: str, token: str | int) -> str:
    return f"{path}[{token}]" if isinstance(token, int) else f"{path}.{token}"


def _looks_like_path(value: str) -> bool:
    return value == "$" or "." in value or "[" in value or value in {
        "characters",
        "locations",
        "events",
        "scenes",
        "storyboard",
        "metadata",
    }


def _looks_like_shot(value: Mapping[str, Any]) -> bool:
    return value.get("source_beat_id") is not None and value.get("camera") is not None


def _normalize_action(action: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise LLMResponseError("action 必须是对象")

    normalized = dict(action)
    required_fields = ("actor", "motion", "from", "to", "emotion")
    missing = [field_name for field_name in required_fields if not str(normalized.get(field_name, "")).strip()]
    if missing:
        raise LLMResponseError(f"action 缺少字段：{', '.join(missing)}")

    for field_name in required_fields:
        normalized[field_name] = str(normalized[field_name]).strip()
    return normalized


def _id_name_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append(_character_item(item) if _is_character_item(item) else _named_item(item))
    return items


def _id_summary_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary"),
                    "source_chapter": item.get("source_chapter"),
                    "source_chapters": item.get("source_chapters"),
                    "involved_characters": item.get("involved_characters"),
                }
            )
    return items


def _scene_outline_items(value: Any, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for scene in value:
        if not isinstance(scene, Mapping):
            continue
        items.append(
            {
                "id": scene.get("id"),
                "title": scene.get("title"),
                "location": _location_context(payload, scene.get("location_id")),
                "characters": _character_contexts(payload, scene.get("characters")),
                "beat_ids": [
                    beat.get("id")
                    for beat in scene.get("beats", [])
                    if isinstance(beat, Mapping) and beat.get("id")
                ],
            }
        )
    return items


def _storyboard_outline_items(value: Any, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for scene in value:
        if not isinstance(scene, Mapping):
            continue
        items.append(
            {
                "scene_id": scene.get("scene_id"),
                "cast": [
                    {
                        **_character_context(payload, member.get("character_id")),
                        "position": member.get("position"),
                        "pose": member.get("pose"),
                    }
                    for member in scene.get("cast", [])
                    if isinstance(member, Mapping) and member.get("character_id")
                ],
                "shot_ids": [
                    shot.get("id")
                    for shot in scene.get("timeline", [])
                    if isinstance(shot, Mapping) and shot.get("id")
                ],
            }
        )
    return items


def _storyboard_scenes(payload: Mapping[str, Any]) -> Any:
    storyboard = payload.get("storyboard")
    return storyboard.get("scenes") if isinstance(storyboard, Mapping) else []


def _object_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _named_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "description": item.get("description"),
    }


def _character_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "aliases": item.get("aliases") if isinstance(item.get("aliases"), list) else [],
        "role": item.get("role"),
        "description": item.get("description"),
        "motivation": item.get("motivation"),
    }


def _is_character_item(item: Mapping[str, Any]) -> bool:
    return "role" in item or "aliases" in item or str(item.get("id", "")).startswith("char_")


def _character_display(item: Mapping[str, Any]) -> str:
    character = _character_item(item)
    item_id = str(character.get("id", "")).strip()
    name = str(character.get("name", "")).strip()
    aliases = [str(alias).strip() for alias in character.get("aliases", []) if str(alias).strip()]
    role = str(character.get("role", "")).strip()
    details = [value for value in [name, f"别名：{'、'.join(aliases)}" if aliases else "", role] if value]
    return f"{item_id}（{' / '.join(details)}）" if details else item_id


def _character_context(payload: Mapping[str, Any], character_id: Any) -> dict[str, Any]:
    normalized_id = str(character_id or "").strip()
    for item in _object_items(payload.get("characters")):
        if str(item.get("id", "")).strip() == normalized_id:
            return _character_item(item)
    return {"id": normalized_id, "name": normalized_id}


def _character_contexts(payload: Mapping[str, Any], character_ids: Any) -> list[dict[str, Any]]:
    if not isinstance(character_ids, list):
        return []
    return [_character_context(payload, character_id) for character_id in character_ids if str(character_id).strip()]


def _location_context(payload: Mapping[str, Any], location_id: Any) -> dict[str, Any]:
    normalized_id = str(location_id or "").strip()
    for item in _object_items(payload.get("locations")):
        if str(item.get("id", "")).strip() == normalized_id:
            return _named_item(item)
    return {"id": normalized_id, "name": normalized_id}


def _collect_character_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"character_id", "speaker_id", "actor"}:
                text = str(item or "").strip()
                if text:
                    refs.add(text)
            elif key == "characters" and isinstance(item, list):
                refs.update(str(character_id).strip() for character_id in item if str(character_id).strip())
            else:
                refs.update(_collect_character_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(_collect_character_refs(item))
    return refs


def _json_result(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
