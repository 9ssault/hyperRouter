"""Pure text, token and display-column helpers."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def redact(text: str) -> str:
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", text)
    text = re.sub(r"(?i)(authorization:\s*bearer\s+)[^\s,;]+", r"\1***", text)
    text = re.sub(r"(?i)(api[_-]?key[\"'=:\s]+)[A-Za-z0-9._-]{8,}", r"\1***", text)
    return text


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif item.get("type") == "image_url":
                    parts.append("[image]")
        return "\n".join(parts)
    return str(content or "")


def messages_to_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    parts = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "user")
        parts.append(f"{role}: {content_to_text(msg.get('content'))}")
    return "\n".join(parts)


def display_width(text: str) -> int:
    width = 0
    for char in str(text or ""):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def clip_display(text: str, width: int) -> str:
    """Trim a string to a display width without splitting wide characters."""
    if width <= 0:
        return ""
    out: list[str] = []
    used = 0
    for char in str(text or ""):
        if unicodedata.combining(char):
            out.append(char)
            continue
        size = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if used + size > width:
            break
        out.append(char)
        used += size
    return "".join(out)


def _cap(text: str, limit: int = 12000) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... ({len(text) - limit} more characters)"


def human_count(value: float) -> str:
    value = float(value or 0)
    for unit in ("", "k", "M", "B"):
        if abs(value) < 1000 or unit == "B":
            return f"{value:.0f}" if unit == "" else f"{value:.1f}{unit}"
        value /= 1000.0
    return str(value)
