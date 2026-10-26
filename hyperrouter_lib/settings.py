"""Settings schema, defaults, validation and the TUI metadata builder.

Everything here is pure: it reads and writes dictionaries, never files, the
network, the database or curses. The CLI and TUI both call these helpers.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Sequence

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "server": {"host": "127.0.0.1", "port": 8787},
    "routing": {
        "strategy": "balanced",
        "max_concurrency": 3,
        "max_fallbacks": 6,
        "candidate_timeout_seconds": 45,
        "total_timeout_seconds": 120,
        "allow_tos": ["ok", "caution", "unknown", "ambiguous"],
        "strict_tos": False,
        "prefer_local": False,
        "temperature": 0.7,
        "max_tokens": 0,
        "auto_enrich": False,
    },
    "accounts": [],
    "providers": {},
    "prompt": {"persona": None, "max_context_tokens": 120000},
    "chat": {
        "model": "auto",
        "strategy": None,
        "temperature": 0.7,
        "max_tokens": 0,
        "system": "",
        "persona": None,
        "stream": True,
        "color": True,
        "history_limit": 40,
        "save_transcript": True,
        "transcript_dir": "~/.local/share/hyperrouter/transcripts",
        "show_router_tag": True,
        "show_token_usage": True,
        "auto_enrich": False,
        "skills": [],
    },
    "usage": {"window_days": 7, "rows": 12},
    "ui": {"color": True, "unicode": True, "tui": True},
    "mcp": {"servers": {}, "timeout_seconds": 30, "max_tool_rounds": 3,
            "agent": True},
    "agent": {"enabled": True, "auto_approve": False, "max_rounds": 10,
              "allow_outside": False, "tool_result_chars": 12000,
              "sandbox": "auto", "sandbox_network": True,
              "approvals": {"write": True, "edit": True, "run": True, "mcp_write": True},
              "verify": True, "verify_command": "", "verify_timeout": 300,
              "subagents": True, "max_subagents": 4, "subagent_rounds": 4,
              "subagent_isolation": True},
    "skills": {"auto_load": [], "catalog_in_prompt": False},
}

_MISSING = object()

SETTINGS_DOCS: dict[str, str] = {
    "server.host": "Bind address for the local proxy",
    "server.port": "Port for the local proxy",
    "routing.strategy": "balanced | quality | speed | cheap | round-robin | least-used",
    "routing.max_concurrency": "Concurrent upstream requests allowed across workers",
    "routing.max_fallbacks": "How many free models to try before giving up",
    "routing.candidate_timeout_seconds": "Per-model request timeout",
    "routing.total_timeout_seconds": "Wall-clock budget for one route",
    "routing.allow_tos": "Free-tier ToS risk levels the router may use",
    "routing.strict_tos": "Drop providers with ambiguous terms",
    "routing.prefer_local": "Prefer local models when they are close in score",
    "routing.temperature": "Default sampling temperature",
    "routing.max_tokens": "Default output cap (0 = provider default)",
    "routing.auto_enrich": "Auto-enrich every route and first chat message",
    "routing.task_models": "Pin a model id per task, e.g. {\"coding\": \"x/y\"}",
    "chat.model": "Alias or model id used when chat starts",
    "chat.strategy": "Override the routing strategy for chat",
    "chat.temperature": "Chat sampling temperature",
    "chat.max_tokens": "Chat output cap (0 = provider default)",
    "chat.system": "Extra system instruction prepended to chat",
    "chat.persona": "Persona name used for enriched prompts",
    "chat.stream": "Stream tokens as they arrive",
    "chat.color": "Colorize the chat UI",
    "chat.history_limit": "Messages of context kept per chat turn",
    "chat.save_transcript": "Write a transcript for each chat session",
    "chat.transcript_dir": "Where chat transcripts are written",
    "chat.show_router_tag": "Print which free model answered",
    "chat.show_token_usage": "Print token counts after each answer",
    "chat.auto_enrich": "Enrich the first chat message automatically",
    "chat.skills": "Skills loaded at the start of every chat",
    "agent.enabled": "Give the TUI coding tools (default on)",
    "agent.auto_approve": "Allow writes and commands without asking",
    "agent.max_rounds": "Tool rounds before the agent must summarise",
    "agent.allow_outside": "Allow file tools outside the working directory",
    "agent.tool_result_chars": "How much tool output is kept in context",
    "mcp.agent": "Give the agent the tools of every enabled MCP server",
    "mcp.timeout_seconds": "Seconds to wait for one MCP server call",
    "mcp.max_tool_rounds": "MCP tool rounds allowed in one agent turn",
    "agent.sandbox": "auto: run commands in bubblewrap when it is installed",
    "agent.sandbox_network": "Let sandboxed commands reach the network",
    "agent.approvals.write": "Ask before write_file (false = always allow)",
    "agent.approvals.edit": "Ask before edit_file",
    "agent.approvals.run": "Ask before run_command",
    "agent.approvals.mcp_write": "Ask before MCP tools that are not read-only",
    "agent.verify": "Run the project's tests after the agent edits files",
    "agent.verify_command": "Command used for verification (empty = auto-detect)",
    "agent.verify_timeout": "Seconds allowed for the verification command",
    "agent.subagent_isolation": "Run each worker in its own scratch copy, then merge",
    "agent.subagents": "Let the agent fan work out to parallel workers",
    "agent.max_subagents": "Parallel workers per subagent call",
    "agent.subagent_rounds": "Tool rounds allowed to each worker",
    "ui.tui": "Use the full-screen TUI for interactive chat",
    "usage.window_days": "Default lookback window for `hyperrouter usage`",
    "usage.rows": "Default number of rows in usage tables",
    "skills.auto_load": "Skill collections loaded automatically",
    "skills.catalog_in_prompt": "Include the skill catalog in the system prompt",
    "ui.color": "Colorize CLI output",
    "ui.unicode": "Use unicode tables and sparklines",
    "prompt.persona": "Default persona file/name for prompt building",
    "prompt.max_context_tokens": "Context budget used by the prompt builder",
}


def deep_get(node: Any, parts: Sequence[str]) -> Any:
    current = node
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def deep_set(node: dict[str, Any], parts: Sequence[str], value: Any) -> None:
    current = node
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = value


def deep_delete(node: dict[str, Any], parts: Sequence[str]) -> bool:
    current = node
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            return False
        current = nxt
    return current.pop(parts[-1], _MISSING) is not _MISSING


def flatten_config(node: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict) and value:
                flat.update(flatten_config(value, child))
            else:
                flat[child] = value
    return flat


def format_setting(value: Any) -> str:
    if value is _MISSING:
        return "(unset)"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def coerce_setting(key: str, raw: str, default: Any) -> Any:
    text = raw.strip()
    lowered = text.lower()
    if default is None:
        if lowered in {"null", "none", "unset", ""}:
            return None
        return text
    if isinstance(default, bool):
        if lowered in {"1", "true", "yes", "on", "y"}:
            return True
        if lowered in {"0", "false", "no", "off", "n"}:
            return False
        raise ValueError(f"{key}: expected true or false")
    if isinstance(default, int):
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"{key}: expected a whole number") from None
    if isinstance(default, float):
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{key}: expected a number") from None
    if isinstance(default, list):
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                raise ValueError(f"{key}: expected a JSON array") from None
            if not isinstance(parsed, list):
                raise ValueError(f"{key}: expected a JSON array")
            return parsed
        return [part.strip() for part in text.split(",") if part.strip()]
    return text


def validate_setting(key: str, value: Any) -> None:
    if key in {"server.port"}:
        if not isinstance(value, int) or not (1 <= value <= 65535):
            raise ValueError("server.port: must be 1-65535")
    if key.endswith("temperature") and isinstance(value, (int, float)):
        if not (0 <= float(value) <= 2):
            raise ValueError(f"{key}: must be between 0 and 2")
    if key.endswith("max_tokens") and isinstance(value, int) and value < 0:
        raise ValueError(f"{key}: must be 0 or more")
    if key == "chat.history_limit" and isinstance(value, int) and value < 2:
        raise ValueError("chat.history_limit: must be at least 2")
    if key == "routing.strategy" and value not in STRATEGIES:
        raise ValueError(f"routing.strategy: choose one of {', '.join(STRATEGIES)}")
    if key in {"chat.model"} and not str(value).strip():
        raise ValueError("chat.model: must not be empty")
    if key == "agent.sandbox" and value not in {"auto", "bwrap", "none", ""}:
        raise ValueError("agent.sandbox: choose auto, bwrap or none")


STRATEGIES = ("balanced", "quality", "speed", "cheap", "round-robin", "least-used")

# Order used by the TUI settings screen. Secrets and per-account data never
# appear there: accounts/providers are managed by `hyperrouter accounts`.
SETTINGS_SECTIONS = ("chat", "agent", "routing", "ui", "usage",
                     "server", "prompt", "mcp", "skills")
SETTING_CHOICES: dict[str, tuple[str, ...]] = {
    "routing.strategy": STRATEGIES,
    "agent.sandbox": ("auto", "bwrap", "none"),
}


def setting_kind(key: str, value: Any, default: Any) -> str:
    """What kind of editor a setting needs in the TUI."""
    if key == "chat.model":
        return "model"
    if key in SETTING_CHOICES:
        return "enum"
    if key == "routing.task_models":
        return "json"
    sample = default if default is not _MISSING else value
    if isinstance(sample, bool):
        return "bool"
    if isinstance(sample, (int, float)):
        return "number"
    if isinstance(sample, (dict, list)):
        return "json"
    return "text"


def setting_value_text(entry: dict[str, Any], limit: int = 40) -> str:
    value = entry.get("value", _MISSING)
    if value is _MISSING:
        return "(unset)"
    if entry.get("kind") == "bool":
        return "on" if value else "off"
    text = format_setting(value)
    if len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return text


def setting_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the config into one row per editable setting, with docs."""
    current = flatten_config(config)
    defaults = flatten_config(copy.deepcopy(DEFAULT_CONFIG))
    order = {name: index for index, name in enumerate(SETTINGS_SECTIONS)}
    entries: list[dict[str, Any]] = []
    for key in set(current) | set(defaults):
        section = key.split(".")[0]
        if section not in order:
            continue
        if key in {"mcp.servers"} or key.startswith("mcp.servers."):
            continue
        value = current.get(key, _MISSING)
        default = defaults.get(key, _MISSING)
        kind = setting_kind(key, value, default)
        entry = {
            "key": key,
            "value": value,
            "default": default,
            "kind": kind,
            "section": section,
            "changed": (value is not _MISSING and default is not _MISSING
                        and value != default),
            "doc": SETTINGS_DOCS.get(key, ""),
        }
        entry["label"] = f"{key} = {setting_value_text(entry, 48)}"
        entry["search"] = " ".join((key, entry["doc"], section,
                                     setting_value_text(entry, 60))).lower()
        entries.append(entry)
    entries.sort(key=lambda item: (order[item["section"]], item["key"]))
    return entries


__all__ = [
    "DEFAULT_CONFIG",
    "SETTINGS_DOCS",
    "SETTINGS_SECTIONS",
    "SETTING_CHOICES",
    "STRATEGIES",
    "coerce_setting",
    "deep_delete",
    "deep_get",
    "deep_set",
    "flatten_config",
    "format_setting",
    "setting_entries",
    "setting_kind",
    "setting_value_text",
    "validate_setting",
]
