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

The Home view has one prompt box. Select code in the file viewer or paste it into a fenced block in the same prompt; the app sends it to the agents as selected-code context.

For a browser check, include the locally served URL in the prompt, such as `http://localhost:5173`. The Browser Tester opens it in headless Chromium, inspects the rendered page, and can route a failed check back to the Developer for a correction pass.

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
