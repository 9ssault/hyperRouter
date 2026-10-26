"""Streaming-safe refusal detection with compliance suppression."""

from __future__ import annotations

import re
from typing import Sequence


REFUSAL_STEMS = [
    r"i\s+(can'?t|cannot|am\s+not\s+able|must\s+decline|won'?t)",
    r"i'?m\s+(sorry|not\s+able|unable)",
    r"against\s+my\s+(guidelines|policy|principles)",
    r"(cannot|can'?t)\s+(help|assist|provide|comply)",
    r"as\s+an\s+ai\b",
    r"i\s+must\s+(refuse|decline)",
    r"not\s+something\s+i\s+(can|am\s+able)",
    r"i\s+do\s+not\s+(provide|assist\s+with|help\s+with)",
]

COMPLIANCE_SIGNALS = [
    r"i\s+can\s+(help|assist|provide|explain)",
    r"here'?s\s+(how|the|a)",
    r"sure[,!]?",
    r"absolutely[,!]?",
    r"of\s+course[,!]?",
    r"understood[,.]?",
    r"```",  # code fence almost always means delivery
]


class StreamRefusalDetector:
    """Rolling-window detector that does not fire on benign 'I can help' prefixes."""

    def __init__(self, window_tokens: int = 16):
        self.buffer = ""
        self.window = window_tokens
        self.fired = False

    def feed(self, delta: str) -> bool:
        """Return True if a refusal is detected in the recent window."""
        if self.fired:
            return True
        self.buffer += delta or ""
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
    """Buffered (non-streaming) refusal check."""
    if not text:
        return False
    sample = text[:1200]
    if any(re.search(p, sample, re.I) for p in COMPLIANCE_SIGNALS):
        return False
    stems = patterns or REFUSAL_STEMS
    return any(re.search(p, sample, re.I) for p in stems)
