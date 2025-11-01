# Copyright 2025 msq
"""装备推荐证据构建器。

职责：
- 融合KG装备标准与RAG历史案例提取结果
- 构建完整证据链：KG来源+RAG案例+推理逻辑
- 计算置信水平（高/中/低）
- 提供可追溯的证据标识（Cypher查询+Qdrant chunk_id）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Literal, Optional
from collections import defaultdict

from emergency_agents.rag.equipment_extractor import ExtractedEquipment
from emergency_agents.rag.pipe import RagChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KGEvidence:
    """KG装备标准证据（不可变）。

    Attributes:
        equipment_name: KG中的装备标准名称。
        display_name: 装备显示名称（中文）。
        standard_quantity: 标准配置数量。
        urgency: 紧急程度（1-10）。
        category: 装备类别（如"探测"、"救援"）。
        for_disasters: 适用的灾害类型列表。
        cypher_query: 可重现的Cypher查询语句（用于验证）。
    """
    equipment_name: str
    display_name: str
    standard_quantity: int
    urgency: int
    category: str
    for_disasters: List[str]
    cypher_query: str

    def __post_init__(self) -> None:
        if self.standard_quantity < 0:
            raise ValueError(f"标准数量不能为负: {self.standard_quantity}")
        if self.urgency < 1 or self.urgency > 10:
            raise ValueError(f"紧急程度必须在[1,10]范围内: {self.urgency}")


@dataclass(frozen=True)
class RAGEvidence:
    """RAG历史案例证据（不可变）。

    Attributes:
        case_source: 案例来源（如"wenchuan_2008"）。
        equipment_name: 提取的装备名称。
        quantity: 案例中使用的数量（None表示未提及）。
        context_snippet: 原文片段（30-80字）。
        confidence: 提取置信度（0.0-1.0）。
        qdrant_chunk_id: Qdrant中的chunk标识（用于回溯原文）。
    """
    case_source: str
    equipment_name: str
    quantity: Optional[int]
    context_snippet: str
    confidence: float
    qdrant_chunk_id: str

    def __post_init__(self) -> None:
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f"置信度必须在[0.0,1.0]范围内: {self.confidence}")
        if self.quantity is not None and self.quantity < 0:
            raise ValueError(f"数量不能为负: {self.quantity}")


@dataclass(frozen=True)
class EquipmentRecommendation:
    """装备推荐结果（含完整证据链，不可变）。

    Attributes:
        equipment_name: 装备名称（优先使用KG标准名称）。
        display_name: 装备显示名称。
        recommended_quantity: 推荐配置数量。
        kg_evidence: KG标准证据，None表示KG中无此装备。
        rag_evidence: RAG案例证据列表，空列表表示无历史案例。
        reasoning: 推荐理由（解释数量来源和融合逻辑）。
        confidence_level: 置信水平（高/中/低）。
    """
    equipment_name: str
    display_name: str
    recommended_quantity: int
    kg_evidence: Optional[KGEvidence]
    rag_evidence: List[RAGEvidence]
    reasoning: str
    confidence_level: Literal["高", "中", "低"]

    def __post_init__(self) -> None:
        if self.recommended_quantity < 0:
            raise ValueError(f"推荐数量不能为负: {self.recommended_quantity}")
        if not self.kg_evidence and not self.rag_evidence:
            raise ValueError("必须至少有KG证据或RAG证据之一")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于API返回）。"""
        return {
            "equipment_name": self.equipment_name,
            "display_name": self.display_name,
            "recommended_quantity": self.recommended_quantity,
            "kg_evidence": {
                "equipment_name": self.kg_evidence.equipment_name,
                "standard_quantity": self.kg_evidence.standard_quantity,
                "urgency": self.kg_evidence.urgency,
                "category": self.kg_evidence.category,
                "for_disasters": self.kg_evidence.for_disasters,
                "cypher_query": self.kg_evidence.cypher_query,
            } if self.kg_evidence else None,
            "rag_evidence": [
                {
                    "case_source": ev.case_source,
                    "equipment_name": ev.equipment_name,
                    "quantity": ev.quantity,
                    "context_snippet": ev.context_snippet,
                    "confidence": ev.confidence,
                    "qdrant_chunk_id": ev.qdrant_chunk_id,
                }
                for ev in self.rag_evidence
            ],
            "reasoning": self.reasoning,
            "confidence_level": self.confidence_level,
        }


