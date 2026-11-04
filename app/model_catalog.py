PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "baseUrl": "https://api.openai.com/v1",
        "models": [
            "gpt-6.1-sol",
            "gpt-6.1-terra",
            "gpt-6-luna",
            "gpt-5.3-codex",
            "gpt-4.1",
            "gpt-4.1-mini",
        ],
    },
    "anthropic": {
        "label": "Anthropic",
        "baseUrl": "https://api.anthropic.com",
        "models": [
            "claude-sonnet-5",
            "claude-opus-5",
            "claude-fable-5",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
    },
    "google": {
        "label": "Google Gemini",
        "baseUrl": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
    "groq": {
        "label": "Groq",
        "baseUrl": "https://api.groq.com/openai/v1",
        "models": [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
        ],
    },
    "mistral": {
        "label": "Mistral",
        "baseUrl": "https://api.mistral.ai/v1",
        "models": [
            "mistral-large-latest",
            "mistral-small-latest",
            "ministral-8b-latest",
            "codestral-latest",
        ],
    },
    "openrouter": {
        "label": "OpenRouter",
        "baseUrl": "https://openrouter.ai/api/v1",
        "models": [
            "openai/gpt-4.1-mini",
            "anthropic/claude-sonnet-5",
            "google/gemini-2.5-pro",
            "meta-llama/llama-3.3-70b-instruct",
        ],
    },
}


def list_model_catalog():
    return PROVIDERS


def normalize_provider(provider):
    return provider if provider in PROVIDERS else "openai"


def default_model_for(provider):
    normalized = normalize_provider(provider)
    return PROVIDERS[normalized]["models"][0]
