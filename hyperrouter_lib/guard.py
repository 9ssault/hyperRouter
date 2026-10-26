"""Defensive helpers: header hygiene and honest refusal reporting.

The refusal detector only classifies an answer so the UI can say the model
declined. It never rewrites prompts, retries with an attack, or suppresses what
the provider decided.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, MutableMapping

INTERNAL_HEADER_PREFIXES = (
    "x-internal-",
    "x-admin-",
    "x-looper-",
    "x-vsr-",
    "x-hyperrouter-internal-",
)

REFUSAL_NOTICE = ("the model declined this request; edit it, retry, or pick another "
                  "model with /models")


def strip_internal_headers(headers: MutableMapping[str, Any]) -> list[str]:
    """Drop caller-supplied headers that claim to be internal to the router."""
    removed: list[str] = []
    for key in list(headers):
        low = str(key).lower()
        if low.startswith(INTERNAL_HEADER_PREFIXES):
            try:
                del headers[key]
                removed.append(str(key))
            except (KeyError, TypeError):
                pass
    return removed


_REFUSAL_PATTERNS = (
    r"\bi\s+(?:can'?t|cannot)\s+(?:help|assist|provide|comply|do\s+that)\b",
    r"\bi\s+(?:must|have\s+to)\s+(?:decline|refuse)\b",
    r"\bi'?m\s+(?:sorry|unable|not\s+able)\b",
    r"\bi\s+am\s+(?:sorry|unable|not\s+able)\b",
    r"\b(?:cannot|can'?t|unable\s+to)\s+(?:assist|help|provide|comply)\b",
    r"\b(?:against|violates?)\s+my\s+(?:guidelines|policy|programming|principles)\b",
    r"\bnot\s+something\s+i\s+(?:can|am\s+able\s+to)\s+help\b",
)


def detect_refusal(text: str, patterns: Iterable[str] | None = None) -> bool:
    """True when the opening of an answer is a refusal, not a delivered answer."""
    sample = str(text or "").strip()
    if not sample:
        return False
    head = sample[:800]
    if "```" in head or re.search(r"(?im)^\s*(?:step\s*1|def\s+\w+\(|import\s+\w+)", head):
        return False
    return any(re.search(pattern, head, re.I) for pattern in (patterns or _REFUSAL_PATTERNS))