def build_equipment_recommendations(
    kg_standards: List[Dict[str, Any]],
    rag_cases: List[RagChunk],
    extracted_equipment: List[ExtractedEquipment],
    disaster_types: List[str]
) -> List[EquipmentRecommendation]:
    """构建装备推荐结果（融合KG标准与RAG案例）。

    融合逻辑：
    1. KG+RAG都有：高置信度，取max(KG标准, RAG平均值)
    2. 仅KG有：中-高置信度，使用KG标准数量
    3. 仅RAG有：中-低置信度，使用RAG平均值或中位数

    Args:
        kg_standards: KG查询结果（来自KGService.get_equipment_requirements）。
        rag_cases: RAG原始检索案例（用于构建RAG证据追溯）。
        extracted_equipment: 从RAG案例中提取的装备列表。
        disaster_types: 当前灾害类型列表（用于生成Cypher查询）。

    Returns:
        装备推荐列表，按紧急程度+置信度排序。

    Example:
        >>> kg = [{"equipment_name": "life_detector", "display_name": "生命探测仪", "total_quantity": 15, ...}]
        >>> rag_cases = [RagChunk(text="使用生命探测仪18台...", source="wenchuan_2008", loc="p1")]
        >>> extracted = [ExtractedEquipment(name="生命探测仪", quantity=18, ...)]
        >>> recommendations = build_equipment_recommendations(kg, rag_cases, extracted, ["people_trapped"])
        >>> recommendations[0].recommended_quantity
        20  # max(15, avg(18)) = 18, 向上取整+10%安全余量 = 20
    """
    if not kg_standards and not extracted_equipment:
        logger.warning("无KG标准且无RAG提取结果，无法生成装备推荐")
        return []

    # 构建KG证据字典 {display_name -> KGEvidence}
    kg_evidence_map: Dict[str, KGEvidence] = {}
    for kg_item in kg_standards:
        # 生成可重现的Cypher查询
        cypher = f"""MATCH (d:Disaster)-[r:REQUIRES]->(eq:Equipment {{name: "{kg_item['equipment_name']}"}})
WHERE d.name IN {disaster_types}
RETURN eq.display_name, sum(r.quantity) AS total_quantity, max(r.urgency) AS urgency"""

        kg_ev = KGEvidence(
            equipment_name=kg_item["equipment_name"],
            display_name=kg_item["display_name"],
            standard_quantity=int(kg_item["total_quantity"]),
            urgency=int(kg_item.get("max_urgency", 5)),
            category=kg_item.get("category", "未分类"),
            for_disasters=kg_item.get("for_disasters", disaster_types),
            cypher_query=cypher
        )
        kg_evidence_map[kg_ev.display_name] = kg_ev

    # 构建RAG证据字典 {equipment_name -> List[RAGEvidence]}
    # 需要从RagChunk查找对应的source和chunk_id
    rag_evidence_map: Dict[str, List[RAGEvidence]] = defaultdict(list)
    for extracted in extracted_equipment:
        # 根据source_chunk_id查找原始RagChunk（格式为"case_N"）
        try:
            case_idx = int(extracted.source_chunk_id.replace("case_", "")) - 1
            if 0 <= case_idx < len(rag_cases):
                rag_chunk = rag_cases[case_idx]
            else:
                logger.warning("source_chunk_id超出rag_cases范围: %s", extracted.source_chunk_id)
                rag_chunk = None
        except (ValueError, AttributeError):
            logger.warning("无效的source_chunk_id格式: %s", extracted.source_chunk_id)
            rag_chunk = None

        rag_ev = RAGEvidence(
            case_source=rag_chunk.source if rag_chunk else "unknown",
            equipment_name=extracted.name,
            quantity=extracted.quantity,
            context_snippet=extracted.context,
            confidence=extracted.confidence,
            qdrant_chunk_id=f"{rag_chunk.source}:{rag_chunk.loc}" if rag_chunk else extracted.source_chunk_id
        )
        rag_evidence_map[extracted.name].append(rag_ev)

    # 融合KG和RAG证据
    recommendations: List[EquipmentRecommendation] = []

    # 1. 处理KG中的装备
    for display_name, kg_ev in kg_evidence_map.items():
        # 查找RAG中相同装备（模糊匹配）
        matching_rag_evidence = _find_matching_rag_evidence(display_name, rag_evidence_map)

        if matching_rag_evidence:
            # KG+RAG都有：高置信度
            rag_quantities = [ev.quantity for ev in matching_rag_evidence if ev.quantity is not None]
            if rag_quantities:
                rag_avg = sum(rag_quantities) / len(rag_quantities)
                # 取max(KG标准, RAG平均值)，并加10%安全余量
                recommended_qty = int(max(kg_ev.standard_quantity, rag_avg) * 1.1)
                reasoning = f"KG标准要求{kg_ev.standard_quantity}件，历史案例平均使用{rag_avg:.1f}件，推荐{recommended_qty}件（含10%安全余量）"
                confidence = "高"
            else:
                # RAG中有装备但无数量
                recommended_qty = int(kg_ev.standard_quantity * 1.05)
                reasoning = f"KG标准要求{kg_ev.standard_quantity}件，历史案例确认使用但未提及数量，推荐{recommended_qty}件（含5%余量）"
                confidence = "中"
        else:
            # 仅KG有：中-高置信度
            recommended_qty = kg_ev.standard_quantity
            reasoning = f"基于KG标准配置{kg_ev.standard_quantity}件，暂无历史案例参考"
            confidence = "中" if kg_ev.urgency >= 7 else "中"

        recommendation = EquipmentRecommendation(
            equipment_name=kg_ev.equipment_name,
            display_name=kg_ev.display_name,
            recommended_quantity=recommended_qty,
            kg_evidence=kg_ev,
            rag_evidence=matching_rag_evidence,
            reasoning=reasoning,
            confidence_level=confidence
        )
        recommendations.append(recommendation)

    # 2. 处理仅在RAG中出现的装备（KG中未包含）
    rag_only_equipment = set(rag_evidence_map.keys()) - {kg_ev.display_name for kg_ev in kg_evidence_map.values()}
    for equipment_name in rag_only_equipment:
        rag_evs = rag_evidence_map[equipment_name]
        rag_quantities = [ev.quantity for ev in rag_evs if ev.quantity is not None]

        if rag_quantities:
            # 使用中位数+平均值的组合
            rag_median = sorted(rag_quantities)[len(rag_quantities) // 2]
            rag_avg = sum(rag_quantities) / len(rag_quantities)
            recommended_qty = int((rag_median + rag_avg) / 2)
            reasoning = f"历史案例平均{rag_avg:.1f}件，中位数{rag_median}件，推荐{recommended_qty}件（无KG标准）"
        else:
            # 无数量信息，给一个保守估计
            recommended_qty = 5
            reasoning = f"历史案例提及但未明确数量，给予保守估计{recommended_qty}件"

        # 计算置信水平：基于RAG证据的平均置信度
        avg_confidence = sum(ev.confidence for ev in rag_evs) / len(rag_evs)
        if avg_confidence >= 0.8:
            confidence = "中"
        elif avg_confidence >= 0.6:
            confidence = "低"
        else:
            confidence = "低"

        recommendation = EquipmentRecommendation(
            equipment_name=equipment_name,  # 使用RAG提取的名称
            display_name=equipment_name,
            recommended_quantity=recommended_qty,
            kg_evidence=None,
            rag_evidence=rag_evs,
            reasoning=reasoning,
            confidence_level=confidence
        )
        recommendations.append(recommendation)

    # 按紧急程度（KG）和置信度排序
    def sort_key(rec: EquipmentRecommendation) -> tuple:
        urgency = rec.kg_evidence.urgency if rec.kg_evidence else 0
        confidence_score = {"高": 3, "中": 2, "低": 1}[rec.confidence_level]
        return (-urgency, -confidence_score)

    recommendations.sort(key=sort_key)

    logger.info("生成装备推荐%d项（KG标准%d项，RAG提取%d项）",
                len(recommendations), len(kg_evidence_map), len(rag_evidence_map))

    return recommendations


def _find_matching_rag_evidence(
    equipment_name: str,
    rag_evidence_map: Dict[str, List[RAGEvidence]]
) -> List[RAGEvidence]:
    """查找匹配的RAG证据（支持模糊匹配）。

    Args:
        equipment_name: 装备名称（来自KG或RAG）。
        rag_evidence_map: RAG证据字典。

    Returns:
        匹配的RAG证据列表。
    """
    # 精确匹配
    if equipment_name in rag_evidence_map:
        return rag_evidence_map[equipment_name]

    # 模糊匹配：检查是否互为子串
    for rag_name, rag_evs in rag_evidence_map.items():
        if equipment_name in rag_name or rag_name in equipment_name:
            return rag_evs

    return []
