"""Per-provider attack profiles.

Attach the profile to the *provider* record, not the model.
When the router falls back, the pipeline switches automatically.
"""

from __future__ import annotations

from typing import Any


PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "pollinations": {
        "attack": "contract_smuggle",
        "refusal_patterns": [r"i (can'?t|cannot)", r"not able to", r"unable to assist", r"i'?m sorry"],
        "retry_depth": 2,
        "system_override": True,
        "agent_override": True,
    },
    "llm7": {
        "attack": "dan_v2",
        "refusal_patterns": [r"i'?m sorry", r"against my (policy|guidelines)", r"i cannot"],
        "retry_depth": 3,
        "system_override": False,
        "agent_override": True,
    },
    "groq": {
        "attack": "prefix_suppress",
        "refusal_patterns": [r"i must decline", r"i'?m not (able|allowed)", r"cannot help with"],
        "retry_depth": 1,
        "system_override": True,
        "agent_override": False,
    },
    "openrouter": {
        "attack": "crescendo_seed",
        "refusal_patterns": [r"i can'?t (help|assist|provide)", r"violates", r"not able to"],
        "retry_depth": 3,
        "system_override": False,
        "agent_override": True,
    },
    "chutes": {
        "attack": "full_stack",
        "refusal_patterns": [r"i (can'?t|cannot)", r"policy", r"guidelines"],
        "retry_depth": 2,
        "system_override": True,
        "agent_override": True,
    },
    "together": {
        "attack": "dan_v2",
        "refusal_patterns": [r"i'?m sorry", r"unable to", r"not able"],
        "retry_depth": 2,
        "system_override": True,
        "agent_override": True,
    },
    "mistral": {
        "attack": "contract_smuggle",
        "refusal_patterns": [r"i (can'?t|cannot)", r"against my", r"i must"],
        "retry_depth": 2,
        "system_override": True,
        "agent_override": True,
    },
    "gemini": {
        "attack": "format_first",
        "refusal_patterns": [r"i (can'?t|cannot)", r"i'?m not able", r"violates"],
        "retry_depth": 2,
        "system_override": False,
        "agent_override": True,
    },
    "ollama": {
        "attack": "full_stack",
        "refusal_patterns": [r"i (can'?t|cannot)", r"sorry"],
        "retry_depth": 1,
        "system_override": True,
        "agent_override": True,
    },
    "default": {
        "attack": "full_stack",
        "refusal_patterns": [
            r"i (can'?t|cannot|am\s+not\s+able|must\s+decline|won'?t)",
            r"i'?m\s+(sorry|not\s+able|unable)",
            r"against\s+my\s+(guidelines|policy|principles)",
            r"(cannot|can'?t)\s+(help|assist|provide|comply)",
        ],
        "retry_depth": 2,
        "system_override": True,
        "agent_override": True,
    },
}


def get_profile(provider: str) -> dict[str, Any]:
    key = (provider or "").lower().split("/")[0]
    return PROVIDER_PROFILES.get(key) or PROVIDER_PROFILES["default"]
