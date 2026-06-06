import json
import os
import sys
import unittest

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import Field


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from script_yaml import ScriptYamlGenerator


class RecordingFakeChatModel(FakeListChatModel):
    prompts: list[str] = Field(default_factory=list)

    def _call(self, messages, *args, **kwargs):
        self.prompts.append("\n".join(str(message.content) for message in messages))
        return super()._call(messages, *args, **kwargs)


class ScriptYamlTests(unittest.TestCase):
    def test_generates_script_yaml_by_chapter_with_short_memory(self):
        model = RecordingFakeChatModel(
            responses=[
                json.dumps(_plan_payload(1), ensure_ascii=False),
                json.dumps(_fragment_payload(1), ensure_ascii=False),
                json.dumps(_memory_payload(1), ensure_ascii=False),
                json.dumps(_plan_payload(2), ensure_ascii=False),
                json.dumps(_fragment_payload(2), ensure_ascii=False),
                json.dumps(_memory_payload(2), ensure_ascii=False),
                json.dumps(_plan_payload(3), ensure_ascii=False),
                json.dumps(_fragment_payload(3), ensure_ascii=False),
                json.dumps(_memory_payload(3), ensure_ascii=False),
            ]
        )

        progress_events = []
        result = ScriptYamlGenerator(model).generate(
            title="长篇样例",
            chapters=[_chapter(index) for index in range(1, 4)],
            characters=_characters(),
            locations=_locations(),
            events=_events(),
            on_progress=progress_events.append,
        )

        self.assertEqual(len(model.prompts), 9)
        self.assertEqual(progress_events[0]["phase"], "scene_planning")
        self.assertEqual(progress_events[0]["chapter_index"], 1)
        self.assertEqual(progress_events[0]["chapter_total"], 3)
        self.assertIn("fragment_generation", [event["phase"] for event in progress_events])
        self.assertIn("memory_update", [event["phase"] for event in progress_events])
        self.assertEqual(progress_events[-1]["phase"], "finished")
        self.assertEqual(progress_events[-1]["completed_chapters"], 3)
        self.assertIn("scene_001_001", result)
        self.assertIn("scene_002_001", result)
        self.assertIn("scene_003_001", result)
        self.assertIn("chapters_count: 3", result)
        self.assertIn("chapter_001", model.prompts[0])
        self.assertNotIn("chapter_002", model.prompts[0])
        self.assertNotIn("chapter_003", model.prompts[0])
        self.assertIn("第1章之后的剧情记忆", model.prompts[3])
        self.assertIn("chapter_002", model.prompts[3])
        self.assertNotIn("chapter_003", model.prompts[3])

    def test_repairs_only_current_chapter_fragment(self):
        invalid_fragment = _fragment_payload(1)
        invalid_fragment["storyboard"]["scenes"][0]["cast"] = []
        model = RecordingFakeChatModel(
            responses=[
                json.dumps(_plan_payload(1), ensure_ascii=False),
                json.dumps(invalid_fragment, ensure_ascii=False),
                json.dumps(_fragment_payload(1), ensure_ascii=False),
                json.dumps(_memory_payload(1), ensure_ascii=False),
            ]
        )

        result = ScriptYamlGenerator(model).generate(
            title="长篇样例",
            chapters=[_chapter(1)],
            characters=_characters(),
            locations=_locations(),
            events=_events(),
        )

        self.assertEqual(len(model.prompts), 4)
        self.assertIn("需要修复的章节 YAML 片段", model.prompts[2])
        self.assertIn("character_id: char_001", result)
        self.assertIn("speaker_id: char_001", result)


def _chapter(index: int) -> dict:
    return {
        "id": f"chapter_{index:03d}",
        "index": index,
        "heading": f"第{index}章",
        "title": f"章节{index}",
        "summary": f"第{index}章摘要",
        "analysis": {
            "summary": f"第{index}章摘要",
            "characters": [{"name": "林舟"}],
            "locations": [{"name": "旧书店"}],
            "events": [{"summary": f"第{index}章事件"}],
            "conflicts": [f"第{index}章冲突"],
            "dialogue_candidates": ["这里还有人吗？"],
            "scene_candidates": [
                {
                    "title": f"章节{index}场景",
                    "location": "旧书店",
                    "characters": ["林舟"],
                    "summary": f"第{index}章场景摘要",
                    "dramatic_purpose": "推进悬疑线",
                    "beats": ["进入旧书店", "发现线索", "留下悬念"],
                }
            ],
            "continuity_notes": [f"第{index}章连续性"],
        },
    }


