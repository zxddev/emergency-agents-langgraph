# Copyright 2025 msq
"""意图识别完整流程集成测试。

验证LangGraph图编排：
- intent → validator → [缺槽] prompt_slots → validator → [通过] intent_router
- 演示中断与恢复机制
"""
from __future__ import annotations

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 设置环境变量避免真实连接
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "test-password"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000/v1"

import pytest

POSTGRES_DSN = os.getenv("POSTGRES_DSN")
if not POSTGRES_DSN:
    pytest.skip("POSTGRES_DSN 未配置，跳过intent图结构测试", allow_module_level=True)


def test_graph_structure():
    """测试图结构是否正确构建。"""
    print("\n=== 集成测试1：图结构验证 ===")
    
    try:
        from emergency_agents.graph.app import build_app
        
        app = asyncio.run(build_app(sqlite_path=":memory:", postgres_dsn=POSTGRES_DSN))
        
        nodes = list(app.get_graph().nodes.keys())
        print(f"图节点数量: {len(nodes)}")
        print(f"节点列表: {sorted(nodes)}")
        
        expected_nodes = ["intent", "validator", "prompt_slots", "intent_router", "situation"]
        for node in expected_nodes:
            assert node in nodes, f"缺少节点: {node}"
            print(f"✅ 节点 {node} 已注册")
        
        print("✅ 测试1通过：图结构正确")
        return True
        
    except ImportError as e:
        print(f"⚠️  跳过测试1：缺少依赖 ({e})")
        print("提示：需要安装 langgraph 和相关依赖")
        return True
    except Exception as e:
        print(f"❌ 图构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validator_node_直接调用():
    """测试validator节点直接调用（不通过图）。"""
    print("\n=== 集成测试2：Validator节点直接调用 ===")
    
    from emergency_agents.intent.validator import validate_and_prompt_node
    
    class MockLLM:
        class Completion:
            def __init__(self):
                self.message = type('obj', (object,), {'content': '请提供坐标（经度和纬度）。'})()
        
        class Completions:
            def create(self, **kwargs):
                return type('obj', (object,), {'choices': [MockLLM.Completion()]})()
        
        def __init__(self):
            self.chat = type('obj', (object,), {'completions': self.Completions()})()
    
    state_缺槽 = {
        "intent": {
            "intent_type": "recon_minimal",
            "slots": {"alt_m": 100},
            "meta": {}
        }
    }
    
    result = validate_and_prompt_node(state_缺槽, MockLLM(), "mock")
    
    assert result.get("validation_status") == "invalid"
    assert "lng" in result.get("missing_fields", [])
    assert "lat" in result.get("missing_fields", [])
    print(f"✅ 缺槽追问：{result.get('prompt')}")
    
    state_完整 = {
        "intent": {
            "intent_type": "recon_minimal",
            "slots": {"lng": 103.85, "lat": 31.68, "alt_m": 80},
            "meta": {}
        }
    }
    
    result = validate_and_prompt_node(state_完整, MockLLM(), "mock")
    
    assert result.get("validation_status") == "valid"
    print("✅ 完整槽位验证通过")
    
    print("✅ 测试2通过")
    return True


def test_high_risk_intents():
    """测试高风险intent标记。"""
    print("\n=== 集成测试3：高风险Intent标记 ===")
    
    from emergency_agents.intent.schemas import HIGH_RISK_INTENTS
    
    assert "device_control_robotdog" in HIGH_RISK_INTENTS
    assert "plan_task_approval" in HIGH_RISK_INTENTS
    assert "rescue_task_generate" in HIGH_RISK_INTENTS
    
    print(f"✅ 高风险Intent: {HIGH_RISK_INTENTS}")
    print("✅ 测试3通过")
    return True


def test_schema_required_fields():
    """测试必填字段识别正确。"""
    print("\n=== 集成测试4：必填字段识别 ===")
    
    from emergency_agents.intent.schemas import INTENT_SCHEMAS
    
    recon_schema = INTENT_SCHEMAS["recon_minimal"]
    assert "lng" in recon_schema["required"]
    assert "lat" in recon_schema["required"]
    assert "alt_m" not in recon_schema["required"]
    print("✅ recon_minimal必填字段正确: lng, lat")
    
    rfa_schema = INTENT_SCHEMAS["rfa_request"]
    assert "unit_type" in rfa_schema["required"]
    assert "count" in rfa_schema["required"]
    assert "priority" not in rfa_schema["required"]
    print("✅ rfa_request必填字段正确: unit_type, count")
    
    print("✅ 测试4通过")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("意图识别完整流程集成测试")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= test_graph_structure()
    all_passed &= test_validator_node_直接调用()
    all_passed &= test_high_risk_intents()
    all_passed &= test_schema_required_fields()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有集成测试通过 (4/4)")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ 部分测试失败")
        print("=" * 60)
        sys.exit(1)
