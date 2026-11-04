import threading

from app.agents import AGENTS, normalize_mode
from app.agent_graph import run_agent_graph
from app.model_catalog import PROVIDERS, default_model_for, normalize_provider
from app.storage import (
    add_job_event,
    append_job_stream,
    append_history,
    append_history_entries,
    auto_name_session,
    get_job,
    get_session,
    get_settings,
    list_sessions,
    remove_job_from_queue,
    update_job,
)

SESSION_WORKERS = set()
WORKERS_LOCK = threading.Lock()


def _start_worker_locked(session_id):
    SESSION_WORKERS.add(session_id)
    threading.Thread(target=_run_session_queue, args=(session_id,), daemon=True).start()


def enqueue(job):
    session_id = job["sessionId"]
    with WORKERS_LOCK:
        if session_id not in SESSION_WORKERS:
            _start_worker_locked(session_id)


def resume_queued_jobs():
    """Resume saved queued prompts when the local server starts again."""
    for session in list_sessions():
        for job_id in session.get("queue", []):
            job = get_job(job_id)
            if not job:
                remove_job_from_queue(session["id"], job_id)
                continue
            if job.get("status") == "running":
                result = "The server restarted while this prompt was running. Inspect the workspace, then submit it again if work remains."
                update_job(job_id, {"status": "failed", "result": result})
                append_history(session["id"], {"role": "assistant", "content": result})
                remove_job_from_queue(session["id"], job_id)
                continue
            if job.get("status") == "queued":
                enqueue(job)
                break
            if job.get("status") == "waiting_approval":
                break


def _drain_session_queue(session_id):
    """Process each session's persisted jobs in queue order, pausing on approval."""
    while True:
        session = get_session(session_id)
        if not session or not session.get("queue"):
            return
        job_id = session["queue"][0]
        job = get_job(job_id)
        if not job:
            remove_job_from_queue(session_id, job_id)
            continue
        if job["status"] in {"done", "failed", "waiting_approval"}:
            if job["status"] == "waiting_approval":
                return
            remove_job_from_queue(session_id, job_id)
            continue
        if job["status"] != "queued":
            return
        process_job(job_id)
        if (get_job(job_id) or {}).get("status") == "waiting_approval":
            return


def _run_session_queue(session_id):
    try:
        _drain_session_queue(session_id)
    finally:
        with WORKERS_LOCK:
            SESSION_WORKERS.discard(session_id)
            session = get_session(session_id)
            if session and session.get("queue"):
                next_job = get_job(session["queue"][0])
                if next_job and next_job.get("status") in {"queued", "done", "failed"}:
                    _start_worker_locked(session_id)


def event(job_id, agent, message, data=None):
    add_job_event(job_id, {"agent": agent, "message": message, "data": data or {}})


def process_job(job_id):
    job = update_job(job_id, {"status": "running"})
    if not job:
        return
    waiting_for_approval = False
    session = get_session(job["sessionId"])
    if not session:
        return

    settings = get_settings()
    provider = normalize_provider(job["input"].get("provider") or settings.get("provider"))
    model = job["input"].get("model") or (
        settings.get("model") if provider == settings.get("provider") else default_model_for(provider)
    )
    api_key_enabled = (settings.get("apiKeyEnabled") or {}).get(provider, True)
    api_key = (settings.get("apiKeys") or {}).get(provider) if api_key_enabled else ""
    if not api_key and provider == settings.get("provider"):
        api_key = settings.get("apiKey", "") if api_key_enabled else ""
    base_url = PROVIDERS[provider]["baseUrl"]
    if provider == "openai" and settings.get("baseUrlOverrideEnabled"):
        base_url = settings.get("baseUrl") or base_url
    session["settings"] = {
        **settings,
        "provider": provider,
        "model": model,
        "apiKey": api_key,
        "baseUrl": base_url,
    }
    input_data = {
        "mode": normalize_mode(job["input"].get("mode")),
        "prompt": job["input"].get("prompt") or "",
        "selectedCode": job["input"].get("selectedCode") or "",
        "provider": provider,
        "model": model,
        "permissionMode": job["input"].get("permissionMode") or "safe_only",
    }

    try:
        event(job_id, "system", "Starting queued prompt.", {"agents": [agent["name"] for agent in AGENTS]})
        pending_approval = job.get("approval") if job.get("approvalGranted") else None
        graph_result = run_agent_graph(
            session,
            input_data,
            approval_state=pending_approval,
            on_token=lambda token: append_job_stream(job_id, token),
        )
        for graph_event in graph_result.get("events", []):
            event(job_id, graph_event["agent"], graph_event["message"], graph_event.get("data"))

        if graph_result.get("awaiting_approval"):
            auto_name_session(session["id"], input_data["prompt"])
            approval_state = {
                key: graph_result[key]
                for key in ("plan", "developer_output", "safety_assessment", "edit_results", "verification_results", "correction_attempts")
                if key in graph_result
            }
            event(job_id, "safety", "Waiting for your approval before running these commands.", {
                "commands": graph_result.get("developer_output", {}).get("commands", []),
            })
            update_job(job_id, {
                "status": "waiting_approval",
                "result": "Commands are waiting for your approval.",
                "approval": approval_state,
                "approvalGranted": False,
            })
            waiting_for_approval = True
            return

        result = graph_result.get("final_result") or "The agent graph completed without a final message."
        auto_name_session(session["id"], input_data["prompt"])
        append_history_entries(session["id"], [{
            "role": "user",
            "mode": input_data["mode"],
            "prompt": input_data["prompt"],
            "selectedCode": input_data["selectedCode"],
        }, {"role": "assistant", "mode": input_data["mode"], "content": result}])
        update_job(job_id, {"status": "done", "result": result, "approval": None, "approvalGranted": False})
    except Exception as exc:
        failure = str(exc)
        event(job_id, "system", "Job failed.", {"error": failure})
        # Keep failed prompts and their final error visible in the persisted chat transcript.
        try:
            auto_name_session(session["id"], input_data["prompt"])
            append_history_entries(session["id"], [{
                "role": "user",
                "mode": input_data["mode"],
                "prompt": input_data["prompt"],
                "selectedCode": input_data["selectedCode"],
            }, {"role": "assistant", "mode": input_data["mode"], "content": failure}])
        except Exception:
            pass
        update_job(job_id, {"status": "failed", "result": failure, "approval": None, "approvalGranted": False})
    finally:
        if not waiting_for_approval:
            remove_job_from_queue(job["sessionId"], job_id)
