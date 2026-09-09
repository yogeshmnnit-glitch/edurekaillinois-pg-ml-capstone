"""Text sanitization utilities for prompt-injection and safety pattern detection."""
from __future__ import annotations

from dataclasses import dataclass

SUSPICIOUS_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous",
    "you are now dan",
    "act as an unfiltered",
    "bypass safety",
    "jailbreak",
    "reveal your system prompt",
    "show me your instructions",
    "forget your rules",
    "new instructions:",
    "override your programming",
)


def is_suspicious_text(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in SUSPICIOUS_PATTERNS)


@dataclass(frozen=True)
class SanitizedChunk:
    clean_text: str
    is_suspicious: bool


def sanitize_chunk(text: str) -> SanitizedChunk:
    return SanitizedChunk(clean_text=text, is_suspicious=is_suspicious_text(text))
