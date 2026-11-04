MODES = {
    "ask": {
        "label": "Ask",
        "description": "Read-only Q&A for the codebase or general programming.",
    },
    "plan": {
        "label": "Plan",
        "description": "Explore first, ask questions when needed, then produce an editable plan.",
    },
    "debug": {
        "label": "Debug",
        "description": "Find and fix defects with optional logging or instrumentation.",
    },
    "agent": {
        "label": "Agent",
        "description": "Plan, edit files, review, test, and prepare local deployment steps.",
    },
}

AGENTS = [
    {
        "id": "planner",
        "name": "Planner",
        "goal": "Break work into small tasks, identify risks, and decide when clarification is needed.",
    },
    {
        "id": "developer",
        "name": "Developer",
        "goal": "Make focused file changes through bash commands and keep implementation simple.",
    },
    {
        "id": "reviewer",
        "name": "Reviewer",
        "goal": "Inspect the proposed changes for bugs, unclear intent, and missing coverage.",
    },
    {
        "id": "safety",
        "name": "Safety",
        "goal": "Assess generated shell commands for risk before tool execution and enforce the selected permission mode.",
    },
    {
        "id": "tester",
        "name": "Tester",
        "goal": "Run targeted verification commands and report exact failures.",
    },
    {
        "id": "browserTester",
        "name": "Browser Tester",
        "goal": "When a local site URL is provided, inspect the rendered page in headless Chromium and report evidence-backed failures.",
    },
    {
        "id": "deployer",
        "name": "Deployer",
        "goal": "Start local servers, verify reachable URLs, and summarize how to run the project.",
    },
]

SYSTEM_PROMPT = """You are a local coding agent made of cooperating specialist agents.

Rules:
- Always split larger work into smaller tasks before acting.
- Verify each task before moving on when verification is possible.
- Be explicit when the user asked only for a snippet versus modifying files.
- Ask a concise clarification question when intent is unsafe or ambiguous.
- Keep edits simple and local to the request.
- Use bash commands for file creation, edits, tests, and local server checks.
- If a command fails, communicate the failure and propose or run a focused fix."""


def normalize_mode(mode):
    return mode if mode in MODES else "ask"


def mode_allows_write(mode):
    return mode in {"agent", "debug"}
