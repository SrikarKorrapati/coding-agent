import unittest
from unittest.mock import patch

from app import orchestrator


class OrchestratorTests(unittest.TestCase):
    def test_session_worker_processes_prompts_in_fifo_order(self):
        session = {"id": "session-1", "queue": ["job-1", "job-2"]}
        jobs = {
            "job-1": {"id": "job-1", "status": "queued"},
            "job-2": {"id": "job-2", "status": "queued"},
        }
        processed = []

        def process(job_id):
            processed.append(job_id)
            jobs[job_id]["status"] = "done"
            session["queue"].remove(job_id)

        with patch.object(orchestrator, "get_session", return_value=session), patch.object(
            orchestrator, "get_job", side_effect=lambda job_id: jobs.get(job_id)
        ), patch.object(orchestrator, "process_job", side_effect=process):
            orchestrator._drain_session_queue("session-1")

        self.assertEqual(processed, ["job-1", "job-2"])
        self.assertEqual(session["queue"], [])

    def test_session_worker_pauses_at_a_job_waiting_for_approval(self):
        session = {"id": "session-1", "queue": ["job-1", "job-2"]}
        jobs = {
            "job-1": {"id": "job-1", "status": "waiting_approval"},
            "job-2": {"id": "job-2", "status": "queued"},
        }

        with patch.object(orchestrator, "get_session", return_value=session), patch.object(
            orchestrator, "get_job", side_effect=lambda job_id: jobs.get(job_id)
        ), patch.object(orchestrator, "process_job") as process:
            orchestrator._drain_session_queue("session-1")

        process.assert_not_called()
        self.assertEqual(session["queue"], ["job-1", "job-2"])

    def test_session_worker_keeps_a_paused_job_in_its_queue(self):
        session = {"id": "session-1", "queue": ["job-1", "job-2"]}
        jobs = {
            "job-1": {"id": "job-1", "status": "paused"},
            "job-2": {"id": "job-2", "status": "queued"},
        }

        with patch.object(orchestrator, "get_session", return_value=session), patch.object(
            orchestrator, "get_job", side_effect=lambda job_id: jobs.get(job_id)
        ), patch.object(orchestrator, "process_job") as process:
            orchestrator._drain_session_queue("session-1")

        process.assert_not_called()
        self.assertEqual(session["queue"], ["job-1", "job-2"])


if __name__ == "__main__":
    unittest.main()
