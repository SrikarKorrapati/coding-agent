# Local Coding Agent

A small Python coding agent with persistent chats, queued prompts, modes, file tools, safety permissions, and a minimal browser UI.

The multi-agent workflow uses **LangChain Python** for model calls and **LangGraph Python** for graph orchestration.

## Setup

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## Run

```bash
python3 -m app.server
```

Open `http://localhost:4317`.

The server binds to `127.0.0.1` by default so the local API and saved keys are not exposed to other devices on the network. Set `HOST` only when you intentionally need another bind address.

Use another port if needed:

```bash
PORT=4320 python3 -m app.server
```

## Test

```bash
python3 -m unittest discover -s tests
```

## Modes

- `Ask`: read-only Q&A.
- `Plan`: read-only planning for bigger tasks.
- `Debug`: focused bug fixing with file edits enabled by mode.
- `Agent`: full plan, edit, review, test, safety check, and local deployment workflow.

The selected mode controls whether the agents may edit files: Ask and Plan are read-only; Debug and Agent can make changes. Use Ask for generated snippets or explanations.

Plan replies include numbered steps with verification notes. Follow up in the same chat to revise a plan; the Planner uses recent conversation context.

The Home view has one prompt box. Select code in the file viewer and choose **Ask about selection** to add its path and text to a read-only question. You can also paste code in a fenced block.

The status at the bottom of the chat clearly shows when the agent is idle, queued, working, pausing, paused, or waiting for approval. Pause takes effect at the next model or tool boundary; Resume continues the current job. The agent records small workflow checkpoints and shows them under the response.

Each chat can keep editable long-term memory. **Compact chat** summarizes older messages, keeps the recent messages in the transcript, and archives the full older history. **Fork chat** starts a separate persistent chat with the current context and memory.

To give the agent browser access, enter a local site such as `http://localhost:5173` in **Browser URL**. The Browser Tester uses headless Chromium to inspect the rendered page, and can perform a small set of requested clicks, fills, or key presses. Browser navigation is restricted to localhost; a failed check in Debug or Agent mode can return to Developer for a correction pass.

## Models

The UI has provider-aware model dropdowns for OpenAI, Anthropic, Google Gemini, Groq, Mistral, and OpenRouter. OpenAI-compatible providers use `langchain-openai`; Claude uses `langchain-anthropic`.

## Permissions

- `Ask every time`: show the proposed shell commands and wait for you to approve them in the timeline.
- `Auto-approve safe commands`: run only commands the Safety agent classifies as safe.
- `Approve everything`: run generated commands after logging the Safety agent assessment.

The file panel counts added and deleted lines for tracked changes, including staged edits, and counts lines in new untracked text files.

## API Key

The app stores shared API settings in `work/agent-data/store.json`.

- Use the Settings button in the left rail to set the default provider and model, and manage separate OpenAI, Anthropic, and Google API keys. Each key can be enabled independently; OpenAI also has an optional base URL override.
- Groq, Mistral, and OpenRouter can use the optional key field under “Other OpenAI-compatible providers.”
- API keys are stored locally for this prototype. For serious use, move keys to encrypted storage or environment variables.
