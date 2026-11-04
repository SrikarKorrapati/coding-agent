import threading

from app.agents import AGENTS, normalize_mode
from app.agent_graph import run_agent_graph
from app.model_catalog import normalize_provider
from app.storage import (
    add_job_event,
    append_history,
    auto_name_session,
    get_session,
    get_settings,
    remove_job_from_queue,
    update_job,
)

SESSION_LOCKS = {}
LOCKS_LOCK = threading.Lock()


def _session_lock(session_id):
    with LOCKS_LOCK:
        if session_id not in SESSION_LOCKS:
            SESSION_LOCKS[session_id] = threading.Lock()
        return SESSION_LOCKS[session_id]


def enqueue(job):
    thread = threading.Thread(target=_run_queued_job, args=(job,), daemon=True)
    thread.start()


def _run_queued_job(job):
    with _session_lock(job["sessionId"]):
        process_job(job["id"])


def event(job_id, agent, message, data=None):
    add_job_event(job_id, {"agent": agent, "message": message, "data": data or {}})


def process_job(job_id):
    job = update_job(job_id, {"status": "running"})
    if not job:
        return
    session = get_session(job["sessionId"])
    if not session:
        return

    settings = get_settings()
    provider = normalize_provider(job["input"].get("provider") or settings.get("provider"))
    session["settings"] = {**settings, "provider": provider, "model": job["input"].get("model") or settings.get("model")}
    input_data = {
        "mode": normalize_mode(job["input"].get("mode")),
        "prompt": job["input"].get("prompt") or "",
        "selectedCode": job["input"].get("selectedCode") or "",
        "provider": provider,
        "model": session["settings"]["model"],
        "permissionMode": job["input"].get("permissionMode") or "safe_only",
    }

    try:
        event(job_id, "system", "Starting queued prompt.", {"agents": [agent["name"] for agent in AGENTS]})
        graph_result = run_agent_graph(session, input_data)
        for graph_event in graph_result.get("events", []):
            event(job_id, graph_event["agent"], graph_event["message"], graph_event.get("data"))

        result = graph_result.get("final_result") or "The agent graph completed without a final message."
        auto_name_session(session["id"], input_data["prompt"])
        append_history(session["id"], {
            "role": "user",
            "mode": input_data["mode"],
            "prompt": input_data["prompt"],
            "selectedCode": input_data["selectedCode"],
        })
        append_history(session["id"], {"role": "assistant", "mode": input_data["mode"], "content": result})
        update_job(job_id, {"status": "done", "result": result})
    except Exception as exc:
        event(job_id, "system", "Job failed.", {"error": str(exc)})
        update_job(job_id, {"status": "failed", "result": str(exc)})
    finally:
        remove_job_from_queue(job["sessionId"], job_id)
