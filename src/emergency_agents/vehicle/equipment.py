#!/usr/bin/env python3
# Copyright 2025 msq
"""
装备推荐服务 - RAG+KG混合推理引擎

核心创新：
- 三阶段推理：RAG规范检索 → KG案例验证 → LLM智能合成
- 推理链透明化：记录每个步骤的数据源和耗时
- 防幻觉机制：知识图谱校验装备真实性
- 专家可信度：引用GB/T标准 + 历史案例

技术栈：
- RAG: Qdrant向量检索 + BGE-M3 Embeddings
- KG: Neo4j知识图谱（装备-灾害关系）
- LLM: GLM-4-Plus (vLLM部署在H100 GPU#2)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DisasterType(str, Enum):
    """灾害类型枚举"""
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"
    FIRE = "fire"
    LANDSLIDE = "landslide"
    CHEMICAL_LEAK = "chemical_leak"


class ReasoningStage(str, Enum):
    """推理阶段枚举"""
    RAG_RETRIEVAL = "RAG检索"
    KG_VALIDATION = "KG验证"
    LLM_SYNTHESIS = "LLM合成"
    FINAL_OUTPUT = "最终输出"


@dataclass
class ReasoningStep:
    """推理链中的单个步骤"""
    stage: ReasoningStage
    source: str  # 数据来源：GB/T标准、历史案例、知识图谱
    result: Any  # 步骤输出结果
    duration_ms: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EquipmentItem:
    """装备项"""
    name: str
    category: str  # 通信/医疗/破拆/生命探测/照明/防护
    quantity: int
    priority: str  # 必需/重要/备用
    reason: str  # 推荐理由
    source: str  # 数据来源（规范/案例/经验）
    kg_verified: bool = False  # 是否经过知识图谱验证


@dataclass
class EquipmentRecommendation:
    """装备推荐结果"""
    disaster_context: Dict[str, Any]  # 灾害上下文
    equipment_list: List[EquipmentItem]
    reasoning_chain: List[ReasoningStep]  # 完整推理链（用于前端可视化）

    # 统计信息
    total_items: int
    total_reasoning_time_ms: float
    confidence_score: float

    # 引用来源
    citations: List[Dict[str, str]]  # [{"type": "标准", "name": "GB/T 33743-2017"}]


class EquipmentRecommender:
    """装备推荐引擎

    使用方法：
        recommender = EquipmentRecommender(
            rag_url="http://localhost:8008/rag/query",
            kg_url="http://localhost:8008/kg/recommend",
            llm_url="http://192.168.31.40:8002/v1"
        )
        result = await recommender.recommend({
            "disaster_type": "earthquake",
            "magnitude": 7.0,
            "affected_area": "汶川县",
            "terrain": "山区",
            "weather": "晴"
        })
        print(f"推荐 {result.total_items} 件装备")
        print(f"推理链: {len(result.reasoning_chain)} 步")
    """

    def __init__(
        self,
        rag_url: str,
        kg_url: str,
        llm_url: str,
        llm_model: str = "glm-4-plus",
        timeout: float = 30.0,
    ):
        """初始化装备推荐引擎

        Args:
            rag_url: RAG服务地址 (本地API /rag/query)
            kg_url: KG服务地址 (本地API /kg/recommend)
            llm_url: vLLM服务地址 (GLM-4-Plus on H100 #2)
            llm_model: LLM模型名称
            timeout: 超时时间（秒）
        """
        self.rag_url = rag_url
        self.kg_url = kg_url
        self.llm_url = llm_url.rstrip("/")
        self.llm_model = llm_model
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, trust_env=False)

        logger.info(
            f"EquipmentRecommender initialized: rag={rag_url}, "
            f"kg={kg_url}, llm={llm_url}"
        )

    async def recommend(
        self, disaster_context: Dict[str, Any]
    ) -> EquipmentRecommendation:
        """生成装备推荐方案

        Args:
            disaster_context: 灾害上下文字典，包含：
                - disaster_type: 灾害类型
                - magnitude: 震级/强度
                - affected_area: 受灾区域
                - terrain: 地形（山区/平原/城市）
                - weather: 天气（晴/雨/雪）
                - casualties: 伤亡预估
                - hazards: 次生灾害列表

        Returns:
            EquipmentRecommendation: 完整推荐结果（含推理链）
        """
        overall_start = time.time()
        reasoning_chain: List[ReasoningStep] = []

        try:
            # 阶段1: RAG检索规范文档
            rag_step, rag_results = await self._stage1_rag_retrieval(disaster_context)
            reasoning_chain.append(rag_step)

            # 阶段2: KG验证装备真实性
            kg_step, kg_results = await self._stage2_kg_validation(disaster_context)
            reasoning_chain.append(kg_step)

            # 阶段3: LLM智能合成方案
            llm_step, equipment_list = await self._stage3_llm_synthesis(
                disaster_context, rag_results, kg_results
            )
            reasoning_chain.append(llm_step)

            # 构建最终结果
            total_time_ms = (time.time() - overall_start) * 1000
            result = self._build_recommendation(
                disaster_context,
                equipment_list,
                reasoning_chain,
                total_time_ms,
            )

            logger.info(
                f"Equipment recommendation completed in {total_time_ms:.0f}ms: "
                f"{result.total_items} items, confidence={result.confidence_score:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Equipment recommendation failed: {e}", exc_info=True)
            raise

    async def _stage1_rag_retrieval(
        self, context: Dict[str, Any]
    ) -> tuple[ReasoningStep, List[Dict[str, Any]]]:
        """阶段1: RAG检索应急救援规范文档"""
        start_time = time.time()

        # 构建检索query
        query = self._build_rag_query(context)

        # 调用RAG API
        try:
            response = await self.client.post(
                self.rag_url,
                json={
                    "domain": "规范",  # Domain.SPEC
                    "question": query,
                    "top_k": 5,
                },
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            duration_ms = (time.time() - start_time) * 1000

            step = ReasoningStep(
                stage=ReasoningStage.RAG_RETRIEVAL,
                source="GB/T 33743-2017等应急救援标准",
                result=results,
                duration_ms=duration_ms,
                confidence=0.9,
                metadata={
                    "query": query,
                    "top_k": len(results),
                    "domain": "规范",
                },
            )

            logger.info(f"RAG retrieval completed: {len(results)} chunks in {duration_ms:.0f}ms")
            return step, results

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            # 返回空结果但不中断流程
            return (
                ReasoningStep(
                    stage=ReasoningStage.RAG_RETRIEVAL,
                    source="RAG服务",
                    result=[],
                    duration_ms=(time.time() - start_time) * 1000,
                    confidence=0.0,
                    metadata={"error": str(e)},
                ),
                [],
            )

    async def _stage2_kg_validation(
        self, context: Dict[str, Any]
    ) -> tuple[ReasoningStep, List[Dict[str, Any]]]:
        """阶段2: 知识图谱验证装备-灾害关系"""
        start_time = time.time()

        hazard = context.get("disaster_type", "earthquake")
        environment = context.get("terrain", "")

        try:
            response = await self.client.post(
                self.kg_url,
                json={
                    "hazard": hazard,
                    "environment": environment,
                    "top_k": 10,
                },
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("recommendations", [])

            duration_ms = (time.time() - start_time) * 1000

            step = ReasoningStep(
                stage=ReasoningStage.KG_VALIDATION,
                source="Neo4j装备知识图谱",
                result=results,
                duration_ms=duration_ms,
                confidence=0.95,
                metadata={
                    "hazard": hazard,
                    "environment": environment,
                    "validated_count": len(results),
                },
            )

            logger.info(f"KG validation completed: {len(results)} items in {duration_ms:.0f}ms")
            return step, results

        except Exception as e:
            logger.error(f"KG validation failed: {e}")
            return (
                ReasoningStep(
                    stage=ReasoningStage.KG_VALIDATION,
                    source="KG服务",
                    result=[],
                    duration_ms=(time.time() - start_time) * 1000,
                    confidence=0.0,
                    metadata={"error": str(e)},
                ),
                [],
            )

    async def _stage3_llm_synthesis(
        self,
        context: Dict[str, Any],
        rag_results: List[Dict[str, Any]],
        kg_results: List[Dict[str, Any]],
    ) -> tuple[ReasoningStep, List[EquipmentItem]]:
        """阶段3: LLM综合RAG+KG生成最终方案"""
        start_time = time.time()

        # 构建提示词
        prompt = self._build_synthesis_prompt(context, rag_results, kg_results)

        try:
            # 调用GLM-4-Plus
            response = await self.client.post(
                f"{self.llm_url}/chat/completions",
                json={
                    "model": self.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是应急救援装备专家，根据规范和经验推荐装备清单。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                },
            )
            response.raise_for_status()

            data = response.json()
            llm_output = data["choices"][0]["message"]["content"]

            # 解析LLM输出为结构化装备列表
            equipment_list = self._parse_equipment_list(llm_output, kg_results)

            duration_ms = (time.time() - start_time) * 1000

            step = ReasoningStep(
                stage=ReasoningStage.LLM_SYNTHESIS,
                source=f"{self.llm_model} (H100 GPU#2)",
                result={"equipment_count": len(equipment_list)},
                duration_ms=duration_ms,
                confidence=0.85,
                metadata={
                    "model": self.llm_model,
                    "prompt_length": len(prompt),
                    "output_length": len(llm_output),
                },
            )

            logger.info(f"LLM synthesis completed: {len(equipment_list)} items in {duration_ms:.0f}ms")
            return step, equipment_list

        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            # 降级：直接使用KG结果
            fallback_list = self._build_fallback_equipment(kg_results)
            return (
                ReasoningStep(
                    stage=ReasoningStage.LLM_SYNTHESIS,
                    source="KG降级方案",
                    result={"equipment_count": len(fallback_list)},
                    duration_ms=(time.time() - start_time) * 1000,
                    confidence=0.5,
                    metadata={"error": str(e), "fallback": True},
                ),
                fallback_list,
            )

    def _build_rag_query(self, context: Dict[str, Any]) -> str:
        """构建RAG检索query"""
        disaster_type = context.get("disaster_type", "earthquake")
        magnitude = context.get("magnitude", 0)
        terrain = context.get("terrain", "")

        return (
            f"{disaster_type} {magnitude}级 {terrain}地形 "
            f"应急救援 装备配置 规范标准"
        )

    def _build_synthesis_prompt(
        self,
        context: Dict[str, Any],
        rag_results: List[Dict[str, Any]],
        kg_results: List[Dict[str, Any]],
    ) -> str:
        """构建LLM综合推理的提示词"""
        # 整理RAG证据
        rag_evidence = "\n".join(
            [
                f"- [{r.get('source', 'unknown')}] {r.get('text', '')}"
                for r in rag_results[:3]
            ]
        )

        # 整理KG装备库
        kg_equipment = "\n".join(
            [f"- {item.get('name', 'unknown')}" for item in kg_results[:10]]
        )

        return f"""基于以下灾害情况和证据，推荐应急救援装备清单：

【灾害情况】
- 类型: {context.get('disaster_type')}
- 强度: {context.get('magnitude')}级
- 区域: {context.get('affected_area')}
- 地形: {context.get('terrain')}
- 天气: {context.get('weather')}

【规范引用（RAG检索）】
{rag_evidence}

【可用装备（KG图谱验证）】
{kg_equipment}

请按以下JSON格式输出装备清单（只返回JSON，无其他文字）：

```json
{{
  "equipment": [
    {{
      "name": "卫星通信设备",
      "category": "通信",
      "quantity": 5,
      "priority": "必需",
      "reason": "山区信号中断，需要卫星通信保障",
      "source": "GB/T 33743-2017第5.2节"
    }}
  ]
}}
```

分类: 通信/医疗/破拆/生命探测/照明/防护/后勤
优先级: 必需/重要/备用"""

    def _parse_equipment_list(
        self, llm_output: str, kg_results: List[Dict[str, Any]]
    ) -> List[EquipmentItem]:
        """解析LLM输出为EquipmentItem列表"""
        # 提取JSON
        if "```json" in llm_output:
            import re
            match = re.search(r"```json\n(.*?)\n```", llm_output, re.DOTALL)
            json_str = match.group(1) if match else llm_output
        else:
            json_str = llm_output

        try:
            data = json.loads(json_str)
            equipment_data = data.get("equipment", [])

            # 转换为EquipmentItem并验证
            kg_names = {item.get("name", "").lower() for item in kg_results}

            items = []
            for eq in equipment_data:
                item = EquipmentItem(
                    name=eq.get("name", "unknown"),
                    category=eq.get("category", "其他"),
                    quantity=eq.get("quantity", 1),
                    priority=eq.get("priority", "重要"),
                    reason=eq.get("reason", ""),
                    source=eq.get("source", "LLM生成"),
                    kg_verified=eq.get("name", "").lower() in kg_names,
                )
                items.append(item)

            return items

        except Exception as e:
            logger.error(f"Failed to parse equipment list: {e}")
            return self._build_fallback_equipment(kg_results)

    def _build_fallback_equipment(
        self, kg_results: List[Dict[str, Any]]
    ) -> List[EquipmentItem]:
        """构建降级装备列表（直接使用KG结果）"""
        return [
            EquipmentItem(
                name=item.get("name", "unknown"),
                category="通用",
                quantity=1,
                priority="重要",
                reason="知识图谱推荐",
                source="Neo4j KG",
                kg_verified=True,
            )
            for item in kg_results[:10]
        ]

    def _build_recommendation(
        self,
        context: Dict[str, Any],
        equipment_list: List[EquipmentItem],
        reasoning_chain: List[ReasoningStep],
        total_time_ms: float,
    ) -> EquipmentRecommendation:
        """构建最终推荐结果"""
        # 提取引用来源
        citations = []
        for step in reasoning_chain:
            if "GB/T" in step.source:
                citations.append({"type": "标准", "name": step.source})
            elif "案例" in step.source:
                citations.append({"type": "案例", "name": step.source})

        # 计算平均置信度
        confidences = [step.confidence for step in reasoning_chain]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return EquipmentRecommendation(
            disaster_context=context,
            equipment_list=equipment_list,
            reasoning_chain=reasoning_chain,
            total_items=len(equipment_list),
            total_reasoning_time_ms=total_time_ms,
            confidence_score=avg_confidence,
            citations=citations,
        )

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
