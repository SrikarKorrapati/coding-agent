import unittest

from app.permissions import apply_permission_mode, fallback_safety_assessment


class PermissionTests(unittest.TestCase):
    def test_fallback_safety_assessment_blocks_destructive_commands(self):
        assessment = fallback_safety_assessment([{"command": "rm -rf /tmp/example", "why": "cleanup"}])
        self.assertEqual(assessment["risk"], "unsafe")
        self.assertFalse(assessment["allowed"])

    def test_permission_modes_enforce_ask_and_approve_all(self):
        safe = fallback_safety_assessment([{"command": "python3 -m unittest discover -s tests", "why": "verify"}])
        self.assertFalse(apply_permission_mode(safe, "ask_every_time")["allowed"])
        self.assertTrue(apply_permission_mode(safe, "safe_only")["allowed"])

        unsafe = fallback_safety_assessment([{"command": "sudo rm -rf /", "why": "bad idea"}])
        self.assertTrue(apply_permission_mode(unsafe, "approve_all")["allowed"])


if __name__ == "__main__":
    unittest.main()
