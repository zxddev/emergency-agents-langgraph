# Copyright 2025 msq
import pytest
from emergency_agents.graph.app import build_app
from langgraph.types import Command
from emergency_agents.config import AppConfig


@pytest.mark.integration
def test_full_workflow():
    """测试完整的工作流程：态势感知 → 风险预测 → 方案生成 → 人工审批
    
    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 362-401
    """
    cfg = AppConfig.load_from_env()
    app = build_app(cfg.checkpoint_sqlite_path, cfg.postgres_dsn)
    
    init_state = {
        "rescue_id": "integration_test_001",
        "user_id": "test_user",
        "raw_report": "四川汶川发生7.8级地震，震中位于北纬31.0度、东经103.4度。震中附近有紫坪铺水库和多家化工厂。"
    }
    
    thread_id = f"rescue-{init_state['rescue_id']}"
    config = {"configurable": {"thread_id": thread_id}}
    
    result = app.invoke(init_state, config=config)
    
    assert "situation" in result
    assert result["situation"]["disaster_type"] in ["earthquake", "地震"]
    print(f"✅ Step 1: 态势感知完成 - {result['situation']['disaster_type']}")
    
    assert "predicted_risks" in result
    assert len(result["predicted_risks"]) > 0
    print(f"✅ Step 2: 风险预测完成 - {len(result['predicted_risks'])}个风险")
    
    assert "proposals" in result
    assert len(result["proposals"]) > 0
    assert result["status"] == "awaiting_approval"
    print(f"✅ Step 3: 方案生成完成 - {len(result['proposals'])}个提案")
    
    approved_ids = [result["proposals"][0]["id"]]
    result2 = app.invoke(Command(resume=approved_ids), config=config)
    
    assert "executed_actions" in result2
    print(f"✅ Step 4: 执行完成")
    
    print("\n✅ 完整工作流程测试通过!")


if __name__ == "__main__":
    print("Run with: pytest tests/test_integration_workflow.py -m integration -v -s")

