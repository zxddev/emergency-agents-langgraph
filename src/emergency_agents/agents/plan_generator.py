# Copyright 2025 msq
from __future__ import annotations

import json
import uuid
import logging
from typing import Dict, Any, List
from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.normalize import normalize_disaster_name
from emergency_agents.utils.merge import append_timeline

logger = logging.getLogger(__name__)


def plan_generator_agent(
    state: Dict[str, Any],
    kg_service,
    llm_client,
    llm_model: str = "glm-4"
) -> Dict[str, Any]:
    """方案生成智能体
    
    基于态势和风险预测生成救援方案
    
    输入:
        state["situation"] - 态势信息
        state["predicted_risks"] - 预测风险
        state["secondary_disasters"] - 次生灾害
    
    输出:
        state["proposals"] - AI生成的待审批方案列表
        state["plan"] - 推荐方案
        state["alternative_plans"] - 备选方案
        state["equipment_recommendations"] - 装备推荐
    
    流程:
        1. 从KG查询所需装备
        2. 用LLM生成救援方案
        3. 生成proposals供人工审批
    
    Reference: 
        - docs/行动计划/ACTION-PLAN-DAY1.md (Day 6-8)
        - docs/分析报告 lines 875-915
    """
    if "proposals" in state and state["proposals"]:
        logger.info("方案已存在，跳过（幂等性）")
        return state
    
    situation = state.get("situation", {})
    predicted_risks = state.get("predicted_risks", [])
    
    if not situation:
        logger.warning("无态势信息，无法生成方案")
        return state
    
    primary_type = normalize_disaster_name(situation.get("disaster_type", "earthquake"))
    magnitude = situation.get("magnitude", 0.0)
    affected_area = situation.get("affected_area", "")
    
    try:
        disaster_types = [primary_type] + [r["type"] for r in predicted_risks]
        equipment_reqs = kg_service.get_equipment_requirements(disaster_types=disaster_types)
        
        equipment_info = "\n".join([
            f"- {eq['display_name']}: {eq['total_quantity']}件, 紧急度:{eq['max_urgency']}, 用于:{','.join(eq['for_disasters'])}"
            for eq in equipment_reqs[:10]
        ])
        
        risks_info = "\n".join([
            f"- {r.get('display_name', r['type'])}: 概率{r['probability']}, {r['eta_hours']}小时后, {r['severity']}"
            for r in predicted_risks
        ])
        
        prompt = f"""作为应急救援指挥专家，请基于以下信息生成救援方案：

## 主灾害
类型: {primary_type}
强度: {magnitude}
地区: {affected_area}

## 预测风险
{risks_info if risks_info else "无预测风险"}

## 推荐装备
{equipment_info if equipment_info else "无装备数据"}

请生成救援方案，以JSON格式返回：
{{
  "primary_plan": {{
    "name": "主救援方案",
    "priority": "P0",
    "objectives": ["目标1", "目标2"],
    "phases": [
      {{
        "phase": "初期响应",
        "duration_hours": 2,
        "tasks": ["任务1", "任务2"],
        "required_equipment": ["生命探测仪", "救援艇"],
        "personnel": 50
      }}
    ],
    "estimated_duration_hours": 48,
    "estimated_cost": 5000000
  }},
  "alternative_plans": [
    {{
      "name": "备选方案1",
      "priority": "P1",
      "difference": "不同之处说明"
    }}
  ],
  "critical_warnings": ["警告1", "警告2"]
}}

只返回JSON。"""
        
        response = llm_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "你是专业的应急救援指挥专家，精通灾害应对和资源调度。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        llm_output = response.choices[0].message.content
        
        try:
            result = json.loads(llm_output)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', llm_output, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
            else:
                result = {
                    "primary_plan": {"name": "应急方案", "phases": []},
                    "alternative_plans": []
                }
        
        primary_plan = result.get("primary_plan", {})
        alternative_plans = result.get("alternative_plans", [])
        
        proposal_id = str(uuid.uuid4())
        proposals = [{
            "id": proposal_id,
            "type": "execute_rescue_plan",
            "params": {
                "plan": primary_plan,
                "disaster_type": primary_type,
                "magnitude": magnitude
            },
            "rationale": f"基于{primary_type}(强度{magnitude})及{len(predicted_risks)}个预测风险的综合分析",
            "risk_level": state.get("risk_level", 3),
            "requires_approval": True
        }]
        
        logger.info(f"方案生成成功: {primary_plan.get('name')}, {len(alternative_plans)}个备选方案")
        # 时间轴记账
        state = append_timeline(state, "plan_generated", {"proposal_id": proposal_id})
        
        from emergency_agents.audit.logger import log_ai_decision
        log_ai_decision(
            rescue_id=state.get("rescue_id", "unknown"),
            user_id=state.get("user_id", "unknown"),
            agent_name="plan_generator_agent",
            decision_type="plan_generation",
            decision_data={
                "plan_name": primary_plan.get("name"),
                "proposal_id": proposal_id,
                "alternative_count": len(alternative_plans),
                "equipment_count": len(equipment_reqs)
            }
        )
        
        # 两阶段提交：准备阶段
        content = json.dumps(
            {"kind": "plan", "proposal_id": proposal_id, "plan": primary_plan, "alternatives": alternative_plans},
            ensure_ascii=False,
        )
        state = prepare_memory_node(
            state,
            content=content,
            metadata={"agent": "plan_generator", "step": "001", "proposal_id": proposal_id},
        )

        return state | {
            "proposals": proposals,
            "plan": primary_plan,
            "alternative_plans": alternative_plans,
            "equipment_recommendations": equipment_reqs,
            "status": "awaiting_approval"
        }
        
    except Exception as e:
        logger.error(f"方案生成失败: {e}", exc_info=True)
        return state | {
            "last_error": {"agent": "plan_generator", "error": str(e)}
        }

