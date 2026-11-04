import json
import mimetypes
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from app.model_catalog import list_model_catalog
from app.orchestrator import enqueue
from app.storage import (
    create_job,
    create_session,
    delete_session,
    ensure_store,
    get_job,
    get_session,
    get_settings,
    list_sessions,
    update_session,
    update_settings,
)
from app.tools import get_workspace_info, list_files, read_workspace_file, run_bash

ROOT = Path.cwd()
PUBLIC_DIR = ROOT / "public"
PORT = int(os.environ.get("PORT", "4317"))


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        return

    def send_json(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        length = int(self.headers.get("content-length") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route()

    def do_PATCH(self):
        self.route()

    def do_DELETE(self):
        self.route()

    def route(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/"):
                return self.route_api(parsed)
            return self.serve_static(parsed.path)
        except Exception as exc:
            return self.send_json(500, {"error": str(exc)})

    def route_api(self, parsed):
        method = self.command
        path = parsed.path
        query = parse_qs(parsed.query)

        if method == "GET" and path == "/api/sessions":
            return self.send_json(200, list_sessions())

        if method == "POST" and path == "/api/sessions":
            body = self.read_json()
            return self.send_json(201, create_session(body.get("name") or "New Chat"))

        if method == "GET" and path == "/api/settings":
            return self.send_json(200, get_settings())

        if method == "PATCH" and path == "/api/settings":
            return self.send_json(200, update_settings(self.read_json()))

        if method == "GET" and path == "/api/models":
            return self.send_json(200, list_model_catalog())

        if method == "GET" and path == "/api/files":
            return self.send_json(200, list_files((query.get("dir") or ["."])[0], 3))

        if method == "GET" and path == "/api/workspace":
            return self.send_json(200, get_workspace_info())

        if method == "GET" and path == "/api/file":
            file_path = (query.get("path") or [""])[0]
            return self.send_json(200, {"content": read_workspace_file(file_path)})

        if method == "POST" and path == "/api/bash":
            body = self.read_json()
            return self.send_json(200, run_bash(body.get("command", ""), body.get("cwd", ".")))

        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[:2] == ["api", "sessions"]:
            session_id = parts[2]
            if method == "GET":
                session = get_session(session_id)
                return self.send_json(200, session) if session else self.send_json(404, {"error": "Session not found"})
            if method == "PATCH":
                session = update_session(session_id, self.read_json())
                return self.send_json(200, session) if session else self.send_json(404, {"error": "Session not found"})
            if method == "DELETE":
                return self.send_json(200, {"ok": True}) if delete_session(session_id) else self.send_json(404, {"error": "Session not found"})

        if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "prompts" and method == "POST":
            job = create_job(parts[2], self.read_json())
            enqueue(job)
            return self.send_json(202, job)

        if len(parts) == 3 and parts[:2] == ["api", "jobs"] and method == "GET":
            job = get_job(parts[2])
            return self.send_json(200, job) if job else self.send_json(404, {"error": "Job not found"})

        return self.send_json(404, {"error": "Not found"})

    def serve_static(self, raw_path):
        requested = "/index.html" if raw_path == "/" else raw_path
        file_path = (PUBLIC_DIR / unquote(requested.lstrip("/"))).resolve()
        if PUBLIC_DIR not in file_path.parents and file_path != PUBLIC_DIR:
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", mimetypes.guess_type(str(file_path))[0] or "application/octet-stream")
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    ensure_store()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Local coding agent running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down local coding agent.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
