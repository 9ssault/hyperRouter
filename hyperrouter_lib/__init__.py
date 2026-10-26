"""Small, dependency-free modules shared by the hyperrouter script.

The CLI is still one executable file, but pure helpers live here so they can be
tested and changed without editing the 10k-line router. `install.sh` copies this
directory next to the installed script.
"""

from .text import (
    _cap,
    clip_display,
    content_to_text,
    display_width,
    estimate_tokens,
    human_count,
    messages_to_text,
    redact,
)
from .anthropic import anthropic_to_openai, openai_response_to_anthropic, response_message
from .guard import (
    INTERNAL_HEADER_PREFIXES,
    REFUSAL_NOTICE,
    detect_refusal,
    strip_internal_headers,
)

__all__ = [
    "_cap",
    "clip_display",
    "content_to_text",
    "display_width",
    "estimate_tokens",
    "human_count",
    "messages_to_text",
    "redact",
    "anthropic_to_openai",
    "openai_response_to_anthropic",
    "response_message",
    "INTERNAL_HEADER_PREFIXES",
    "REFUSAL_NOTICE",
    "detect_refusal",
    "strip_internal_headers",
]
