import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

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
        "git diff HEAD --numstat -- .",
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
        # Binary diffs use '-' instead of line counts, so don't display a false 0-line badge.
        if not added.isdigit() or not deleted.isdigit():
            continue
        path = " ".join(path_parts)
        changes[path] = {
            "added": int(added),
            "deleted": int(deleted),
            "total": int(added) + int(deleted),
        }
    untracked = subprocess.run(
        "git ls-files -z --others --exclude-standard",
        cwd=ROOT,
        shell=True,
        executable="/bin/bash",
        text=True,
        capture_output=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    if untracked.returncode == 0:
        for path in untracked.stdout.split("\0"):
            if not path:
                continue
            try:
                line_count = len((ROOT / path).read_text(encoding="utf-8").splitlines())
            except (OSError, UnicodeDecodeError):
                continue
            changes[path] = {"added": line_count, "deleted": 0, "total": line_count}
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


def smoke_test_url(url, actions=None):
    """Inspect a local site and execute only a small, structured browser action list."""
    if not re.match(r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:/|$)", url):
        return {"available": False, "ok": False, "error": "Browser access is limited to localhost websites."}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "available": False,
            "ok": False,
            "error": "Playwright is not installed. Run python3 -m pip install -r requirements.txt and python3 -m playwright install chromium.",
        }

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as exc:
                return {"available": False, "ok": False, "error": f"Chromium is unavailable: {exc}"}

            try:
                page = browser.new_page()
                def keep_navigation_local(route):
                    request = route.request
                    if request.is_navigation_request() and urlsplit(request.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
                        route.abort()
                    else:
                        route.continue_()
                page.route("**/*", keep_navigation_local)
                page_errors = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                try:
                    response = page.goto(url, wait_until="load", timeout=10_000)
                    # The app publishes this marker after sessions, settings, and files finish loading.
                    page.wait_for_function(
                        "() => document.documentElement.dataset.codingAgentReady !== 'false'",
                        timeout=5_000,
                    )
                    completed_actions = []
                    for action in (actions or [])[:8]:
                        kind = action.get("action")
                        if kind == "wait":
                            duration = max(0, min(int(action.get("milliseconds", 500)), 3000))
                            page.wait_for_timeout(duration)
                            completed_actions.append({"action": kind, "milliseconds": duration})
                            continue
                        selector = str(action.get("selector") or "")[:200]
                        if not selector:
                            continue
                        target = page.locator(selector).first
                        if kind == "click":
                            target.click(timeout=3000)
                        elif kind == "fill":
                            target.fill(str(action.get("value") or "")[:1000], timeout=3000)
                        elif kind == "press":
                            key = str(action.get("key") or "Enter")
                            if key not in {"Enter", "Escape", "Tab", "ArrowDown", "ArrowUp"}:
                                continue
                            target.press(key, timeout=3000)
                        else:
                            continue
                        completed_actions.append({"action": kind, "selector": selector})
                    body = page.locator("body").inner_text(timeout=5_000)
                    status = response.status if response else None
                    return {
                        "available": True,
                        "ok": bool(status and 200 <= status < 400 and not page_errors),
                        "status": status,
                        "url": page.url,
                        "title": page.title(),
                        "headings": page.locator("h1:visible, h2:visible, h3:visible").all_text_contents()[:30],
                        "buttons": page.locator("button:visible").all_text_contents()[:40],
                        "actions": completed_actions,
                        "text": body[:4000],
                        "pageErrors": page_errors,
                    }
                except Exception as exc:
                    return {"available": True, "ok": False, "url": url, "error": str(exc), "pageErrors": page_errors}
            finally:
                browser.close()
    except Exception as exc:
        return {"available": False, "ok": False, "error": str(exc)}
