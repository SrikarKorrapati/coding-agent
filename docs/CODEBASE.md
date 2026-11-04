# Codebase Documentation

## Purpose

This project is a minimal Python local coding agent. It keeps the implementation small while covering the requested core behavior:

- LangChain Python model calls through `ChatOpenAI`.
- LangGraph Python orchestration through `StateGraph`.
- Persistent chats with a shared master API key.
- Provider-aware model lists in the UI.
- Prompt queueing per session.
- Four modes: Ask, Plan, Debug, and Agent.
- AI agent nodes for Planner, Developer, Safety, Reviewer, Tester, Browser Tester, and Deployer.
- File creation and modification through bash commands.
- Selected-code context pasted into the prompt composer.
- Delete, rename, and automatic first-prompt chat naming.
- Right-side workspace file panel with fresh file reads and git-based modified-line counts.

## File Map

- `app/server.py`: HTTP server, static file hosting, and JSON API routes.
- `app/orchestrator.py`: Prompt queue processing and LangGraph job execution.
- `app/agent_graph.py`: LangGraph state graph, AI agent nodes, conditional routing, and tool nodes.
- `app/agents.py`: Mode and agent definitions.
- `app/llm.py`: LangChain `ChatOpenAI` setup, agent calls, and fallback planning.
- `app/model_catalog.py`: Provider and model dropdown catalog.
- `app/permissions.py`: Permission modes and fallback command risk heuristics.
- `app/storage.py`: JSON-backed sessions, history, jobs, settings, and queue state.
- `app/tools.py`: Workspace-safe bash execution, file listing, file reading, git diff summary, and URL smoke checks.
- `public/index.html`: Minimal UI structure.
- `public/styles.css`: UI styling.
- `public/app.js`: Browser-side session, settings, prompt queue, model dropdown, and polling logic.
- `tests/`: Python `unittest` coverage for core behavior, permissions, and LangGraph compilation.

## Runtime Flow

1. The user creates or selects a chat.
2. The user chooses a mode, optionally pastes selected code, selects provider/model/permissions, then queues a prompt.
3. The server creates a job and adds it to the session queue.
4. `orchestrator.py` processes one job per session at a time.
5. The job enters `agent_graph.py`, a LangGraph `StateGraph`.
6. Planner breaks the prompt into smaller tasks.
7. Ask and Plan modes route to read-only workspace and reviewer nodes.
8. Debug and Agent modes route to Developer, Safety, bash tool, Reviewer, Tester, Browser Tester, and Deployer nodes.
9. Safety assesses command risk before execution and applies the selected permission mode.
10. If verification fails, LangGraph routes back to Developer for a corrective pass.
11. If a localhost URL is mentioned, Browser Tester performs an HTTP smoke test.
12. The final answer and all graph events are stored in session history and job events.

## API Routes

- `GET /api/sessions`: list sessions.
- `POST /api/sessions`: create a session.
- `GET /api/sessions/:id`: read one session.
- `PATCH /api/sessions/:id`: rename or update session metadata.
- `DELETE /api/sessions/:id`: delete a session, its history, and its jobs.
- `GET /api/settings`: read the master API settings.
- `PATCH /api/settings`: update the master API settings.
- `GET /api/models`: read provider/model dropdown data.
- `POST /api/sessions/:id/prompts`: queue a prompt.
- `GET /api/jobs/:id`: poll job status and agent events.
- `GET /api/files`: list workspace files.
- `GET /api/workspace`: read the current working path and git diff summary.
- `GET /api/file?path=...`: read a workspace file.
- `POST /api/bash`: run a bash command in the workspace.

## Current Limits

- The browser tester is currently an HTTP smoke test, not full Playwright control.
- API keys are stored in plain local JSON.
- Bash safety is a lightweight blocklist plus Safety-agent classification, not a full sandbox.
- Direct Anthropic API execution is listed in the model picker but not yet implemented; use OpenRouter or another OpenAI-compatible gateway for those models.
