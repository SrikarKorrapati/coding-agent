import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from uuid import uuid4

from app.model_catalog import default_model_for, normalize_provider

ROOT = Path.cwd()
DATA_DIR = ROOT / "work" / "agent-data"
STORE_PATH = DATA_DIR / "store.json"
LOCK = threading.RLock()

EMPTY_STORE = {
    "settings": {
        "provider": "openai",
        "baseUrl": "https://api.openai.com/v1",
        "model": "gpt-6.1-sol",
        "apiKey": "",
        "apiKeys": {
            "google": "",
            "openai": "",
            "anthropic": "",
        },
    },
    "sessions": {},
    "jobs": {},
}


def store_transaction(function):
    """Keep each read-modify-write operation atomic across concurrent job threads."""
    @wraps(function)
    def locked(*args, **kwargs):
        with LOCK:
            return function(*args, **kwargs)
    return locked


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_store():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        save_store(deepcopy(EMPTY_STORE))


def load_store():
    with LOCK:
        ensure_store()
        store = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        migrated_settings = store.get("settings")
        if not migrated_settings:
            migrated_settings = next(
                (session.get("settings") for session in store.get("sessions", {}).values() if session.get("settings")),
                {},
            )
        merged = deepcopy(EMPTY_STORE)
        merged.update(store)
        settings = {**EMPTY_STORE["settings"], **(migrated_settings or {})}
        settings["apiKeys"] = {**EMPTY_STORE["settings"]["apiKeys"], **(migrated_settings or {}).get("apiKeys", {})}
        legacy_provider = normalize_provider(settings.get("provider"))
        if settings.get("apiKey") and not settings["apiKeys"].get(legacy_provider):
            settings["apiKeys"][legacy_provider] = settings["apiKey"]
        merged["settings"] = settings
        return merged


def save_store(store):
    with LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary_path = STORE_PATH.with_suffix(STORE_PATH.suffix + ".tmp")
        temporary_path.write_text(json.dumps(store, indent=2), encoding="utf-8")
        temporary_path.replace(STORE_PATH)


def list_sessions():
    store = load_store()
    return sorted(store["sessions"].values(), key=lambda item: item["updatedAt"], reverse=True)


@store_transaction
def create_session(name="New Chat"):
    store = load_store()
    stamp = now_iso()
    session = {
        "id": str(uuid4()),
        "name": name,
        "isAutoNamed": name in {"New Chat", "Untitled session"},
        "createdAt": stamp,
        "updatedAt": stamp,
        "history": [],
        "queue": [],
    }
    store["sessions"][session["id"]] = session
    save_store(store)
    return session


def get_session(session_id):
    return load_store()["sessions"].get(session_id)


@store_transaction
def update_session(session_id, patch):
    store = load_store()
    session = store["sessions"].get(session_id)
    if not session:
        return None
    session.update(patch)
    session["updatedAt"] = now_iso()
    save_store(store)
    return session


@store_transaction
def delete_session(session_id):
    store = load_store()
    if session_id not in store["sessions"]:
        return False
    del store["sessions"][session_id]
    store["jobs"] = {job_id: job for job_id, job in store["jobs"].items() if job.get("sessionId") != session_id}
    save_store(store)
    return True


def get_settings():
    return load_store()["settings"]


@store_transaction
def update_settings(settings):
    store = load_store()
    provider = normalize_provider(settings.get("provider") or store["settings"].get("provider"))
    model = settings.get("model") or store["settings"].get("model") or default_model_for(provider)
    api_keys = {**store["settings"].get("apiKeys", {}), **settings.get("apiKeys", {})}
    legacy_key = settings.get("apiKey", store["settings"].get("apiKey", ""))
    if legacy_key and ("apiKeys" not in settings or provider not in {"google", "openai", "anthropic"}):
        api_keys[provider] = legacy_key
    store["settings"] = {
        **store["settings"],
        **settings,
        "apiKey": legacy_key,
        "apiKeys": api_keys,
        "provider": provider,
        "model": model,
    }
    save_store(store)
    return store["settings"]


@store_transaction
def auto_name_session(session_id, prompt):
    store = load_store()
    session = store["sessions"].get(session_id)
    if not session or not session.get("isAutoNamed") or session.get("history"):
        return session
    clean = " ".join("".join(ch for ch in prompt if ch.isalnum() or ch in {" ", "-", "_"}).split())
    words = clean.split()[:6]
    session["name"] = " ".join(words) if words else "New Chat"
    session["updatedAt"] = now_iso()
    save_store(store)
    return session


@store_transaction
def append_history(session_id, entry):
    store = load_store()
    session = store["sessions"].get(session_id)
    if not session:
        return None
    session["history"].append({"id": str(uuid4()), "at": now_iso(), **entry})
    session["updatedAt"] = now_iso()
    save_store(store)
    return session


@store_transaction
def create_job(session_id, input_data):
    store = load_store()
    session = store["sessions"].get(session_id)
    if not session:
        raise ValueError("Session not found")
    stamp = now_iso()
    job = {
        "id": str(uuid4()),
        "sessionId": session_id,
        "status": "queued",
        "input": input_data,
        "events": [],
        "result": None,
        "createdAt": stamp,
        "updatedAt": stamp,
    }
    store["jobs"][job["id"]] = job
    session["queue"].append(job["id"])
    session["updatedAt"] = stamp
    save_store(store)
    return job


def get_job(job_id):
    return load_store()["jobs"].get(job_id)


@store_transaction
def update_job(job_id, patch):
    store = load_store()
    job = store["jobs"].get(job_id)
    if not job:
        return None
    job.update(patch)
    job["updatedAt"] = now_iso()
    save_store(store)
    return job


@store_transaction
def request_job_approval(job_id):
    """Atomically queue a paused job once the user approves its exact command batch."""
    store = load_store()
    job = store["jobs"].get(job_id)
    if not job or job.get("status") != "waiting_approval" or not job.get("approval"):
        return None
    job["status"] = "queued"
    job["approvalGranted"] = True
    job["updatedAt"] = now_iso()
    save_store(store)
    return job


@store_transaction
def add_job_event(job_id, event):
    store = load_store()
    job = store["jobs"].get(job_id)
    if not job:
        return None
    job["events"].append({"id": str(uuid4()), "at": now_iso(), **event})
    job["updatedAt"] = now_iso()
    save_store(store)
    return job


@store_transaction
def remove_job_from_queue(session_id, job_id):
    store = load_store()
    session = store["sessions"].get(session_id)
    if not session:
        return
    session["queue"] = [item for item in session["queue"] if item != job_id]
    session["updatedAt"] = now_iso()
    save_store(store)
