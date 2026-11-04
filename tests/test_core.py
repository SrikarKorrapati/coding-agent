import unittest

from app.agents import mode_allows_write, normalize_mode
from app.tools import assert_safe_command, safe_resolve


class CoreTests(unittest.TestCase):
    def test_mode_allows_write_keeps_ask_and_plan_read_only(self):
        self.assertFalse(mode_allows_write("ask", "modify files"))
        self.assertFalse(mode_allows_write("plan", "modify files"))
        self.assertTrue(mode_allows_write("agent", "modify files"))
        self.assertTrue(mode_allows_write("debug", "modify files"))
        self.assertFalse(mode_allows_write("agent", "show me a snippet"))

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


if __name__ == "__main__":
    unittest.main()
