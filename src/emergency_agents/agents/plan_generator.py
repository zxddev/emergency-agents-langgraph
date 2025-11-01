# Copyright 2025 msq
from __future__ import annotations

import json
import uuid
import logging
import re
from typing import Dict, Any, List, Optional

from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.normalize import normalize_disaster_name
from emergency_agents.utils.merge import append_timeline
from emergency_agents.llm.client import LLMClientProtocol
from emergency_agents.graph.kg_service import KGService
from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.external.orchestrator_client import (
    OrchestratorClient,
    OrchestratorClientError,
    RescueScenarioLocation,
    RescueScenarioPayload,
)

logger = logging.getLogger(__name__)


def _strip_control_chars(text: str) -> str:
    return "".join(ch for ch in text if ch >= " " or ch in "\n\r\t")


def plan_generator_agent(
    state: Dict[str, Any],
    kg_service: KGService,
    llm_client: LLMClientProtocol,
    llm_model: str = "glm-4",
    orchestrator_client: Optional[OrchestratorClient] = None,
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
    casualties = situation.get("initial_casualties") or {}
    victims_estimate = casualties.get("estimated")
    
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
        
        llm_output = response.choices[0].message.content or ""
        clean_output = _strip_control_chars(llm_output)

        try:
            result = json.loads(clean_output)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', clean_output, re.DOTALL)
            if match:
                result = json.loads(_strip_control_chars(match.group(0)))
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

        updated_state = state | {
            "proposals": proposals,
            "plan": primary_plan,
            "alternative_plans": alternative_plans,
            "equipment_recommendations": equipment_reqs,
            "status": "awaiting_approval"
        }

        if orchestrator_client is not None:
            try:
                _push_to_orchestrator(
                    state=updated_state,
                    plan=primary_plan,
                    equipment_items=equipment_reqs,
                    victims_estimate=victims_estimate,
                    orchestrator=orchestrator_client,
                )
            except Exception as exc:
                logger.warning("orchestrator_push_exception %s", str(exc), exc_info=True)

        return updated_state
        
    except Exception as e:
        logger.error(f"方案生成失败: {e}", exc_info=True)
        return state | {
            "last_error": {"agent": "plan_generator", "error": str(e)}
        }


def _push_to_orchestrator(
    state: Dict[str, Any],
    plan: Dict[str, Any],
    equipment_items: List[Dict[str, Any]],
    victims_estimate: Any,
    orchestrator: OrchestratorClient,
) -> None:
    try:
        context = state.get("incident_context")
        if not isinstance(context, dict):
            context = {}
            state["incident_context"] = context

        incident_id = context.get("incident_id")
        if not incident_id:
            # 兼容旧流程：若外部未提前写入事件上下文，则退回到演示事件，确保流程不中断
            incident_id = str(state.get("incident_id") or RESCUE_DEMO_INCIDENT_ID)
            context["incident_id"] = incident_id
            context.setdefault("incident_title", plan.get("name") or "救援事件")
            logger.info(
                "plan_orchestrator_using_default_incident incident_id=%s plan_name=%s",
                incident_id,
                plan.get("name"),
            )

        scenario_payload = _build_rescue_scenario_payload(state, plan, equipment_items, incident_id, victims_estimate)
        if scenario_payload is None:
            logger.info("rescue_scenario_skipped_missing_payload incident_id=%s", incident_id)
            return

        logger.info(
            "rescue_scenario_publish_attempt incident_id=%s payload_keys=%s",
            incident_id,
            list(scenario_payload.to_dict().keys()),
        )
        orchestrator.publish_rescue_scenario(scenario_payload)
        logger.info("rescue_scenario_publish_success incident_id=%s", incident_id)
    except OrchestratorClientError as exc:
        logger.warning("orchestrator_push_failed error=%s", str(exc))


def _build_rescue_scenario_payload(
    state: Dict[str, Any],
    plan: Dict[str, Any],
    equipment_items: List[Dict[str, Any]],
    incident_id: str,
    victims_estimate: Any,
) -> Optional[RescueScenarioPayload]:
    situation = state.get("situation") or {}
    epicenter = situation.get("epicenter") or {}
    longitude = _safe_float(epicenter.get("lng") or epicenter.get("longitude"))
    latitude = _safe_float(epicenter.get("lat") or epicenter.get("latitude"))
    if longitude is None or latitude is None:
        return None

    location_name = situation.get("affected_area") or plan.get("name") or "救援现场"
    location = RescueScenarioLocation(longitude=longitude, latitude=latitude, name=location_name)

    phases = plan.get("phases") or []
    phase_lines = []
    for phase in phases:
        phase_name = phase.get("phase")
        tasks = phase.get("tasks") or []
        phase_lines.append(f"- {phase_name}：{','.join(tasks[:4])}" if phase_name else f"- {','.join(tasks[:4])}")
    objectives = plan.get("objectives") or []
    content_sections = [
        f"方案名称：{plan.get('name', '主救援方案')}",
        f"主要目标：{'、'.join(objectives[:3])}" if objectives else "主要目标：快速救援与安全评估",
        "阶段安排：",
        *(phase_lines if phase_lines else ["- 详情见任务面板"]),
    ]
    content = "\n".join(content_sections)

    hazards = []
    for risk in state.get("predicted_risks") or []:
        name = risk.get("display_name") or risk.get("type")
        if isinstance(name, str) and name:
            hazards.append(name)
    equipment_categories = {
        str(item.get("category"))
        for item in equipment_items
        if item.get("category")
    }

    return RescueScenarioPayload(
        event_id=incident_id,
        location=location,
        title=f"{location_name} 救援方案",
        content=content,
        origin="AI指挥助手",
        victims_estimate=int(victims_estimate) if isinstance(victims_estimate, (int, float)) else None,
        hazards=hazards or None,
        scope=["commander"],
        prompt_level=2,
        required_capabilities=sorted(equipment_categories) if equipment_categories else None,
    )

def _safe_float(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        return None
    return numeric
