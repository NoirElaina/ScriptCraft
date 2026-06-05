import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from llm import (
    AnthropicClient,
    LLMConfigError,
    OpenAICompatibleClient,
    create_llm_client_from_env,
)
from llm.env_loader import load_env_file
from story_elements import StoryElementExtractor


class FakeClient:
    def complete_json(self, messages):
        return {
            "characters": [
                {
                    "id": "char_001",
                    "name": "林舟",
                    "role": "protagonist",
                    "description": "年轻记者",
                }
            ],
            "locations": [
                {
                    "id": "loc_001",
                    "name": "老城区咖啡馆",
                    "description": "雨夜中的见面地点",
                }
            ],
            "events": [
                {
                    "id": "event_001",
                    "source_chapter": "chapter_001",
                    "summary": "林舟收到匿名短信。",
                    "involved_characters": ["char_001"],
                }
            ],
        }


class StoryElementTests(unittest.TestCase):
    def test_extracts_ai_story_elements(self):
        extractor = StoryElementExtractor(FakeClient())
        result = extractor.extract(
            title="雨夜来信",
            chapters=[
                {
                    "id": "chapter_001",
                    "index": 1,
                    "heading": "第一章",
                    "title": "雨夜",
                    "content": "林舟收到匿名短信。",
                }
            ],
        )

        self.assertEqual(result["title"], "雨夜来信")
        self.assertEqual(result["characters"][0]["name"], "林舟")
        self.assertEqual(result["locations"][0]["id"], "loc_001")
        self.assertEqual(result["events"][0]["source_chapter"], "chapter_001")

    def test_requires_llm_environment(self):
        with self.assertRaises(LLMConfigError):
            create_llm_client_from_env({})

    def test_supports_openai_provider(self):
        client = create_llm_client_from_env(
            {
                "LLM_PROVIDER": "openai",
                "LLM_API_KEY": "key",
                "LLM_MODEL": "gpt-4o-mini",
            }
        )

        self.assertIsInstance(client, OpenAICompatibleClient)

    def test_supports_anthropic_provider(self):
        client = create_llm_client_from_env(
            {
                "LLM_PROVIDER": "anthropic",
                "ANTHROPIC_API_KEY": "key",
                "ANTHROPIC_MODEL": "claude-sonnet-4-5",
            }
        )

        self.assertIsInstance(client, AnthropicClient)

    def test_reads_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "LLM_PROVIDER=anthropic\nANTHROPIC_MODEL='claude-sonnet-4-5'\n",
                encoding="utf-8",
            )

            values = load_env_file(env_path)

        self.assertEqual(values["LLM_PROVIDER"], "anthropic")
        self.assertEqual(values["ANTHROPIC_MODEL"], "claude-sonnet-4-5")


if __name__ == "__main__":
    unittest.main()
