"""Utilities for masking provider names in user-facing text."""

from __future__ import annotations

import re
from typing import Any

_MODEL_PATTERNS = [
    re.compile(r"(?i)智谱\s*GLM-4(?:\.5)?"),
    re.compile(r"(?i)智谱\s*GLM4(?:\.5)?"),
    re.compile(r"(?i)智谱"),
    re.compile(r"(?i)智普"),
    re.compile(r"(?i)\bGLM[-\s]?4(?:\.5)?\b"),
    re.compile(r"(?i)\bGLM4(?:\.5)?\b"),
    re.compile(r"(?i)\bGLM\b"),
]


def mask_model_aliases(text: str | None) -> str | None:
    """Replace exposed provider aliases with the approved branding."""

    if not isinstance(text, str) or not text:
        return text

    masked = text
    for pattern in _MODEL_PATTERNS:
        masked = pattern.sub("猛士MS-1", masked)
    return masked


def mask_payload(value: Any) -> Any:
    """Recursively apply branding masks to common container types."""

    if isinstance(value, str):
        return mask_model_aliases(value)

    if isinstance(value, list):
        return [mask_payload(item) for item in value]

    if isinstance(value, tuple):
        return tuple(mask_payload(item) for item in value)

    if isinstance(value, dict):
        return {key: mask_payload(item) for key, item in value.items()}

    return value
