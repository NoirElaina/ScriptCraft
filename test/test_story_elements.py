import os
import sys
import tempfile
import unittest
import json
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI
from pydantic import Field


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from llm import (
    LLMConfigError,
    create_llm_client_from_env,
)
from llm.env_loader import load_env_file
from story_elements import StoryElementExtractor


class RecordingFakeChatModel(FakeListChatModel):
    prompts: list[str] = Field(default_factory=list)

    def _call(self, messages, *args, **kwargs):
        self.prompts.append("\n".join(str(message.content) for message in messages))
        return super()._call(messages, *args, **kwargs)


class StoryElementTests(unittest.TestCase):
    def test_extracts_story_elements_incrementally_by_chapter(self):
        model = RecordingFakeChatModel(
            responses=[
                json.dumps(
                    {
                        "character_updates": [
                            {
                                "action": "create",
                                "name": "林舟",
                                "aliases": [],
                                "role": "主角",
                                "description": "年轻记者",
                                "motivation": "查清匿名短信来源",
                            }
                        ],
                        "location_updates": [
                            {
                                "action": "create",
                                "name": "老城区咖啡馆",
                                "description": "雨夜中的见面地点",
                            }
                        ],
                        "event_updates": [
                            {
                                "action": "create",
                                "source_chapter": "chapter_001",
                                "summary": "林舟收到匿名短信。",
                                "involved_characters": ["林舟"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "character_updates": [
                            {
                                "action": "merge",
                                "target_id": "char_001",
                                "name": "林舟",
                                "new_aliases": ["小林"],
                                "role": "主角",
                                "description_patch": "第二章中开始主动追查线索。",
                                "motivation_patch": "找到短信背后的发信人。",
                            }
                        ],
                        "location_updates": [],
                        "event_updates": [
                            {
                                "action": "create",
                                "source_chapter": "chapter_002",
                                "summary": "林舟前往咖啡馆赴约。",
                                "involved_characters": ["char_001"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            ]
        )
        extractor = StoryElementExtractor(model)
        progress_events = []
        result = extractor.extract(
            title="雨夜来信",
            chapters=[
                {
                    "id": "chapter_001",
                    "index": 1,
                    "heading": "第一章",
                    "title": "雨夜",
                    "summary": "林舟收到匿名短信。",
                    "analysis": {"summary": "林舟收到匿名短信。"},
                },
                {
                    "id": "chapter_002",
                    "index": 2,
                    "heading": "第二章",
                    "title": "赴约",
                    "summary": "林舟前往老城区咖啡馆。",
                    "analysis": {"summary": "林舟前往老城区咖啡馆。"},
                },
            ],
            on_progress=progress_events.append,
        )

        self.assertEqual(len(model.prompts), 2)
        self.assertEqual(progress_events[0]["phase"], "chapter_processing")
        self.assertEqual(progress_events[0]["chapter_index"], 1)
        self.assertEqual(progress_events[0]["chapter_total"], 2)
        self.assertEqual(progress_events[-1]["phase"], "finished")
        self.assertEqual(progress_events[-1]["character_count"], 1)
        self.assertEqual(progress_events[-1]["event_count"], 2)
        self.assertIn("chapter_001", model.prompts[0])
        self.assertNotIn("chapter_002", model.prompts[0])
        self.assertIn("chapter_002", model.prompts[1])
        self.assertIn("char_001", model.prompts[1])
        self.assertEqual(result["title"], "雨夜来信")
        self.assertEqual(result["characters"][0]["name"], "林舟")
        self.assertIn("小林", result["characters"][0]["aliases"])
        self.assertEqual(result["locations"][0]["id"], "loc_001")
        self.assertEqual(result["events"][0]["source_chapter"], "chapter_001")
        self.assertEqual(result["events"][1]["source_chapter"], "chapter_002")
        self.assertEqual(result["events"][1]["involved_characters"], ["char_001"])

    def test_requires_llm_environment(self):
        with self.assertRaises(LLMConfigError):
            create_llm_client_from_env({})

    def test_supports_openai_provider(self):
        client = create_llm_client_from_env(
            {
                "LLM_PROVIDER": "openai",
                "LLM_API_KEY": "key",
                "LLM_BASE_URL": "https://example.com/v1",
                "LLM_MODEL": "gpt-4o-mini",
            }
        )

        self.assertIsInstance(client, ChatOpenAI)

    def test_supports_anthropic_provider(self):
        client = create_llm_client_from_env(
            {
                "LLM_PROVIDER": "anthropic",
                "LLM_API_KEY": "key",
                "LLM_BASE_URL": "https://example.com",
                "LLM_MODEL": "claude-sonnet-4-5",
            }
        )

        self.assertIsInstance(client, ChatAnthropic)

    def test_reads_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "LLM_PROVIDER=anthropic\nLLM_MODEL='claude-sonnet-4-5'\n",
                encoding="utf-8",
            )

            values = load_env_file(env_path)

        self.assertEqual(values["LLM_PROVIDER"], "anthropic")
        self.assertEqual(values["LLM_MODEL"], "claude-sonnet-4-5")


if __name__ == "__main__":
    unittest.main()
