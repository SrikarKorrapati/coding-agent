# Codebase Documentation

## Purpose

This project is a minimal Python local coding agent. It keeps the implementation small while covering the requested core behavior:

- LangChain Python model calls through `ChatOpenAI` and `ChatAnthropic`.
- LangGraph Python orchestration through `StateGraph`.
- Persistent chats with shared provider API keys, per-key enable switches, and model defaults.
- Provider-aware model lists in the UI.
- Persistent prompt queues processed in FIFO order per session.
- Four modes: Ask, Plan, Debug, and Agent. Plan mode returns editable-in-chat steps with verification notes and uses recent conversation context for revisions.
- Chat-style transcript with live streamed assistant replies.
- AI agent nodes for Planner, Developer, Safety, Reviewer, Tester, Browser Tester, and Deployer; the Tester evaluates command evidence and sends supported failures back for correction.
- File creation and modification through bash commands.
- Selected-code context pasted into the prompt composer.
- One prompt box that extracts fenced code blocks as selected-code context.
- Delete, rename, and automatic first-prompt chat naming.
- Right-side workspace file panel with fresh file reads and line counts for staged, unstaged, and new text files.
- Explicit command approval for the “Ask every time” permission mode.

## File Map

- `app/server.py`: HTTP server, static file hosting, and JSON API routes.
- `app/orchestrator.py`: Prompt queue processing and LangGraph job execution.
- `app/agent_graph.py`: LangGraph state graph, AI agent nodes, conditional routing, and tool nodes.
- `app/agents.py`: Mode and agent definitions.
- `app/llm.py`: LangChain provider integrations, agent calls, and fallback planning.
- `app/model_catalog.py`: Provider and model dropdown catalog.
- `app/permissions.py`: Permission modes and fallback command risk heuristics.
- `app/storage.py`: JSON-backed sessions, history, jobs, settings, and queue state.
- `app/tools.py`: Workspace-safe bash execution, file listing, file reading, git diff summary, and Chromium page checks.
- `public/index.html`: Minimal UI structure and Home/Settings navigation.
- `public/styles.css`: UI styling.
- `public/app.js`: Browser-side session, settings, prompt queue, model dropdown, code selection context, live transcript updates, and polling logic.
- `tests/`: Python `unittest` coverage for core behavior, permissions, and LangGraph compilation.

## Runtime Flow

1. The user creates or selects a chat.
2. The user chooses a mode, writes one prompt, optionally selects code in the file viewer or includes code in a fenced block, selects provider/model/permissions, then queues it.
3. The server creates a job and adds it to the session queue.
4. `orchestrator.py` drains each session queue in FIFO order; an approval-pending job pauses later prompts for that session, and saved queued prompts resume when the server starts again.
5. The job enters `agent_graph.py`, a LangGraph `StateGraph`.
6. Planner breaks the prompt into smaller tasks.
7. Ask and Plan modes route to read-only workspace and reviewer nodes.
8. Debug and Agent modes route to Developer, Safety, bash tool, Reviewer, Tester, Browser Tester, and Deployer nodes.
9. Safety combines the AI Safety agent's assessment with deterministic risk heuristics before applying the selected permission mode. “Ask every time” pauses the job with the exact command batch until the user approves it.
10. Tester runs requested verification commands and reviews their results with the AI Tester. If either reports a supported failure, LangGraph routes back to Developer for a corrective pass.
11. If a localhost URL is mentioned, Browser Tester opens it in headless Chromium, collects rendered page evidence, and can route failures back to Developer.
12. Text replies stream from LangChain into the job record while the UI polls; the final answer and graph events are also stored in session history and job events.

## API Routes

- `GET /api/sessions`: list sessions.
- `POST /api/sessions`: create a session.
- `GET /api/sessions/:id`: read one session.
- `PATCH /api/sessions/:id`: rename or update session metadata.
- `DELETE /api/sessions/:id`: delete a session, its history, and its jobs.
- `GET /api/settings`: read shared provider keys and default model settings.
- `PATCH /api/settings`: update shared provider keys and default model settings.
- `GET /api/models`: read provider/model dropdown data.
- `POST /api/sessions/:id/prompts`: queue a prompt.
- `GET /api/jobs/:id`: poll job status and agent events.
- `POST /api/jobs/:id/approve`: approve the pending command batch for a paused job.
- `GET /api/files`: list workspace files.
- `GET /api/workspace`: read the current working path and git diff summary.
- `GET /api/file?path=...`: read a workspace file.
- `POST /api/bash`: run a bash command in the workspace.

## Current Limits

- The browser tester checks rendered page content and JavaScript page errors; it does not yet perform model-generated click-through test scripts.
- API keys are stored in plain local JSON.
- Bash safety is a lightweight blocklist plus Safety-agent classification, not a full sandbox.
