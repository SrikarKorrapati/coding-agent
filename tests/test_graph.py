import unittest
from unittest.mock import patch

from app.agent_graph import (
    browser_tester_node,
    create_agent_graph,
    normalize_safety_assessment,
    route_after_browser_test,
    route_after_edit,
    route_after_read_only,
    route_after_safety,
    run_agent_graph,
    safety_node,
)


class GraphTests(unittest.TestCase):
    def test_langgraph_workflow_compiles(self):
        graph = create_agent_graph()
        self.assertTrue(callable(getattr(graph, "invoke", None)))

    def test_safety_agent_cannot_downgrade_a_heuristic_unsafe_command(self):
        command = {"command": "sudo rm -rf /tmp/work", "why": "cleanup"}
        model_assessment = {
            "risk": "safe",
            "allowed": True,
            "commandAssessments": [{"command": command["command"], "risk": "safe", "reason": "Looks fine."}],
        }

        result = normalize_safety_assessment(model_assessment, [command], "safe_only")

        self.assertEqual(result["risk"], "unsafe")
        self.assertFalse(result["allowed"])

    def test_failed_edit_routes_back_to_developer_until_retry_limit(self):
        self.assertEqual(route_after_edit({"needs_correction": True, "correction_attempts": 1}), "developer")
        self.assertEqual(route_after_edit({"needs_correction": True, "correction_attempts": 2}), "deployer")

    def test_failed_local_site_check_is_reported_for_correction(self):
        state = {
            "input": {"mode": "agent", "prompt": "Fix the page at http://localhost:5173"},
            "session": {"settings": {"apiKey": ""}},
            "verification_results": [],
            "correction_attempts": 0,
        }
        with patch("app.agent_graph.smoke_test_url", side_effect=OSError("connection refused")), patch(
            "app.agent_graph.call_agent", return_value={"ok": False, "content": "No API key configured.", "json": None}
        ):
            result = browser_tester_node(state)

        self.assertTrue(result["needs_correction"])
        self.assertEqual(result["correction_attempts"], 1)
        self.assertEqual(route_after_browser_test({**state, **result}), "developer")

    def test_read_only_chat_can_request_a_local_browser_check(self):
        state = {"browser_url": "http://localhost:4317", "input": {"mode": "ask"}}
        self.assertEqual(route_after_read_only(state), "browserTester")
        self.assertEqual(route_after_browser_test({"input": {"mode": "ask"}, "needs_correction": True}), "end")

    def test_ask_every_time_pauses_with_the_exact_commands_for_approval(self):
        command = {"command": "python3 -m unittest discover -s tests", "why": "Verify the change."}
        state = {
            "session": {"settings": {}},
            "input": {"permissionMode": "ask_every_time"},
            "developer_output": {"commands": [command]},
            "final_result": "",
        }
        safety_response = {
            "ok": True,
            "json": {
                "risk": "safe",
                "allowed": True,
                "reason": "Local test command.",
                "commandAssessments": [{"command": command["command"], "risk": "safe", "reason": "Test."}],
            },
        }
        with patch("app.agent_graph.call_agent", return_value=safety_response):
            result = safety_node(state)

        self.assertTrue(result["awaiting_approval"])
        self.assertFalse(result["safety_assessment"]["allowed"])
        self.assertEqual(route_after_safety(result), "approval")

    def test_approved_job_runs_saved_commands_without_regenerating_them(self):
        session = {"settings": {}}
        input_data = {
            "mode": "agent",
            "prompt": "Make the requested change.",
            "selectedCode": "",
            "permissionMode": "ask_every_time",
        }
        approval_state = {
            "plan": {"tasks": []},
            "developer_output": {
                "summary": "Approved edit",
                "commands": [{"command": "echo approved", "why": "Apply the edit."}],
                "verification": [],
            },
            "edit_results": [],
            "verification_results": [],
            "correction_attempts": 0,
        }
        with patch("app.agent_graph.run_bash", return_value={"command": "echo approved", "ok": True, "stdout": "approved", "stderr": ""}) as run_bash, patch(
            "app.agent_graph.call_agent", return_value={"ok": False, "content": "No key configured.", "json": None}
        ):
            result = run_agent_graph(session, input_data, approval_state=approval_state)

        run_bash.assert_called_once_with("echo approved", ".")
        self.assertFalse(result.get("awaiting_approval"))


if __name__ == "__main__":
    unittest.main()