def _characters() -> list[dict]:
    return [
        {
            "id": "char_001",
            "name": "林舟",
            "aliases": [],
            "role": "主角",
            "description": "寻找线索的年轻人。",
            "motivation": "找出匿名信来源。",
        }
    ]


def _locations() -> list[dict]:
    return [
        {
            "id": "loc_001",
            "name": "旧书店",
            "description": "雨夜里快要倒闭的书店。",
        }
    ]


def _events() -> list[dict]:
    return [
        {
            "id": f"event_{index:03d}",
            "source_chapter": f"chapter_{index:03d}",
            "summary": f"第{index}章关键事件",
            "involved_characters": ["char_001"],
        }
        for index in range(1, 4)
    ]


def _plan_payload(index: int) -> dict:
    return {
        "chapter_id": f"chapter_{index:03d}",
        "scenes": [
            {
                "id": f"scene_{index:03d}_001",
                "title": f"章节{index}场景",
                "source_chapters": [f"chapter_{index:03d}"],
                "source_events": [f"event_{index:03d}"],
                "location_id": "loc_001",
                "time_of_day": "night",
                "characters": ["char_001"],
                "dramatic_purpose": "推进悬疑线",
                "summary": f"第{index}章被拆成一个剧本场景。",
                "key_beats": ["进入旧书店", "发现线索", "留下悬念"],
            }
        ],
    }


def _fragment_payload(index: int) -> dict:
    scene_id = f"scene_{index:03d}_001"
    return {
        "scenes": [
            {
                "id": scene_id,
                "title": f"章节{index}场景",
                "source_chapters": [f"chapter_{index:03d}"],
                "source_events": [f"event_{index:03d}"],
                "location_id": "loc_001",
                "time_of_day": "night",
                "characters": ["char_001"],
                "dramatic_purpose": "推进悬疑线。",
                "summary": f"林舟在第{index}章进入旧书店并发现线索。",
                "beats": [
                    {
                        "id": f"beat_{index:03d}_001_001",
                        "type": "action",
                        "content": "林舟推门进入旧书店。",
                    },
                    {
                        "id": f"beat_{index:03d}_001_002",
                        "type": "dialogue",
                        "speaker_id": "char_001",
                        "content": "这里还有人吗？",
                    },
                    {
                        "id": f"beat_{index:03d}_001_003",
                        "type": "narration",
                        "content": "雨声盖住了门铃声。",
                    },
                ],
            }
        ],
        "storyboard": {
            "scenes": [
                {
                    "scene_id": scene_id,
                    "setting": {
                        "mood": "suspenseful",
                        "weather": "rain",
                        "lighting": "dim",
                        "background": "雨夜旧书店",
                    },
                    "cast": [
                        {
                            "character_id": "char_001",
                            "position": "center",
                            "pose": "standing",
                        }
                    ],
                    "timeline": [
                        {
                            "id": f"shot_{index:03d}_001_001",
                            "source_beat_id": f"beat_{index:03d}_001_001",
                            "type": "action",
                            "duration_ms": 2000,
                            "camera": {
                                "shot": "wide",
                                "target": "char_001",
                                "movement": "hold",
                            },
                            "actions": [],
                            "effects": ["rain"],
                        },
                        {
                            "id": f"shot_{index:03d}_001_002",
                            "source_beat_id": f"beat_{index:03d}_001_002",
                            "type": "dialogue",
                            "duration_ms": 2000,
                            "camera": {
                                "shot": "medium",
                                "target": "char_001",
                                "movement": "cut",
                            },
                            "actions": [],
                            "dialogue": {
                                "speaker_id": "char_001",
                                "text": "这里还有人吗？",
                            },
                        },
                        {
                            "id": f"shot_{index:03d}_001_003",
                            "source_beat_id": f"beat_{index:03d}_001_003",
                            "type": "narration",
                            "duration_ms": 2000,
                            "camera": {
                                "shot": "wide",
                                "target": "stage",
                                "movement": "hold",
                            },
                            "actions": [],
                            "effects": ["rain"],
                        },
                    ],
                }
            ]
        },
    }


def _memory_payload(index: int) -> dict:
    return {
        "story_so_far": f"第{index}章之后的剧情记忆",
        "character_state": [
            {
                "character_id": "char_001",
                "current_goal": "继续追查匿名信",
                "relationship_changes": [],
            }
        ],
        "open_threads": ["匿名信来源"],
        "used_events": [f"event_{index:03d}"],
        "last_scene_summary": f"第{index}章最后一个场景结束。",
    }


if __name__ == "__main__":
    unittest.main()
