# Copyright 2025 msq
from __future__ import annotations

import json
import logging
from typing import Dict, Any, List

from langgraph.func import task

from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.normalize import normalize_disaster_name
from emergency_agents.utils.merge import upsert_by_key, append_timeline
from emergency_agents.graph.kg_service import KGService
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.llm.client import LLMClientProtocol

logger = logging.getLogger(__name__)


@task
def _query_kg_secondary_disasters(kg_service: KGService, primary_disaster: str, magnitude: float) -> List[Dict[str, Any]]:
    """隔离KG查询副作用：预测次生灾害

    使用@task确保workflow恢复时不重复查询Neo4j。

    Args:
        kg_service: KG服务实例
        primary_disaster: 主灾害类型
        magnitude: 灾害强度

    Returns:
        次生灾害预测列表
    """
    return kg_service.predict_secondary_disasters(
        primary_disaster=primary_disaster,
        magnitude=magnitude
    )


@task
def _query_rag_cases(rag_pipeline: RagPipeline, question: str, domain: str, top_k: int) -> List:
    """隔离RAG检索副作用：查询历史案例

    使用@task确保workflow恢复时不重复查询Qdrant。

    Args:
        rag_pipeline: RAG管道实例
        question: 查询问题
        domain: 知识域
        top_k: 返回数量

    Returns:
        RAG检索结果列表
    """
    return rag_pipeline.query(
        question=question,
        domain=domain,
        top_k=top_k
    )


