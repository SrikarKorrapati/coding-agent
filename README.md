# Local Coding Agent

A small Python coding agent with persistent chats, queued prompts, modes, file tools, safety permissions, and a minimal browser UI.

The multi-agent workflow uses **LangChain Python** for model calls and **LangGraph Python** for graph orchestration.

## Setup

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 -m app.server
```

Open `http://localhost:4317`.

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

## Models

The UI has provider-aware model dropdowns for OpenAI, Anthropic, Google Gemini, Groq, Mistral, and OpenRouter. The Python runtime currently executes through OpenAI-compatible chat endpoints via `langchain-openai`; for Anthropic direct API use an OpenAI-compatible gateway such as OpenRouter, or add a dedicated Anthropic adapter.

## Permissions

- `Ask every time`: block before shell execution and ask for approval.
- `Auto-approve safe commands`: run only commands the Safety agent classifies as safe.
- `Approve everything`: run generated commands after logging the Safety agent assessment.

## API Key

The app stores one master API setting set in `work/agent-data/store.json`, shared by every chat.

- The Save API Settings button writes provider, API key, base URL, and model once for all chats.
- API keys are stored locally for this prototype. For serious use, move keys to encrypted storage or environment variables.
