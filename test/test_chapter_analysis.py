import json
import os
import sys
import unittest

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import Field


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from chapter_analysis import ChapterAnalyzer


class RecordingFakeChatModel(FakeListChatModel):
    prompts: list[str] = Field(default_factory=list)

    def _call(self, messages, *args, **kwargs):
        self.prompts.append("\n".join(str(message.content) for message in messages))
        return super()._call(messages, *args, **kwargs)


class ChapterAnalysisTests(unittest.TestCase):
    def test_analyzes_single_chapter_to_structured_payload(self):
        model = FakeListChatModel(
            responses=[
                json.dumps(
                    {
                        "summary": "林舟在废弃天台收到外界信号，发现城市防护罩之外仍有幸存者。",
                        "characters": [
                            {
                                "name": "林舟",
                                "aliases": [],
                                "role_in_chapter": "主角",
                                "evidence": "他打开一台从垃圾场捡来的旧终端。",
                            }
                        ],
                        "locations": [
                            {
                                "name": "第九区贫民层废弃工厂天台",
                                "description": "唯一能收到外界信号的地方。",
                                "evidence": "这里是整个贫民层唯一能接收到外界信号的地方。",
                            }
                        ],
                        "events": [
                            {
                                "summary": "林舟接收到疑似来自火星的信号。",
                                "event_type": "inciting_incident",
                                "involved_characters": ["林舟"],
                                "evidence": "屏幕闪烁起来。",
                            }
                        ],
                        "conflicts": ["贫民层与外界信息隔绝"],
                        "dialogue_candidates": ["终于见面了。"],
                        "scene_candidates": [
                            {
                                "title": "天台信号",
                                "location": "废弃工厂天台",
                                "characters": ["林舟"],
                                "summary": "林舟在天台捕捉到神秘信号。",
                                "dramatic_purpose": "引出主线目标。",
                                "beats": ["林舟爬上天台", "旧终端亮起", "陌生声音出现"],
                            }
                        ],
                        "continuity_notes": ["外界信号来源需要后续解释"],
                    },
                    ensure_ascii=False,
                )
            ]
        )

        result = ChapterAnalyzer(model).analyze(
            title="星火计划",
            chapter={
                "id": "chapter_001",
                "index": 1,
                "heading": "第一章",
                "title": "废弃天台上的信号",
                "content": "公元2147年，林舟在废弃天台收到信号。",
            },
        )

        self.assertEqual(result["chapter_id"], "chapter_001")
        self.assertEqual(result["chapter_index"], 1)
        self.assertEqual(result["summary"], "林舟在废弃天台收到外界信号，发现城市防护罩之外仍有幸存者。")
        self.assertEqual(result["characters"][0]["name"], "林舟")
        self.assertEqual(result["events"][0]["event_type"], "inciting_incident")
        self.assertEqual(result["scene_candidates"][0]["beats"][1], "旧终端亮起")

    def test_includes_previous_memory_in_chapter_prompt(self):
        model = RecordingFakeChatModel(
            responses=[
                json.dumps(
                    {
                        "summary": "林舟继续追查外界信号。",
                        "characters": [],
                        "locations": [],
                        "events": [],
                        "conflicts": [],
                        "dialogue_candidates": [],
                        "scene_candidates": [],
                        "continuity_notes": [],
                    },
                    ensure_ascii=False,
                )
            ]
        )

        ChapterAnalyzer(model).analyze(
            title="星火计划",
            chapter={
                "id": "chapter_002",
                "index": 2,
                "heading": "第二章",
                "title": "追踪",
                "content": "林舟追查信号。",
            },
            memory={
                "story_so_far": "第 1 章中林舟在废弃天台收到外界信号。",
                "continuity_notes": ["外界信号来源未明"],
            },
        )

        self.assertIn("第 1 章中林舟在废弃天台收到外界信号", model.prompts[0])
        self.assertIn("外界信号来源未明", model.prompts[0])


if __name__ == "__main__":
    unittest.main()
