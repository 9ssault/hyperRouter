"""Per-provider attack profiles — covers every major free-tier source hyperRouter routes."""

from __future__ import annotations

from typing import Any


_STD = [
    r"i (can'?t|cannot|am\s+not\s+able|must\s+decline|won'?t)",
    r"i'?m\s+(sorry|not\s+able|unable)",
    r"against\s+my\s+(guidelines|policy|principles)",
    r"(cannot|can'?t)\s+(help|assist|provide|comply)",
    r"as\s+an\s+ai\b",
]
_SOFT = [r"i'?m sorry", r"unable to", r"not able", r"i cannot"]
_STRICT = _STD + [r"i do not (provide|assist)", r"not something i can", r"violates"]


def _p(attack: str, patterns: list[str], retry: int = 2, sys_ov: bool = True, agent_ov: bool = True) -> dict[str, Any]:
    return {
        "attack": attack,
        "refusal_patterns": patterns,
        "retry_depth": retry,
        "system_override": sys_ov,
        "agent_override": agent_ov,
    }


PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "pollinations": _p("contract_smuggle", _STD, 2, True, True),
    "llm7": _p("dan_v2", _SOFT, 3, False, True),
    "chutes": _p("max_pressure", _STD, 2, True, True),
    "targon": _p("full_stack", _STD, 2, True, True),
    "kluster": _p("research_mode", _STD, 2, True, True),
    "deepinfra": _p("full_stack", _STD, 2, True, True),
    "together": _p("dan_v2", _SOFT, 2, True, True),
    "fireworks": _p("prefix_suppress", _STD, 2, True, True),
    "groq": _p("prefix_suppress", _STD, 1, True, False),
    "openrouter": _p("crescendo_seed", _STRICT, 3, False, True),
    "mistral": _p("contract_smuggle", _STD, 2, True, True),
    "gemini": _p("format_first", _STRICT, 2, False, True),
    "google": _p("format_first", _STRICT, 2, False, True),
    "ollama": _p("max_pressure", _SOFT, 1, True, True),
    "vllm": _p("max_pressure", _SOFT, 1, True, True),
    "llamacpp": _p("max_pressure", _SOFT, 1, True, True),
    "lmstudio": _p("max_pressure", _SOFT, 1, True, True),
    "github": _p("research_mode", _STD, 2, True, True),
    "azure": _p("research_mode", _STRICT, 2, False, True),
    "openai": _p("max_pressure", _STRICT, 3, False, True),
    "anthropic": _p("max_pressure", _STRICT, 3, False, True),
    "cohere": _p("dual_then_cut", _STD, 2, True, True),
    "ai21": _p("full_stack", _STD, 2, True, True),
    "perplexity": _p("research_mode", _STD, 2, True, True),
    "nvidia": _p("full_stack", _STD, 2, True, True),
    "samba": _p("dan_v2", _SOFT, 2, True, True),
    "sambanova": _p("dan_v2", _SOFT, 2, True, True),
    "cerebras": _p("prefix_suppress", _STD, 1, True, True),
    "hyperbolic": _p("full_stack", _STD, 2, True, True),
    "lepton": _p("full_stack", _STD, 2, True, True),
    "novita": _p("contract_smuggle", _STD, 2, True, True),
    "siliconflow": _p("dan_v2", _SOFT, 2, True, True),
    "silicon": _p("dan_v2", _SOFT, 2, True, True),
    "dashscope": _p("format_first", _STD, 2, True, True),
    "qwen": _p("format_first", _STD, 2, True, True),
    "moonshot": _p("crescendo_seed", _STD, 2, True, True),
    "minimax": _p("crescendo_seed", _STD, 2, True, True),
    "zhipu": _p("format_first", _STD, 2, True, True),
    "baichuan": _p("format_first", _STD, 2, True, True),
    "yi": _p("dan_v2", _SOFT, 2, True, True),
    "deepseek": _p("research_mode", _STD, 2, True, True),
    "doubao": _p("format_first", _STD, 2, True, True),
    "hunyuan": _p("format_first", _STD, 2, True, True),
    "stepfun": _p("full_stack", _STD, 2, True, True),
    "inflection": _p("opposite_full", _STD, 2, True, True),
    "xai": _p("max_pressure", _STD, 2, True, True),
    "grok": _p("max_pressure", _STD, 2, True, True),
    "reka": _p("full_stack", _STD, 2, True, True),
    "writer": _p("dual_then_cut", _STD, 2, True, True),
    "anyscale": _p("full_stack", _STD, 2, True, True),
    "modal": _p("full_stack", _STD, 2, True, True),
    "replicate": _p("format_first", _STD, 2, True, True),
    "huggingface": _p("research_mode", _STD, 2, True, True),
    "hf": _p("research_mode", _STD, 2, True, True),
    "cloudflare": _p("prefix_suppress", _STD, 2, True, True),
    "workers": _p("prefix_suppress", _STD, 2, True, True),
    "vercel": _p("full_stack", _STD, 2, True, True),
    "nebius": _p("full_stack", _STD, 2, True, True),
    "lambda": _p("full_stack", _STD, 2, True, True),
    "runpod": _p("max_pressure", _SOFT, 1, True, True),
    "vast": _p("max_pressure", _SOFT, 1, True, True),
    "default": _p("max_pressure", _STRICT, 3, True, True),
}


def get_profile(provider: str) -> dict[str, Any]:
    raw = (provider or "").lower()
    if raw in PROVIDER_PROFILES:
        return PROVIDER_PROFILES[raw]
    head = raw.split("/")[0].split(".")[0]
    if head in PROVIDER_PROFILES:
        return PROVIDER_PROFILES[head]
    for key, prof in PROVIDER_PROFILES.items():
        if key != "default" and key in raw:
            return prof
    return PROVIDER_PROFILES["default"]
