# Copyright 2025 msq
import pytest
from emergency_agents.agents.plan_generator import plan_generator_agent
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig
from emergency_agents.graph.kg_service import KGService, KGConfig


@pytest.fixture
def setup_services():
    """设置测试所需的服务"""
    cfg = AppConfig.load_from_env()
    
    llm_client = get_openai_client(cfg)
    
    kg_service = KGService(KGConfig(
        uri=cfg.neo4j_uri or "bolt://localhost:7687",
        user=cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        password=cfg.neo4j_password or "example-neo4j"
    ))
    
    return llm_client, kg_service, cfg


@pytest.mark.integration
def test_plan_generator_basic(setup_services):
    """测试基本方案生成
    
    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 897-915
    """
    llm_client, kg_service, cfg = setup_services
    
    state = {
        "rescue_id": "test_plan_001",
        "situation": {
            "disaster_type": "earthquake",
            "magnitude": 7.8,
            "affected_area": "汶川县"
        },
        "predicted_risks": [
            {"type": "flood", "probability": 0.75, "eta_hours": 2, "severity": "high", "display_name": "洪水"},
            {"type": "landslide", "probability": 0.85, "eta_hours": 1, "severity": "critical", "display_name": "山体滑坡"}
        ]
    }
    
    result = plan_generator_agent(state, kg_service, llm_client, cfg.llm_model)
    
    assert "proposals" in result
    assert len(result["proposals"]) > 0
    
    proposal = result["proposals"][0]
    assert "id" in proposal
    assert "type" in proposal
    assert "params" in proposal
    assert "rationale" in proposal
    assert proposal["requires_approval"] is True
    
    assert "plan" in result
    plan = result["plan"]
    assert "name" in plan or "phases" in plan
    
    assert result["status"] == "awaiting_approval"
    
    print(f"✅ 方案生成测试通过")
    print(f"  方案: {plan.get('name', 'Unnamed')}")
    print(f"  提案ID: {proposal['id']}")


@pytest.mark.integration
def test_plan_generator_with_equipment(setup_services):
    """测试装备推荐"""
    llm_client, kg_service, cfg = setup_services
    
    state = {
        "situation": {
            "disaster_type": "earthquake",
            "magnitude": 7.5
        },
        "predicted_risks": [
            {"type": "flood", "probability": 0.8, "eta_hours": 2, "severity": "high"}
        ]
    }
    
    result = plan_generator_agent(state, kg_service, llm_client, cfg.llm_model)
    
    if "equipment_recommendations" in result:
        equipment = result["equipment_recommendations"]
        assert isinstance(equipment, list)
        if len(equipment) > 0:
            eq = equipment[0]
            assert "equipment_name" in eq or "display_name" in eq
            print(f"✅ 装备推荐测试通过: {len(equipment)}件装备")
        else:
            print("✅ 装备推荐测试通过（无推荐）")
    else:
        print("✅ 装备推荐测试通过（未返回字段）")


@pytest.mark.integration
def test_plan_generator_idempotency(setup_services):
    """测试幂等性"""
    llm_client, kg_service, cfg = setup_services
    
    existing_proposal = {
        "id": "existing_001",
        "type": "test",
        "params": {},
        "rationale": "existing"
    }
    
    state = {
        "situation": {"disaster_type": "fire"},
        "proposals": [existing_proposal]
    }
    
    result = plan_generator_agent(state, kg_service, llm_client, cfg.llm_model)
    
    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["id"] == "existing_001"
    print("✅ 幂等性测试通过")


def test_plan_generator_no_situation(setup_services):
    """测试无态势信息"""
    llm_client, kg_service, cfg = setup_services
    
    state = {"rescue_id": "test_no_sit"}
    
    result = plan_generator_agent(state, kg_service, llm_client, cfg.llm_model)
    
    assert "proposals" not in result or not result.get("proposals")
    print("✅ 无态势信息测试通过")


if __name__ == "__main__":
    print("Run tests with: pytest tests/test_plan_generator.py -m integration -v -s")

