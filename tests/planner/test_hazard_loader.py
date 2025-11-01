from __future__ import annotations

from pathlib import Path

import pytest

from emergency_agents.planner.hazard_loader import HazardPackLoader


def _knowledge_root() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parent.parent.parent
        / "src"
        / "emergency_agents"
        / "knowledge"
        / "hazard_packs"
    )


@pytest.fixture(scope="module")
def loader() -> HazardPackLoader:
    return HazardPackLoader(base_path=_knowledge_root())


def test_load_known_hazard(loader: HazardPackLoader) -> None:
    pack = loader.load_pack("bridge_collapse")
    assert pack.hazard_type == "bridge_collapse"
    assert pack.version == "1.0.0"
    assert pack.mission_templates, "应至少包含一个阶段任务"


def test_manifest_exposes_hazards(loader: HazardPackLoader) -> None:
    hazards = list(loader.get_available_hazards())
    assert "bridge_collapse" in hazards
    assert "chemical_leak" in hazards
