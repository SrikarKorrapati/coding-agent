import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import llm, storage


class SettingsTests(unittest.TestCase):
    def test_concurrent_session_writes_are_not_lost(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.object(storage, "DATA_DIR", root), patch.object(storage, "STORE_PATH", root / "store.json"):
                storage.ensure_store()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda index: storage.create_session(f"Chat {index}"), range(20)))

                self.assertEqual(len(storage.list_sessions()), 20)

    def test_provider_keys_are_saved_and_merged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.object(storage, "DATA_DIR", root), patch.object(storage, "STORE_PATH", root / "store.json"):
                storage.ensure_store()
                settings = storage.update_settings({
                    "provider": "google",
                    "model": "gemini-2.5-pro",
                    "apiKeys": {"google": "gemini-key", "openai": "openai-key", "anthropic": "claude-key"},
                })

                self.assertEqual(settings["apiKeys"]["google"], "gemini-key")
                self.assertEqual(settings["apiKeys"]["openai"], "openai-key")
                self.assertEqual(settings["apiKeys"]["anthropic"], "claude-key")
                self.assertEqual(storage.get_settings()["provider"], "google")

    def test_legacy_master_key_migrates_to_its_provider(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            legacy_store = {
                "settings": {"provider": "anthropic", "apiKey": "legacy-claude-key"},
                "sessions": {},
                "jobs": {},
            }
            with patch.object(storage, "DATA_DIR", root), patch.object(storage, "STORE_PATH", root / "store.json"):
                (root / "store.json").write_text(json.dumps(legacy_store), encoding="utf-8")
                settings = storage.get_settings()

                self.assertEqual(settings["apiKeys"]["anthropic"], "legacy-claude-key")

    def test_job_approval_can_only_be_claimed_once(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.object(storage, "DATA_DIR", root), patch.object(storage, "STORE_PATH", root / "store.json"):
                storage.ensure_store()
                session = storage.create_session("Approval test")
                job = storage.create_job(session["id"], {"prompt": "Run a command"})
                storage.update_job(job["id"], {
                    "status": "waiting_approval",
                    "approval": {"developer_output": {"commands": [{"command": "true"}]}},
                })

                approved = storage.request_job_approval(job["id"])
                repeated = storage.request_job_approval(job["id"])

        self.assertEqual(approved["status"], "queued")
        self.assertTrue(approved["approvalGranted"])
        self.assertIsNone(repeated)

    def test_claude_uses_the_dedicated_langchain_adapter(self):
        with patch.object(llm, "ChatAnthropic") as chat_anthropic:
            llm.create_chat_model({
                "provider": "anthropic",
                "apiKey": "claude-key",
                "model": "claude-sonnet-5",
                "baseUrl": "https://api.anthropic.com",
            })

        chat_anthropic.assert_called_once_with(
            anthropic_api_key="claude-key",
            model="claude-sonnet-5",
            base_url="https://api.anthropic.com",
        )


if __name__ == "__main__":
    unittest.main()
