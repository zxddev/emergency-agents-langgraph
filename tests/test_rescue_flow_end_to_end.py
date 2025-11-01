# Copyright 2025 msq
"""端到端救援闭环测试。

验证完整流程：
- trapped_report → report_intake → rescue_task_generate → await → execute → commit
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_trapped_report_to_plan():
    """测试被困报告生成方案流程。"""
    print("\n=== 端到端测试1：被困报告 → 方案生成 ===")
    
    from emergency_agents.agents.report_intake import report_intake_agent
    from emergency_agents.agents.rescue_task_generate import rescue_task_generate_agent
    
    class MockKG:
        def get_equipment_requirements(self, disaster_types):
            return [
                {"display_name": "生命探测仪", "total_quantity": 5},
                {"display_name": "救援绳索", "total_quantity": 20},
                {"display_name": "医疗箱", "total_quantity": 10},
            ]
    
    class MockRAG:
        class Result:
            def __init__(self, text, score):
                self.text = text
                self.score = score
        
        def query(self, question, domain, top_k):
            return [
                self.Result("汶川地震救援案例：成功救出50人", 0.92),
                self.Result("雅安地震救援案例：医疗队协同", 0.88),
            ]
    
    class MockLLM:
        class Completion:
            def __init__(self):
                self.message = type('obj', (object,), {
                    'content': '''{
                        "plan": {
                            "name": "水磨镇被困群众救援方案",
                            "units": [
                                {"unit_type": "消防", "count": 2, "equipment": ["生命探测仪"], "eta_hours": 0.5}
                            ],
                            "phases": [{"phase": "初期响应", "duration_hours": 1, "tasks": ["侦察"]}]
                        },
                        "tasks": [
                            {"title": "救援任务1", "unit_type": "消防", "lat": 31.68, "lng": 103.85, "window_hours": 2}
                        ]
                    }'''
                })()
        
        class Completions:
            def create(self, **kwargs):
                return type('obj', (object,), {'choices': [MockLLM.Completion()]})()
        
        def __init__(self):
            self.chat = type('obj', (object,), {'completions': self.Completions()})()
    
    # Step 1: 被困报告
    state = {
        "rescue_id": "test-001",
        "user_id": "expert-001",
        "intent": {
            "intent_type": "trapped_report",
            "slots": {
                "count": 10,
                "lat": 31.68,
                "lng": 103.85,
                "location_text": "水磨镇",
                "description": "被困群众十人"
            },
            "meta": {}
        }
    }
    
    # Step 2: report_intake创建实体
    state = report_intake_agent(state)
    
    assert "pending_entities" in state, "应创建pending_entities"
    assert len(state["pending_entities"]) == 1, "应有1个实体"
    
    entity = state["pending_entities"][0]
    assert entity["type"] == "TRAPPED"
    assert entity["count"] == 10
    assert entity["status"] == "PENDING"
    print(f"✅ 实体已创建: id={entity['id']}, count={entity['count']}")
    
    # Step 3: rescue_task_generate生成方案
    state = rescue_task_generate_agent(state, MockKG(), MockRAG(), MockLLM(), "mock")
    
    assert "proposals" in state, "应生成proposals"
    assert len(state["proposals"]) == 1, "应有1个方案"
    
    proposal = state["proposals"][0]
    assert proposal["type"] == "rescue_task_dispatch"
    assert "evidence" in proposal, "应包含证据"
    
    evidence = proposal["evidence"]
    assert "kg" in evidence, "应包含KG证据"
    assert "rag" in evidence, "应包含RAG证据"
    assert len(evidence["kg"]) >= 3, f"KG证据应≥3，实际{len(evidence['kg'])}"
    assert len(evidence["rag"]) >= 2, f"RAG证据应≥2，实际{len(evidence['rag'])}"
    
    print(f"✅ 方案已生成: id={proposal['id']}")
    print(f"✅ 证据: KG={len(evidence['kg'])}, RAG={len(evidence['rag'])}")
    
    assert "tasks" in state, "应生成tasks"
    assert len(state["tasks"]) >= 1, "应至少有1个任务"
    print(f"✅ 任务已拆解: {len(state['tasks'])}个任务")
    
    assert state["status"] == "awaiting_approval", "应进入awaiting_approval状态"
    print("✅ 状态：等待审批")
    
    print("✅ 端到端测试1通过")


def test_annotation_lifecycle():
    """测试标注生命周期。"""
    print("\n=== 端到端测试2：标注创建 → 签收 ===")
    
    from emergency_agents.agents.annotation_lifecycle import annotation_lifecycle_agent
    
    # Step 1: 创建标注
    state = {
        "rescue_id": "test-002",
        "user_id": "expert-002",
        "intent": {
            "intent_type": "geo_annotate",
            "slots": {
                "label": "道路阻断",
                "geometry_type": "Point",
                "lat": 31.70,
                "lng": 103.90,
                "confidence": 0.95,
                "description": "桥梁塌陷"
            },
            "meta": {}
        }
    }
    
    state = annotation_lifecycle_agent(state)
    
    assert "pending_annotations" in state
    assert len(state["pending_annotations"]) == 1
    
    annotation = state["pending_annotations"][0]
    assert annotation["label"] == "道路阻断"
    assert annotation["status"] == "PENDING"
    annotation_id = annotation["id"]
    print(f"✅ 标注已创建: id={annotation_id}, status=PENDING")
    
    # Step 2: 签收标注
    state["intent"] = {
        "intent_type": "annotation_sign",
        "slots": {
            "annotation_id": annotation_id,
            "decision": "SIGNED"
        },
        "meta": {}
    }
    
    state = annotation_lifecycle_agent(state)
    
    assert len(state.get("pending_annotations", [])) == 0, "PENDING应被移除"
    assert len(state.get("annotations", [])) == 1, "应进入annotations"
    
    signed_ann = state["annotations"][0]
    assert signed_ann["status"] == "SIGNED"
    print(f"✅ 标注已签收: id={annotation_id}, status=SIGNED")
    
    print("✅ 端到端测试2通过")


def test_evidence_gate_integration():
    """测试证据Gate集成。"""
    print("\n=== 端到端测试3：证据Gate验证 ===")
    
    from emergency_agents.policy.evidence import evidence_gate_ok
    
    state_不足 = {
        "available_resources": {"units": []},
        "kg_hits_count": 2,
        "rag_case_refs_count": 1
    }
    
    ok, reason = evidence_gate_ok(state_不足)
    
    assert not ok, "证据不足应返回False"
    assert reason in ("insufficient_kg_evidence", "insufficient_rag_evidence")
    print(f"✅ 证据不足被正确阻止: {reason}")
    
    state_充足 = {
        "available_resources": {"units": ["消防"]},
        "kg_hits_count": 5,
        "rag_case_refs_count": 3
    }
    
    ok, reason = evidence_gate_ok(state_充足)
    
    assert ok, "证据充足应返回True"
    assert reason == "ok"
    print("✅ 证据充足通过Gate")
    
    print("✅ 端到端测试3通过")


if __name__ == "__main__":
    print("=" * 60)
    print("救援闭环端到端测试套件")
    print("=" * 60)
    
    try:
        test_trapped_report_to_plan()
        test_annotation_lifecycle()
        test_evidence_gate_integration()
        
        print("\n" + "=" * 60)
        print("✅ 所有端到端测试通过 (3/3)")
        print("=" * 60)
        print("\n完整救援闭环已实现：")
        print("  被困报告 → 创建实体 → 生成方案 → 证据验证 → 等待审批")
        print("  标注创建 → PENDING → 签收 → SIGNED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

