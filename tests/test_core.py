import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agents import mode_allows_write, normalize_mode
from app import tools
from app.tools import assert_safe_command, safe_resolve


class CoreTests(unittest.TestCase):
    def test_mode_allows_write_keeps_ask_and_plan_read_only(self):
        self.assertFalse(mode_allows_write("ask"))
        self.assertFalse(mode_allows_write("plan"))
        self.assertTrue(mode_allows_write("agent"))
        self.assertTrue(mode_allows_write("debug"))
        self.assertTrue(mode_allows_write("agent"))

    def test_normalize_mode_falls_back_to_ask(self):
        self.assertEqual(normalize_mode("agent"), "agent")
        self.assertEqual(normalize_mode("unknown"), "ask")

    def test_safe_resolve_rejects_paths_outside_workspace(self):
        with self.assertRaises(ValueError):
            safe_resolve("../../../../etc/passwd")

    def test_assert_safe_command_blocks_destructive_commands(self):
        with self.assertRaises(ValueError):
            assert_safe_command("sudo rm -rf /")
        assert_safe_command("python3 -m unittest discover -s tests")

    def test_modified_line_counts_include_staged_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            tracked = root / "tracked.py"
            tracked.write_text("old\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

            tracked.write_text("one\ntwo\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.py"], cwd=root, check=True)
            tracked.write_text("one\ntwo\nthree\n", encoding="utf-8")
            (root / "new.py").write_text("alpha\nbeta\n", encoding="utf-8")

            with patch.object(tools, "ROOT", root):
                changes = tools._git_numstat()["files"]

        self.assertEqual(changes["tracked.py"], {"added": 3, "deleted": 1, "total": 4})
        self.assertEqual(changes["new.py"], {"added": 2, "deleted": 0, "total": 2})


if __name__ == "__main__":
    unittest.main()
