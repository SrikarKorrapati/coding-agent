# Codebase Guide

## Purpose

This is a small local coding agent built with Python, LangChain, and LangGraph. The browser UI is plain HTML, CSS, and JavaScript. It uses one JSON store for chat and job persistence, and keeps model roles as nodes in one LangGraph workflow.

## Main Components

- `app/server.py` serves the UI and JSON API.
- `app/storage.py` owns the locked, atomic JSON store for chats, memory, archived history, queued jobs, and progress checkpoints.
- `app/orchestrator.py` processes each chat's prompt queue in order, handles pause/resume, and saves the final transcript.
- `app/agent_graph.py` defines the LangGraph nodes and routes: Planner, Developer, Safety, Reviewer, Tester, Browser Tester, and Deployer.
- `app/llm.py` calls supported providers through LangChain and streams user-facing text.
- `app/tools.py` contains workspace-safe file/bash helpers and structured localhost browser checks.
- `app/permissions.py` combines shell-command risk heuristics with the selected permission mode.
- `public/index.html`, `public/styles.css`, and `public/app.js` implement the minimal chat UI.
- `tests/` contains focused Python unit tests for storage, queueing, permissions, workspace tools, and graph routing.

## Request Flow

1. The UI posts a prompt to `/api/sessions/:id/prompts`. Selected code includes its source path. An optional localhost URL requests browser inspection.
2. `storage.py` persists the job and adds it to the chat's FIFO queue.
3. `orchestrator.py` starts one worker per chat and calls `run_agent_graph`.
4. `agent_graph.py` gathers workspace context, then routes Ask and Plan requests to read-only responses. Debug and Agent requests can pass through planning, command safety, bash, review, verification, browser checks, and a correction pass.
5. User-facing tokens, status, activity, and compact progress checkpoints are persisted for polling. Pause takes effect at a node or streaming-token boundary; it does not kill a shell command or an in-flight provider request.
6. Completed prompts and responses are appended to chat history. Each chat separately stores editable long-term memory and a compaction summary.

## Sessions and Context

- Chats persist in `work/agent-data/store.json` across server restarts.
- **Fork chat** copies recent transcript context and memory into a new chat with a parent reference.
- **Compact chat** summarizes messages older than the latest eight, preserves the full older transcript in `historyArchive`, and injects the summary into future agent context.
- The user can edit long-term memory in the chat composer. The graph includes it in planning, Q&A, and development prompts.
- Each LangGraph node writes a small checkpoint marker to its job. These markers describe workflow progress; they do not snapshot or roll back workspace files.

## Browser Access

The Browser Tester uses Playwright Chromium for localhost URLs only. It inspects page text and errors. When the prompt asks for interactions, the Browser Tester may produce up to eight structured click, fill, press, or wait actions. It cannot run page JavaScript, and cross-site top-level navigation is blocked. Read-only modes report browser results without triggering file edits; Debug and Agent can send a failed check back to Developer.

## API Routes

- `GET/POST /api/sessions`: list or create chats.
- `GET/PATCH/DELETE /api/sessions/:id`: load, rename/update, or delete a chat.
- `POST /api/sessions/:id/fork`: create a new chat from recent context and memory.
- `POST /api/sessions/:id/compact`: summarize and archive older messages.
- `POST /api/sessions/:id/prompts`: queue a prompt.
- `GET /api/jobs/:id`: poll status, stream text, events, and checkpoints.
- `POST /api/jobs/:id/approve`: approve the saved command batch.
- `POST /api/jobs/:id/pause` and `/resume`: pause or resume a queued/running job.
- `GET/PATCH /api/settings`: read or update shared model and API-key settings.
- `GET /api/models`: list provider model choices.
- `GET /api/files`, `/api/workspace`, and `/api/file`: inspect files and workspace status.
- `POST /api/bash`: run a workspace-safe bash command helper.

## Run and Verify

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
python3 -m app.server
python3 -m unittest discover -s tests
```

Open `http://localhost:4317`. The server binds to `127.0.0.1` by default. Provider keys and chat data are stored locally in plain JSON for this prototype.
