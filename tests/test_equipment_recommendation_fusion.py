# Copyright 2025 msq
"""装备推荐融合端到端测试。

验证完整流程：
- KG装备标准查询
- RAG历史案例检索
- LLM提取装备信息
- 融合构建完整证据链
- 可追溯性验证（Cypher查询+Qdrant chunk_id）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


def test_equipment_extraction_from_rag_cases():
    """测试从RAG案例中提取装备信息（LLM结构化输出）。"""
    print("\n=== 测试1：装备提取 ===")

    from emergency_agents.rag.equipment_extractor import extract_equipment_from_cases
    from emergency_agents.rag.pipe import RagChunk

    # 模拟RAG检索结果
    rag_cases = [
        RagChunk(
            text="2008年汶川地震救援中，救援队使用生命探测仪18台，成功定位多个被困点。配备救援绳索50根，医疗箱20个。",
            source="wenchuan_2008_case",
            loc="p1"
        ),
        RagChunk(
            text="雅安地震救援经验：每个救援小组标配生命探测仪2台，医疗急救箱5个，用于快速响应。",
            source="yaan_2013_case",
            loc="p3"
        ),
    ]

    # 模拟LLM客户端
    class MockLLM:
        class Completion:
            def __init__(self):
                self.message = type('obj', (object,), {
                    'content': '''[
                        {
                            "name": "生命探测仪",
                            "quantity": 18,
                            "context": "救援队使用生命探测仪18台，成功定位多个被困点",
                            "confidence": 1.0,
                            "source_chunk_id": "case_1"
                        },
                        {
                            "name": "救援绳索",
                            "quantity": 50,
                            "context": "配备救援绳索50根",
                            "confidence": 0.95,
                            "source_chunk_id": "case_1"
                        },
                        {
                            "name": "医疗箱",
                            "quantity": 20,
                            "context": "医疗箱20个",
                            "confidence": 0.95,
                            "source_chunk_id": "case_1"
                        },
                        {
                            "name": "生命探测仪",
                            "quantity": 2,
                            "context": "每个救援小组标配生命探测仪2台",
                            "confidence": 0.98,
                            "source_chunk_id": "case_2"
                        },
                        {
                            "name": "医疗急救箱",
                            "quantity": 5,
                            "context": "医疗急救箱5个，用于快速响应",
                            "confidence": 0.92,
                            "source_chunk_id": "case_2"
                        }
                    ]'''
                })()

        class Completions:
            def create(self, **kwargs):
                return type('obj', (object,), {'choices': [MockLLM.Completion()]})()

        def __init__(self):
            self.chat = type('obj', (object,), {'completions': self.Completions()})()

    llm_client = MockLLM()

    # 执行提取
    extracted = extract_equipment_from_cases(
        cases=rag_cases,
        llm_client=llm_client,
        llm_model="glm-4-flash"
    )

    # 验证
    assert len(extracted) == 5, f"应提取5项装备，实际: {len(extracted)}"

    # 验证第一项（应按置信度排序）
    first = extracted[0]
    assert first.name == "生命探测仪"
    assert first.quantity == 18
    assert first.confidence == 1.0
    assert first.source_chunk_id == "case_1"
    assert "18台" in first.context

    # 验证追溯信息完整
    for eq in extracted:
        assert eq.name.strip() != ""
        assert eq.context.strip() != ""
        assert 0.0 <= eq.confidence <= 1.0
        assert eq.source_chunk_id.startswith("case_")

    print(f"✅ 成功提取{len(extracted)}项装备信息")
    for eq in extracted:
        print(f"  - {eq.name}: {eq.quantity}件 (置信度: {eq.confidence})")


def test_evidence_fusion_kg_plus_rag():
    """测试KG标准与RAG案例融合（完整证据链）。"""
    print("\n=== 测试2：证据融合 ===")

    from emergency_agents.rag.evidence_builder import build_equipment_recommendations
    from emergency_agents.rag.equipment_extractor import ExtractedEquipment
    from emergency_agents.rag.pipe import RagChunk

    # 模拟KG标准数据
    kg_standards = [
        {
            "equipment_name": "life_detector",
            "display_name": "生命探测仪",
            "total_quantity": 15,
            "max_urgency": 9,
            "category": "探测",
            "for_disasters": ["people_trapped"]
        },
        {
            "equipment_name": "medical_kit",
            "display_name": "医疗箱",
            "total_quantity": 10,
            "max_urgency": 8,
            "category": "医疗",
            "for_disasters": ["people_trapped"]
        },
    ]

    # 模拟RAG案例
    rag_cases = [
        RagChunk(
            text="汶川救援使用生命探测仪18台，医疗箱25个",
            source="wenchuan_2008",
            loc="p1"
        ),
        RagChunk(
            text="雅安救援配备生命探测仪20台",
            source="yaan_2013",
            loc="p2"
        ),
    ]

    # 模拟提取结果
    extracted_equipment = [
        ExtractedEquipment(
            name="生命探测仪",
            quantity=18,
            context="汶川救援使用生命探测仪18台",
            confidence=1.0,
            source_chunk_id="case_1"
        ),
        ExtractedEquipment(
            name="生命探测仪",
            quantity=20,
            context="雅安救援配备生命探测仪20台",
            confidence=0.98,
            source_chunk_id="case_2"
        ),
        ExtractedEquipment(
            name="医疗箱",
            quantity=25,
            context="医疗箱25个",
            confidence=0.95,
            source_chunk_id="case_1"
        ),
    ]

    # 执行融合
    recommendations = build_equipment_recommendations(
        kg_standards=kg_standards,
        rag_cases=rag_cases,
        extracted_equipment=extracted_equipment,
        disaster_types=["people_trapped"]
    )

    # 验证推荐结果
    assert len(recommendations) == 2, f"应生成2项推荐，实际: {len(recommendations)}"

    # 验证生命探测仪推荐（KG+RAG都有）
    life_detector_rec = next((r for r in recommendations if r.equipment_name == "life_detector"), None)
    assert life_detector_rec is not None, "缺少生命探测仪推荐"

    # KG标准15台，RAG平均(18+20)/2=19台，应推荐max(15,19)*1.1=20.9≈21台
    assert life_detector_rec.recommended_quantity >= 19, f"推荐数量应≥19，实际: {life_detector_rec.recommended_quantity}"
    assert life_detector_rec.confidence_level == "高", f"置信水平应为'高'，实际: {life_detector_rec.confidence_level}"

    # 验证KG证据
    assert life_detector_rec.kg_evidence is not None
    assert life_detector_rec.kg_evidence.standard_quantity == 15
    assert life_detector_rec.kg_evidence.urgency == 9
    assert "REQUIRES" in life_detector_rec.kg_evidence.cypher_query

    # 验证RAG证据
    assert len(life_detector_rec.rag_evidence) == 2, "应有2条RAG证据"
    for rag_ev in life_detector_rec.rag_evidence:
        assert rag_ev.equipment_name == "生命探测仪"
        assert rag_ev.quantity in [18, 20]
        assert rag_ev.qdrant_chunk_id  # 可追溯到Qdrant

    # 验证推理逻辑
    assert "KG标准" in life_detector_rec.reasoning
    assert "历史案例" in life_detector_rec.reasoning

    print(f"✅ 成功融合{len(recommendations)}项装备推荐")
    for rec in recommendations:
        print(f"  - {rec.display_name}: 推荐{rec.recommended_quantity}件 (置信度: {rec.confidence_level})")
        if rec.kg_evidence:
            print(f"    KG标准: {rec.kg_evidence.standard_quantity}件")
        if rec.rag_evidence:
            print(f"    RAG案例: {len(rec.rag_evidence)}条")


def test_complete_traceability():
    """测试完整可追溯性（Cypher查询+Qdrant chunk_id）。"""
    print("\n=== 测试3：完整追溯性 ===")

    from emergency_agents.rag.evidence_builder import build_equipment_recommendations, KGEvidence, RAGEvidence
    from emergency_agents.rag.equipment_extractor import ExtractedEquipment
    from emergency_agents.rag.pipe import RagChunk

    kg_standards = [{
        "equipment_name": "life_detector",
        "display_name": "生命探测仪",
        "total_quantity": 15,
        "max_urgency": 9,
        "category": "探测",
        "for_disasters": ["people_trapped"]
    }]

    rag_cases = [RagChunk(text="使用生命探测仪20台", source="case_001", loc="p5")]

    extracted = [ExtractedEquipment(
        name="生命探测仪",
        quantity=20,
        context="使用生命探测仪20台",
        confidence=1.0,
        source_chunk_id="case_1"
    )]

    recommendations = build_equipment_recommendations(
        kg_standards=kg_standards,
        rag_cases=rag_cases,
        extracted_equipment=extracted,
        disaster_types=["people_trapped"]
    )

    rec = recommendations[0]

    # 验证KG追溯性
    assert rec.kg_evidence is not None
    cypher = rec.kg_evidence.cypher_query
    assert "MATCH" in cypher
    assert "Equipment" in cypher
    assert "people_trapped" in cypher
    print(f"✅ KG Cypher查询可验证:\n{cypher}")

    # 验证RAG追溯性
    assert len(rec.rag_evidence) == 1
    rag_ev = rec.rag_evidence[0]
    assert rag_ev.qdrant_chunk_id == "case_001:p5"
    print(f"✅ RAG Qdrant chunk_id可追溯: {rag_ev.qdrant_chunk_id}")

    # 验证完整的to_dict()输出
    rec_dict = rec.to_dict()
    assert "kg_evidence" in rec_dict
    assert "rag_evidence" in rec_dict
    assert "reasoning" in rec_dict
    assert "confidence_level" in rec_dict

    assert rec_dict["kg_evidence"]["cypher_query"]
    assert rec_dict["rag_evidence"][0]["qdrant_chunk_id"]

    print("✅ 完整证据链可序列化为JSON")


def test_confidence_level_calculation():
    """测试置信水平计算（高/中/低）。"""
    print("\n=== 测试4：置信水平计算 ===")

    from emergency_agents.rag.evidence_builder import build_equipment_recommendations
    from emergency_agents.rag.equipment_extractor import ExtractedEquipment
    from emergency_agents.rag.pipe import RagChunk

    # 场景1：KG+RAG都有 → 高置信度
    kg_both = [{"equipment_name": "eq1", "display_name": "装备1", "total_quantity": 10, "max_urgency": 8, "category": "test", "for_disasters": ["test"]}]
    rag_both = [RagChunk(text="装备1使用10件", source="case1", loc="p1")]
    extracted_both = [ExtractedEquipment(name="装备1", quantity=10, context="装备1使用10件", confidence=0.95, source_chunk_id="case_1")]

    rec_both = build_equipment_recommendations(kg_both, rag_both, extracted_both, ["test"])[0]
    assert rec_both.confidence_level == "高", "KG+RAG应为高置信度"
    print("✅ 场景1(KG+RAG): 高置信度")

    # 场景2：仅KG → 中置信度
    kg_only = [{"equipment_name": "eq2", "display_name": "装备2", "total_quantity": 5, "max_urgency": 7, "category": "test", "for_disasters": ["test"]}]
    rag_only_kg = []
    extracted_only_kg = []

    rec_only_kg = build_equipment_recommendations(kg_only, rag_only_kg, extracted_only_kg, ["test"])[0]
    assert rec_only_kg.confidence_level == "中", "仅KG应为中置信度"
    print("✅ 场景2(仅KG): 中置信度")

    # 场景3：仅RAG高置信度提取 → 中置信度
    kg_none = []
    rag_only_rag = [RagChunk(text="装备3使用20件", source="case2", loc="p2")]
    extracted_only_rag = [ExtractedEquipment(name="装备3", quantity=20, context="装备3使用20件", confidence=0.88, source_chunk_id="case_1")]

    rec_only_rag = build_equipment_recommendations(kg_none, rag_only_rag, extracted_only_rag, ["test"])[0]
    assert rec_only_rag.confidence_level in ["中", "低"], "仅RAG应为中或低置信度"
    print(f"✅ 场景3(仅RAG): {rec_only_rag.confidence_level}置信度")


@pytest.mark.integration
def test_rescue_task_generate_integration():
    """测试救援方案生成Agent完整集成（含新融合逻辑）。"""
    print("\n=== 测试5：救援方案生成完整集成 ===")

    from emergency_agents.agents.rescue_task_generate import rescue_task_generate_agent
    from emergency_agents.rag.pipe import RagChunk

    # 模拟KG服务
    class MockKG:
        def get_equipment_requirements(self, disaster_types):
            return [
                {
                    "equipment_name": "life_detector",
                    "display_name": "生命探测仪",
                    "total_quantity": 15,
                    "max_urgency": 9,
                    "category": "探测",
                    "for_disasters": disaster_types
                },
                {
                    "equipment_name": "rescue_rope",
                    "display_name": "救援绳索",
                    "total_quantity": 30,
                    "max_urgency": 8,
                    "category": "救援",
                    "for_disasters": disaster_types
                },
            ]

    # 模拟RAG管道
    class MockRAG:
        def query(self, question, domain, top_k):
            return [
                RagChunk(
                    text="汶川地震救援：调用生命探测仪18台，救援绳索50根，成功救出被困群众",
                    source="wenchuan_2008",
                    loc="p1"
                ),
                RagChunk(
                    text="雅安地震经验：生命探测仪20台，快速定位被困位置",
                    source="yaan_2013",
                    loc="p3"
                ),
            ]

    # 模拟LLM客户端（需要2次调用：1次提取装备，1次生成方案）
    call_count = 0

    class MockLLM:
        class Completion:
            def __init__(self, call_num):
                if call_num == 1:
                    # 第1次调用：装备提取
                    content = '''[
                        {"name": "生命探测仪", "quantity": 18, "context": "调用生命探测仪18台", "confidence": 1.0, "source_chunk_id": "case_1"},
                        {"name": "救援绳索", "quantity": 50, "context": "救援绳索50根", "confidence": 0.95, "source_chunk_id": "case_1"},
                        {"name": "生命探测仪", "quantity": 20, "context": "生命探测仪20台", "confidence": 0.98, "source_chunk_id": "case_2"}
                    ]'''
                else:
                    # 第2次调用：方案生成
                    content = '''{
                        "plan": {
                            "name": "水磨镇救援方案",
                            "units": [{"unit_type": "消防", "count": 2, "equipment": ["生命探测仪"], "eta_hours": 0.5}],
                            "phases": [{"phase": "初期响应", "duration_hours": 1, "tasks": ["侦察"]}]
                        },
                        "tasks": [{"title": "救援任务1", "unit_type": "消防", "lat": 31.68, "lng": 103.85, "window_hours": 2}]
                    }'''

                self.message = type('obj', (object,), {'content': content})()

        class Completions:
            def __init__(self):
                self.call_count = 0

            def create(self, **kwargs):
                self.call_count += 1
                return type('obj', (object,), {'choices': [MockLLM.Completion(self.call_count)]})()

        def __init__(self):
            self.chat = type('obj', (object,), {'completions': self.Completions()})()

    # 构造状态
    state = {
        "rescue_id": "test-equipment-fusion",
        "user_id": "expert-001",
        "pending_entities": [
            {
                "id": "entity-001",
                "type": "TRAPPED",
                "count": 50,
                "lat": 31.68,
                "lng": 103.85,
                "location_text": "水磨镇"
            }
        ],
        "timeline": []
    }

    # 执行Agent
    result_state = rescue_task_generate_agent(
        state=state,
        kg_service=MockKG(),
        rag_pipeline=MockRAG(),
        llm_client=MockLLM(),
        llm_model="glm-4-flash"
    )

    # 验证结果
    assert "proposals" in result_state
    assert len(result_state["proposals"]) == 1

    proposal = result_state["proposals"][0]
    evidence = proposal["evidence"]

    # 验证新的证据结构
    assert "equipment_recommendations" in evidence, "缺少equipment_recommendations字段"
    assert "fusion_summary" in evidence, "缺少fusion_summary字段"

    # 验证装备推荐
    equipment_recommendations = evidence["equipment_recommendations"]
    assert len(equipment_recommendations) >= 1, "应至少有1项装备推荐"

    first_rec = equipment_recommendations[0]
    assert "equipment_name" in first_rec
    assert "display_name" in first_rec
    assert "recommended_quantity" in first_rec
    assert "kg_evidence" in first_rec
    assert "rag_evidence" in first_rec
    assert "reasoning" in first_rec
    assert "confidence_level" in first_rec

    # 验证追溯性
    if first_rec["kg_evidence"]:
        assert "cypher_query" in first_rec["kg_evidence"]
        assert "MATCH" in first_rec["kg_evidence"]["cypher_query"]

    if first_rec["rag_evidence"]:
        assert len(first_rec["rag_evidence"]) > 0
        assert "qdrant_chunk_id" in first_rec["rag_evidence"][0]

    # 验证融合摘要
    fusion_summary = evidence["fusion_summary"]
    assert fusion_summary["kg_standards_count"] == 2
    assert fusion_summary["rag_cases_count"] == 2
    assert fusion_summary["extracted_equipment_count"] == 3
    assert fusion_summary["final_recommendations_count"] >= 1

    print("✅ 救援方案生成完整集成测试通过")
    print(f"  - 装备推荐: {len(equipment_recommendations)}项")
    print(f"  - KG标准: {fusion_summary['kg_standards_count']}项")
    print(f"  - RAG案例: {fusion_summary['rag_cases_count']}条")
    print(f"  - 提取装备: {fusion_summary['extracted_equipment_count']}项")


if __name__ == "__main__":
    test_equipment_extraction_from_rag_cases()
    test_evidence_fusion_kg_plus_rag()
    test_complete_traceability()
    test_confidence_level_calculation()
    test_rescue_task_generate_integration()

    print("\n" + "="*60)
    print("✅ 所有测试通过！装备推荐融合系统工作正常。")
    print("="*60)
