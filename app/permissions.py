import re

PERMISSION_MODES = {
    "ask_every_time": {
        "label": "Ask every time",
        "description": "Stop before running commands and ask the user to approve.",
    },
    "safe_only": {
        "label": "Auto-approve safe commands",
        "description": "Run only commands assessed as safe.",
    },
    "approve_all": {
        "label": "Approve everything",
        "description": "Run generated commands after logging the safety assessment.",
    },
}

HIGH_RISK_PATTERNS = [
    r"\bsudo\b",
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+checkout\s+--\s+",
    r"\bcurl\b.+\|\s*(sh|bash)\b",
    r"\bwget\b.+\|\s*(sh|bash)\b",
    r"\bchmod\s+-R\s+777\b",
    r"\bchown\s+-R\b",
    r">\s*/dev/",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]

CAUTION_PATTERNS = [
    r"\bnpm\s+install\b",
    r"\bpip\s+install\b",
    r"\bpython\d*\s+-m\s+pip\s+install\b",
    r"\bgit\s+push\b",
    r"\bkill(all)?\b",
    r"\bmv\b.+\s+/",
    r"\bcp\b.+\s+/",
]


def normalize_permission_mode(mode):
    return mode if mode in PERMISSION_MODES else "safe_only"


def _matches_any(command, patterns):
    return any(re.search(pattern, command) for pattern in patterns)


def assess_one(command):
    if _matches_any(command, HIGH_RISK_PATTERNS):
        return {
            "command": command,
            "risk": "unsafe",
            "reason": "Matches a destructive or privilege-escalating command pattern.",
        }
    if _matches_any(command, CAUTION_PATTERNS):
        return {
            "command": command,
            "risk": "caution",
            "reason": "May change dependencies, processes, remote state, or files outside the workspace.",
        }
    return {
        "command": command,
        "risk": "safe",
        "reason": "Looks like a local workspace command.",
    }


def fallback_safety_assessment(commands):
    command_assessments = [assess_one(item.get("command", "")) for item in commands]
    risks = {item["risk"] for item in command_assessments}
    risk = "unsafe" if "unsafe" in risks else "caution" if "caution" in risks else "safe"
    return {
        "risk": risk,
        "allowed": risk == "safe",
        "reason": "Heuristic command assessment completed." if command_assessments else "No commands to assess.",
        "commandAssessments": command_assessments,
    }


def apply_permission_mode(assessment, mode):
    normalized = normalize_permission_mode(mode)
    if normalized == "approve_all":
        return {
            **assessment,
            "allowed": True,
            "reason": f"{assessment.get('reason', '')} Permission mode approves all commands.",
        }
    if normalized == "ask_every_time":
        return {
            **assessment,
            "allowed": False,
            "reason": f"{assessment.get('reason', '')} Permission mode requires manual approval before execution.",
        }
    return {
        **assessment,
        "allowed": assessment.get("risk") == "safe" and bool(assessment.get("allowed")),
    }


def format_blocked_commands(assessment, commands):
    lines = []
    for item in commands:
        why = f" ({item.get('why')})" if item.get("why") else ""
        lines.append(f"- {item.get('command', '')}{why}")
    rendered = "\n".join(lines) or "- No commands generated."
    return f"Commands were not executed.\n\nReason: {assessment.get('reason')}\n\nCommands:\n{rendered}"
