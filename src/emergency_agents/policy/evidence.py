# Copyright 2025 msq
from __future__ import annotations

from typing import Dict, Tuple


def evidence_gate_ok(state: Dict) -> Tuple[bool, str]:
    """证据化门槛判定。

    Returns:
        (ok, reason) 二元组；ok为True表示通过。
    """
    resources_ok = bool(state.get("available_resources"))
    kg_hits = int(state.get("kg_hits_count", 0))
    rag_hits = int(state.get("rag_case_refs_count", 0))
    if not resources_ok:
        return False, "insufficient_resources"
    if kg_hits < 3:
        return False, "insufficient_kg_evidence"
    if rag_hits < 2:
        return False, "insufficient_rag_evidence"
    return True, "ok"


