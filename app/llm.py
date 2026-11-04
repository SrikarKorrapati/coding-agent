import json

from app.agents import SYSTEM_PROMPT

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception:  # Dependencies may not be installed until requirements are applied.
    HumanMessage = None
    SystemMessage = None
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except Exception:  # Keep read-only and local fallback features available before setup.
    ChatAnthropic = None


def extract_json(text):
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last < first:
        return None
    try:
        return json.loads(text[first:last + 1])
    except json.JSONDecodeError:
        return None


def _content_to_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def create_chat_model(settings):
    if settings.get("provider") == "anthropic":
        if ChatAnthropic is None:
            raise RuntimeError("The Anthropic LangChain integration is not installed. Run: python3 -m pip install -r requirements.txt")
        # Omit temperature because current Claude models may reject sampling parameters.
        return ChatAnthropic(
            anthropic_api_key=settings.get("apiKey"),
            model=settings.get("model"),
            base_url=settings.get("baseUrl"),
        )
    if ChatOpenAI is None:
        raise RuntimeError("LangChain dependencies are not installed. Run: python3 -m pip install -r requirements.txt")
    return ChatOpenAI(
        api_key=settings.get("apiKey"),
        model=settings.get("model"),
        temperature=0.2,
        base_url=(settings.get("baseUrl") or "https://api.openai.com/v1").rstrip("/"),
    )


def call_agent(settings, agent, prompt, response_format="text", on_token=None):
    if not settings.get("apiKey"):
        return {"ok": False, "content": "No API key configured. Using local fallback behavior.", "json": None}
    try:
        model = create_chat_model(settings)
        messages = [
            SystemMessage(content=f"{SYSTEM_PROMPT}\n\nYou are the {agent['name']} AI agent.\nYour responsibility: {agent['goal']}"),
            HumanMessage(content=prompt),
        ]
        if on_token:
            content_parts = []
            try:
                for chunk in model.stream(messages):
                    text = _content_to_text(chunk.content)
                    if text:
                        content_parts.append(text)
                        on_token(text)
            except Exception:
                if content_parts:
                    raise
                response = model.invoke(messages)
                content_parts.append(_content_to_text(response.content))
            content = "".join(content_parts)
        else:
            response = model.invoke(messages)
            content = _content_to_text(response.content)
        return {
            "ok": True,
            "content": content,
            "json": extract_json(content) if response_format == "json" else None,
        }
    except Exception as exc:
        return {"ok": False, "content": f"Model request failed: {exc}", "json": None}


def fallback_plan(input_data):
    text = (input_data.get("prompt") or "").lower()
    asks_for_code_change = any(word in text for word in ["edit", "modify", "fix", "create", "add", "update", "implement", "build", "write file"])
    tasks = [
        {
            "id": "understand",
            "title": "Understand the request",
            "verification": "Confirm mode, selected code, and whether file writes are allowed.",
        },
        {
            "id": "inspect",
            "title": "Inspect the workspace",
            "verification": "List relevant files and read any selected code context.",
        },
    ]
    tasks.append({
        "id": "change" if asks_for_code_change else "answer",
        "title": "Make the smallest useful code change" if asks_for_code_change else "Answer without modifying files",
        "verification": "Run focused checks after the edit." if asks_for_code_change else "Ensure the answer matches the requested mode.",
    })
    return {"needsClarification": False, "clarificationQuestion": "", "tasks": tasks}
