import re
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
COMMAND_TIMEOUT_SECONDS = 45

BLOCKED_COMMAND_PATTERNS = [
    r"\bsudo\b",
    r"\brm\s+-rf\s+/(?:\s|$)",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+checkout\s+--\s+",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]


def safe_resolve(input_path="."):
    full = (ROOT / input_path).resolve()
    try:
        full.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Path escapes the workspace") from exc
    return full


def assert_safe_command(command):
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command):
            raise ValueError(f"Blocked unsafe command: {command}")


def run_bash(command, cwd="."):
    try:
        assert_safe_command(command)
        safe_cwd = safe_resolve(cwd)
        completed = subprocess.run(
            command,
            cwd=safe_cwd,
            shell=True,
            executable="/bin/bash",
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(safe_cwd.relative_to(ROOT)) or ".",
            "ok": completed.returncode == 0,
            "code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {
            "command": command,
            "cwd": cwd,
            "ok": False,
            "code": 1,
            "stdout": "",
            "stderr": str(exc),
        }


def _git_numstat():
    completed = subprocess.run(
        "git diff --numstat -- .",
        cwd=ROOT,
        shell=True,
        executable="/bin/bash",
        text=True,
        capture_output=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        return {"available": False, "files": {}}
    changes = {}
    for line in completed.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        added, deleted, *path_parts = parts
        path = " ".join(path_parts)
        added_count = int(added) if added.isdigit() else 0
        deleted_count = int(deleted) if deleted.isdigit() else 0
        changes[path] = {
            "added": added_count,
            "deleted": deleted_count,
            "total": added_count + deleted_count,
        }
    return {"available": True, "files": changes}


def get_workspace_info():
    modified = _git_numstat()
    return {"root": str(ROOT), "modified": modified["files"], "gitAvailable": modified["available"]}


def list_files(directory=".", depth=2):
    root = safe_resolve(directory)
    modified = _git_numstat()["files"]
    out = []

    def walk(current, remaining):
        if remaining < 0:
            return
        for entry in sorted(current.iterdir(), key=lambda item: item.name.lower()):
            if entry.name in {"node_modules", ".git", "agent-data", "__pycache__", ".venv"}:
                continue
            rel = str(entry.relative_to(ROOT))
            item_type = "dir" if entry.is_dir() else "file"
            out.append({
                "path": rel,
                "name": entry.name,
                "type": item_type,
                "modified": modified.get(rel),
            })
            if entry.is_dir():
                walk(entry, remaining - 1)

    walk(root, depth)
    return out


def read_workspace_file(file_path):
    full = safe_resolve(file_path)
    if not full.is_file():
        raise ValueError("Path is not a file")
    if full.stat().st_size > 200_000:
        raise ValueError("File is too large to show")
    return full.read_text(encoding="utf-8")


def smoke_test_url(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        title_match = re.search(r"<title>(.*?)</title>", body, re.IGNORECASE)
        return {
            "ok": 200 <= response.status < 300,
            "status": response.status,
            "title": title_match.group(1) if title_match else "",
            "bytes": len(body),
        }
