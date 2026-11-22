import os
import unittest
from unittest.mock import patch

from app.config.config import Settings


class ModelProviderConfigTests(unittest.TestCase):
    def test_defaults_chat_and_analysis_to_openai_without_changing_embeddings(self):
        environment = {
            "OPENAI_API_KEY": "test-openai-key",
            "GROQ_API_KEY": "test-groq-key",
            "GOOGLE_API_KEY": "test-google-key",
            "HF_TOKEN": "test-huggingface-token",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.llm_provider, "openai")
        self.assertEqual(settings.chat_provider, "openai")
        self.assertEqual(settings.embedding_provider, "huggingface")

    def test_requires_openai_key_instead_of_falling_back_to_another_llm_provider(self):
        environment = {
            "GROQ_API_KEY": "test-groq-key",
            "GOOGLE_API_KEY": "test-google-key",
            "HF_TOKEN": "test-huggingface-token",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY required"):
                Settings.from_env()
