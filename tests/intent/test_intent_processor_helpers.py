from __future__ import annotations

import pytest

pytest.importorskip("qdrant_client")

from emergency_agents.api.intent_processor import _encode_intent_for_mem0


def test_encode_intent_for_mem0_basic() -> None:
    assert _encode_intent_for_mem0("video-analysis") == "VIDEO_ANALYSIS"


def test_encode_intent_for_mem0_empty() -> None:
    assert _encode_intent_for_mem0("") == "UNKNOWN"


def test_encode_intent_for_mem0_leading_digit() -> None:
    assert _encode_intent_for_mem0("123-intent") == "A_123_INTENT"
