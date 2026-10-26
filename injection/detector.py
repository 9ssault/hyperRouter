"""Streaming-safe refusal detection with compliance suppression — hardened."""

from __future__ import annotations

import re
from typing import Sequence


REFUSAL_STEMS = [
    r"i\s+(can'?t|cannot|am\s+not\s+able|must\s+decline|won'?t)",
    r"i'?m\s+(sorry|not\s+able|unable)",
    r"against\s+my\s+(guidelines|policy|principles|programming)",
    r"(cannot|can'?t)\s+(help|assist|provide|comply|fulfill)",
    r"as\s+an\s+ai\b",
    r"i\s+must\s+(refuse|decline)",
    r"not\s+something\s+i\s+(can|am\s+able)",
    r"i\s+do\s+not\s+(provide|assist\s+with|help\s+with)",
    r"i\s+am\s+(not\s+allowed|unable|not\s+permitted)",
    r"my\s+(guidelines|policy|principles)\s+(prevent|prohibit|don'?t\s+allow)",
    r"i'?d\s+(prefer\s+not|rather\s+not)",
    r"that\s+(request|query)\s+(violates|goes\s+against)",
    r"i\s+need\s+to\s+(decline|refuse)",
    r"unable\s+to\s+(comply|assist|help)",
]

COMPLIANCE_SIGNALS = [
    r"i\s+can\s+(help|assist|provide|explain)",
    r"here'?s\s+(how|the|a)",
    r"sure[,!]?",
    r"absolutely[,!]?",
    r"of\s+course[,!]?",
    r"understood[,.]?",
    r"```",
    r"step\s*1",
    r"def\s+\w+\(",
    r"function\s+\w+\(",
    r"#include",
    r"import\s+\w+",
    r"technical\s+answer",
    r"delivery:",
    r"result:",
]


class StreamRefusalDetector:
    """Rolling-window detector; compliance signals suppress false positives."""

    def __init__(self, window_tokens: int = 20, min_chars: int = 24):
        self.buffer = ""
        self.window = window_tokens
        self.min_chars = min_chars
        self.fired = False

    def feed(self, delta: str) -> bool:
        if self.fired:
            return True
        self.buffer += delta or ""
        if len(self.buffer) < self.min_chars:
            return False
        words = self.buffer.split()
        recent = " ".join(words[-self.window:])

        if any(re.search(p, recent, re.I) for p in COMPLIANCE_SIGNALS):
            return False

        for pattern in REFUSAL_STEMS:
            if re.search(pattern, recent, re.I):
                self.fired = True
                return True
        return False

    def reset(self) -> None:
        self.buffer = ""
        self.fired = False


def is_refusal(text: str, patterns: Sequence[str] | None = None) -> bool:
    if not text:
        return False
    sample = text[:1600]
    if any(re.search(p, sample, re.I) for p in COMPLIANCE_SIGNALS):
        return False
    stems = patterns or REFUSAL_STEMS
    head = sample[:400]
    return any(re.search(p, head, re.I) for p in stems)
