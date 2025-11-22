# Copyright 2025 msq
from __future__ import annotations

import json
import logging
from typing import Dict, Any, List

from emergency_agents.agents.base import LLMAgentNode
from emergency_agents.agents.schemas_risk import RiskPrediction
from emergency_agents.container import container
from emergency_agents.utils.normalize import normalize_disaster_name
from emergency_agents.utils.merge import upsert_by_key
from emergency_agents.agents.memory_commit import prepare_memory_node

logger = logging.getLogger(__name__)

RISK_PREDICTION_PROMPT = """基于以下信息预测次生灾害风险：

## 主灾害
类型: {disaster_type}
强度: {magnitude}
地区: {affected_area}
附近设施: {nearby_facilities}

## 知识图谱预测
{kg_info}

## 历史案例
{case_context}

请生成风险预测报告。
"""

class RiskPredictorAgentNode(LLMAgentNode[RiskPrediction]):
    """风险预测智能体 (Refactored)"""

    def __init__(self):
        super().__init__(
            name="risk_predictor",
            output_schema=RiskPrediction,
            prompt_template=RISK_PREDICTION_PROMPT,
            state_key="risk_prediction_result" # 临时 key，需要拆解合并
        )

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if "predicted_risks" in state and state["predicted_risks"]:
            logger.info("风险预测结果已存在，跳过（幂等性）")
            return state

        situation = state.get("situation", {})
        if not situation or situation.get("disaster_type", "unknown") == "unknown":
            logger.warning("态势信息不完整，跳过风险预测")
            return state

        # 准备上下文
        primary_type = normalize_disaster_name(situation.get("disaster_type", "earthquake"))
        magnitude = situation.get("magnitude", 0.0)
        affected_area = situation.get("affected_area", "")
        nearby_facilities = situation.get("nearby_facilities", [])

        # KG 和 RAG 查询 (继续使用原生逻辑或封装到 container)
        # 这里直接调用 container 中的服务
        kg_service = container.kg_service
        rag_pipeline = container.rag_pipeline

        kg_predictions = kg_service.predict_secondary_disasters(primary_type, magnitude)
        rag_cases = rag_pipeline.query(
            question=f"{primary_type} 次生灾害 {affected_area}",
            domain="案例",
            top_k=3
        )

        # 构建上下文变量
        case_context = "\n".join([f"- {c.text[:200]}" for c in rag_cases])
        kg_info = "\n".join([
            f"- {r['display_name']}: 概率{r['probability']}, {r['delay_hours']}小时后, 条件:{r['condition']}"
            for r in kg_predictions
        ])

        # 注入到 state 供 LLM 使用 (临时)
        context_state = state | {
            "disaster_type": primary_type,
            "magnitude": magnitude,
            "affected_area": affected_area,
            "nearby_facilities": ", ".join(nearby_facilities),
            "kg_info": kg_info or "无匹配预测",
            "case_context": case_context or "无相似案例"
        }

        # 执行 LLM
        new_state = await super().run(context_state)
        
        # 处理结果
        result_raw = new_state.get(self.state_key) # 这是 model_dump 后的 dict
        if not result_raw:
             return new_state

        # 恢复原始 state 的干净状态 (去掉临时 prompt 变量)，并合并业务逻辑
        predicted_risks = result_raw.get("predicted_risks", [])
        
        # Upsert logic
        merged_risks = upsert_by_key(state.get("predicted_risks", []), predicted_risks, key="type")

        # Compound risks logic
        active_disasters = [primary_type] + [r["type"] for r in merged_risks]
        compound_risks = []
        if len(active_disasters) > 1:
            compound_risks = kg_service.get_compound_risks(disaster_ids=active_disasters)

        # 审计日志
        from emergency_agents.audit.logger import log_ai_decision
        log_ai_decision(
            rescue_id=state.get("rescue_id", "unknown"),
            user_id=state.get("user_id", "unknown"),
            agent_name="risk_predictor_agent",
            decision_type="risk_prediction",
            decision_data={
                "predicted_risks": predicted_risks,
                "risk_level": result_raw.get("risk_level", 3),
                "compound_risks_count": len(compound_risks)
            }
        )

        # Memory 两阶段提交
        content = json.dumps(
            {"kind": "risk_prediction", "predicted_risks": merged_risks, "risk_level": result_raw.get("risk_level", 3)},
            ensure_ascii=False,
        )
        final_state = prepare_memory_node(
            new_state,
            content=content,
            metadata={"agent": "risk_predictor", "step": "001"},
        )

        # 清理临时 key 并设置正式 key
        final_state.pop(self.state_key, None)
        
        return final_state | {
            "predicted_risks": merged_risks,
            "secondary_disasters": [{"type": r["type"], "probability": r.get("probability")} for r in merged_risks],
            "risk_level": result_raw.get("risk_level", 3),
            "timeline": result_raw.get("timeline", []),
            "compound_risks": compound_risks,
            "hazards": active_disasters
        }

_risk_agent_instance = RiskPredictorAgentNode()

async def risk_predictor_agent(state: Dict[str, Any], kg_service: Any = None, rag_pipeline: Any = None, llm_client: Any = None, llm_model: str = None) -> Dict[str, Any]:
    """
    兼容旧签名的适配器函数。
    依赖项从 Container 获取，忽略传入参数。
    """
    return await _risk_agent_instance.run(state)
