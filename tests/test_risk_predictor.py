# Copyright 2025 msq
import pytest
from emergency_agents.agents.risk_predictor import risk_predictor_agent
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig
from emergency_agents.graph.kg_service import KGService, KGConfig
from emergency_agents.rag.pipe import RagPipeline


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
    
    rag_pipeline = RagPipeline(
        qdrant_url=cfg.qdrant_url or "http://localhost:6333",
        embedding_model=cfg.embedding_model,
        embedding_dim=cfg.embedding_dim,
        openai_base_url=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        llm_model=cfg.llm_model
    )
    
    return llm_client, kg_service, rag_pipeline, cfg


@pytest.mark.integration
def test_risk_predictor_earthquake(setup_services):
    """测试地震的风险预测
    
    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 854-871
    """
    llm_client, kg_service, rag_pipeline, cfg = setup_services
    
    state = {
        "rescue_id": "test_risk_001",
        "situation": {
            "disaster_type": "earthquake",
            "magnitude": 7.8,
            "epicenter": {"lat": 31.0, "lng": 103.4},
            "affected_area": "汶川县",
            "nearby_facilities": ["水库", "化工厂"]
        }
    }
    
    result = risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)
    
    assert "predicted_risks" in result
    risks = result["predicted_risks"]
    
    assert len(risks) > 0, "Should predict at least one secondary disaster"
    
    for risk in risks:
        assert "type" in risk
        assert "probability" in risk
        assert 0.0 <= risk["probability"] <= 1.0
        if "rationale" in risk:
            assert len(risk["rationale"]) > 0
    
    risk_types = [r["type"] for r in risks]
    has_expected_risk = any(rt in ["flood", "landslide", "chemical_leak", "洪水", "滑坡", "泄露"] for rt in risk_types)
    assert has_expected_risk, f"Should predict flood/landslide/chemical_leak, got: {risk_types}"
    
    print(f"✅ 风险预测测试通过: {len(risks)}个风险")
    for risk in risks:
        print(f"  - {risk.get('display_name', risk['type'])}: {risk['probability']:.2f}")


@pytest.mark.integration
def test_risk_predictor_idempotency(setup_services):
    """测试幂等性"""
    llm_client, kg_service, rag_pipeline, cfg = setup_services
    
    state = {
        "situation": {"disaster_type": "earthquake", "magnitude": 7.0},
        "predicted_risks": [{"type": "flood", "probability": 0.8}]
    }
    
    result = risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)
    
    assert len(result["predicted_risks"]) == 1
    assert result["predicted_risks"][0]["type"] == "flood"
    print("✅ 幂等性测试通过")


@pytest.mark.integration
def test_risk_predictor_compound_risks(setup_services):
    """测试复合风险识别"""
    llm_client, kg_service, rag_pipeline, cfg = setup_services
    
    state = {
        "situation": {
            "disaster_type": "earthquake",
            "magnitude": 7.5,
            "affected_area": "化工园区"
        }
    }
    
    result = risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)
    
    if "compound_risks" in result and len(result["compound_risks"]) > 0:
        compound = result["compound_risks"][0]
        assert "multiplier" in compound or "severity_multiplier" in compound
        print(f"✅ 复合风险测试通过: {compound}")
    else:
        print("✅ 未检测到复合风险（正常情况）")


def test_risk_predictor_no_situation(setup_services):
    """测试无态势信息"""
    llm_client, kg_service, rag_pipeline, cfg = setup_services
    
    state = {"rescue_id": "test_no_sit"}
    
    result = risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)
    
    assert "predicted_risks" not in result or not result.get("predicted_risks")
    print("✅ 无态势信息测试通过")


if __name__ == "__main__":
    print("Run tests with: pytest tests/test_risk_predictor.py -m integration -v -s")