@task
def _call_llm_for_risk_prediction(
    prompt: str,
    llm_client: LLMClientProtocol,
    llm_model: str
) -> Dict[str, Any]:
    """隔离LLM调用副作用：综合分析风险

    使用@task确保workflow恢复时不重复调用LLM。

    Args:
        prompt: 完整的prompt字符串
        llm_client: LLM客户端
        llm_model: 模型名称

    Returns:
        结构化的风险预测结果
    """
    response = llm_client.chat.completions.create(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    llm_output = response.choices[0].message.content

    try:
        return json.loads(llm_output)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            return {"predicted_risks": [], "risk_level": 3, "timeline": []}


@task
def _query_kg_compound_risks(kg_service: KGService, disaster_ids: List[str]) -> List[Dict[str, Any]]:
    """隔离KG查询副作用：查询复合风险

    使用@task确保workflow恢复时不重复查询Neo4j。

    Args:
        kg_service: KG服务实例
        disaster_ids: 活跃灾害ID列表

    Returns:
        复合风险列表
    """
    return kg_service.get_compound_risks(disaster_ids=disaster_ids)


def risk_predictor_agent(
    state: Dict[str, Any],
    kg_service: KGService,
    rag_pipeline: RagPipeline,
    llm_client: LLMClientProtocol,
    llm_model: str = "glm-4"
) -> Dict[str, Any]:
    """风险预测智能体
    
    基于当前态势预测次生灾害和复合风险
    
    输入:
        state["situation"] - 态势信息（包含disaster_type, magnitude等）
    
    输出:
        state["predicted_risks"] - 预测的风险列表
        state["secondary_disasters"] - 次生灾害列表
        state["compound_risks"] - 复合风险列表
        state["timeline"] - 时间轴
    
    流程:
        1. 从KG查询TRIGGERS关系（主灾害→次生灾害）
        2. 从RAG检索相似历史案例
        3. 用LLM综合分析并生成风险评估
        4. 如果有多个灾害，查询COMPOUNDS关系
    
    Reference: 
        - docs/行动计划/ACTION-PLAN-DAY1.md (Day 3-5)
        - docs/分析报告 lines 838-873
    """
    if "predicted_risks" in state and state["predicted_risks"]:
        logger.info("风险预测结果已存在，跳过（幂等性）")
        return state
    
    situation = state.get("situation", {})
    if not situation or "disaster_type" in situation and situation.get("disaster_type") == "unknown":
        logger.warning("态势信息不完整，跳过风险预测")
        return state
    
    primary_type = normalize_disaster_name(situation.get("disaster_type", "earthquake"))
    magnitude = situation.get("magnitude", 0.0)
    affected_area = situation.get("affected_area", "")
    nearby_facilities = situation.get("nearby_facilities", [])
    
    try:
        # 使用@task包装的KG查询（支持Durable Execution）
        kg_task = _query_kg_secondary_disasters(kg_service, primary_type, magnitude)
        kg_predictions = kg_task.result()

        # 使用@task包装的RAG检索（支持Durable Execution）
        rag_task = _query_rag_cases(
            rag_pipeline,
            question=f"{primary_type} 次生灾害 {affected_area}",
            domain="案例",
            top_k=3
        )
        rag_cases = rag_task.result()
        
        case_context = "\n".join([f"- {c.text[:200]}" for c in rag_cases])
        
        kg_info = "\n".join([
            f"- {r['display_name']}: 概率{r['probability']}, {r['delay_hours']}小时后, 条件:{r['condition']}"
            for r in kg_predictions
        ])
        
        prompt = f"""基于以下信息预测次生灾害风险：

## 主灾害
类型: {primary_type}
强度: {magnitude}
地区: {affected_area}
附近设施: {', '.join(nearby_facilities)}

## 知识图谱预测
{kg_info if kg_info else "无匹配预测"}

## 历史案例
{case_context if case_context else "无相似案例"}

请以JSON格式返回风险预测：
{{
  "predicted_risks": [
    {{
      "type": "flood",
      "display_name": "洪水",
      "probability": 0.75,
      "severity": "high",
      "eta_hours": 2,
      "rationale": "震中附近有水库，地震可能导致大坝裂缝"
    }}
  ],
  "risk_level": 4,
  "timeline": [
    {{"time": "T+0h", "event": "地震发生"}},
    {{"time": "T+2h", "event": "预测洪水风险"}}
  ]
}}

只返回JSON，不要其他文字。"""

        # 使用@task包装的LLM调用（支持Durable Execution）
        llm_task = _call_llm_for_risk_prediction(prompt, llm_client, llm_model)
        result = llm_task.result()
        
        predicted_risks = result.get("predicted_risks", [])

        # 增量合并：同type的风险做upsert（更新概率/eta/severity），保留旧条目
        merged_risks = upsert_by_key(state.get("predicted_risks", []), predicted_risks, key="type")

        active_disasters = [primary_type] + [r["type"] for r in merged_risks]
        compound_risks = []
        if len(active_disasters) > 1:
            # 使用@task包装的KG查询（支持Durable Execution）
            compound_task = _query_kg_compound_risks(kg_service, active_disasters)
            compound_risks = compound_task.result()
        
        logger.info(f"风险预测完成: {len(predicted_risks)}个次生灾害, {len(compound_risks)}个复合风险")
        
        from emergency_agents.audit.logger import log_ai_decision
        log_ai_decision(
            rescue_id=state.get("rescue_id", "unknown"),
            user_id=state.get("user_id", "unknown"),
            agent_name="risk_predictor_agent",
            decision_type="risk_prediction",
            decision_data={
                "predicted_risks": predicted_risks,
                "risk_level": result.get("risk_level", 3),
                "compound_risks_count": len(compound_risks)
            }
        )
        
        # 时间轴记账
        state = append_timeline(state, "risk_predicted", {"count": len(predicted_risks)})

        # 两阶段提交：准备阶段
        content = json.dumps(
            {"kind": "risk_prediction", "predicted_risks": merged_risks, "risk_level": result.get("risk_level", 3)},
            ensure_ascii=False,
        )
        state = prepare_memory_node(
            state,
            content=content,
            metadata={"agent": "risk_predictor", "step": "001"},
        )

        return state | {
            "predicted_risks": merged_risks,
            "secondary_disasters": [{"type": r["type"], "probability": r.get("probability")} for r in merged_risks],
            "risk_level": result.get("risk_level", 3),
            "timeline": result.get("timeline", []),
            "compound_risks": compound_risks,
            "hazards": active_disasters
        }
        
    except Exception as e:
        logger.error(f"风险预测失败: {e}", exc_info=True)
        return state | {
            "last_error": {"agent": "risk_predictor", "error": str(e)}
        }
