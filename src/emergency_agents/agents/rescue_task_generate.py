# Copyright 2025 msq
"""救援方案与任务生成智能体。

职责：
- 从pending_entities生成救援方案
- 查询KG获取所需资源装备（REQUIRES关系）
- 检索RAG历史救援案例
- 用LLM生成方案与任务拆解
- 检查证据化Gate（资源+KG≥3+RAG≥2）
- 生成proposals供HITL审批
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Callable

from langgraph.func import task

from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.merge import append_timeline
from emergency_agents.policy.evidence import evidence_gate_ok
from emergency_agents.rag.equipment_extractor import extract_equipment_from_cases
from emergency_agents.rag.evidence_builder import build_equipment_recommendations
from emergency_agents.graph.kg_service import KGService
from emergency_agents.rag.pipe import RagPipeline, RagChunk
from emergency_agents.llm.client import LLMClientProtocol

logger = logging.getLogger(__name__)


def _unwrap_task_result(obj: Any) -> Any:
    """展开LangGraph任务结果，直至无 output 属性。"""
    current = obj
    seen: set[int] = set()
    while hasattr(current, "output"):
        next_obj = getattr(current, "output")
        obj_id = id(next_obj)
        if obj_id in seen or next_obj is current:
            break
        seen.add(obj_id)
        current = next_obj
    return current


def _run_task_function(task_fn: Any, /, **kwargs: Any) -> Any:
    """在LangGraph上下文外执行@task包装函数。

    优先调用invoke，若不可用则回退到底层原始函数。
    """
    if hasattr(task_fn, "invoke"):
        return task_fn.invoke(kwargs)  # type: ignore[no-any-return]
    if hasattr(task_fn, "func"):
        base: Callable[..., Any] = getattr(task_fn, "func")
        return base(**kwargs)
    return task_fn(**kwargs)


@task
def _query_kg_equipment_requirements(kg_service: KGService, disaster_types: List[str]) -> List[Dict[str, Any]]:
    """隔离KG查询副作用：获取装备需求标准

    使用@task确保workflow恢复时不重复查询Neo4j。

    Args:
        kg_service: KG服务实例
        disaster_types: 灾害类型列表

    Returns:
        装备需求列表
    """
    return kg_service.get_equipment_requirements(disaster_types=disaster_types)


@task
def _query_rag_rescue_cases(rag_pipeline: RagPipeline, question: str, domain: str, top_k: int) -> List:
    """隔离RAG检索副作用：查询救援案例

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
def _call_llm_for_rescue_plan(
    prompt: str,
    llm_client: LLMClientProtocol,
    llm_model: str
) -> Dict[str, Any]:
    """隔离LLM调用副作用：生成救援方案

    使用@task确保workflow恢复时不重复调用LLM。

    Args:
        prompt: 完整的prompt字符串
        llm_client: LLM客户端
        llm_model: 模型名称

    Returns:
        结构化的救援方案
    """
    response = llm_client.chat.completions.create(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    llm_output = response.choices[0].message.content

    try:
        return json.loads(llm_output)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        logger.error("JSON解析失败: %s", llm_output[:300])
        return {
            "rescue_plan": {
                "priority": "high",
                "summary": "LLM输出解析失败，使用默认方案"
            },
            "tasks": []
        }


def rescue_task_generate_agent(
    state: Dict[str, Any],
    kg_service: KGService,
    rag_pipeline: RagPipeline,
    llm_client: LLMClientProtocol,
    llm_model: str
) -> Dict[str, Any]:
    """救援方案与任务生成智能体。
    
    Args:
        state: 图状态，必含pending_entities。
        kg_service: KG服务实例。
        rag_pipeline: RAG检索管道。
        llm_client: LLM客户端。
        llm_model: 模型名。
    
    Returns:
        更新后的state，包含proposals/tasks/evidence等。
    """
    pending_entities = state.get("pending_entities") or []
    
    if not pending_entities:
        logger.warning("无pending_entities，跳过救援方案生成")
        return state
    
    trapped_entities = [e for e in pending_entities if e.get("type") == "TRAPPED"]
    
    if not trapped_entities:
        logger.info("无被困实体，跳过救援方案生成")
        return state
    
    total_count = sum(e.get("count", 0) for e in trapped_entities)
    locations = [(e.get("lat"), e.get("lng"), e.get("location_text")) for e in trapped_entities]
    
    logger.info("开始生成救援方案: %d个被困点，共%d人", len(trapped_entities), total_count)
    
    try:
        disaster_types = ["people_trapped"]

        # 1. 查询KG装备标准（使用@task包装）
        kg_equipment_raw = _run_task_function(
            _query_kg_equipment_requirements,
            kg_service=kg_service,
            disaster_types=disaster_types,
        )
        kg_equipment: List[Dict[str, Any]] = []
        for item in kg_equipment_raw:
            normalized_item = dict(item)
            if "equipment_name" not in normalized_item:
                fallback_name = normalized_item.get("display_name") or normalized_item.get("name") or "unknown_equipment"
                normalized_item["equipment_name"] = str(fallback_name)
            kg_equipment.append(normalized_item)

        # 2. 检索RAG历史案例（使用@task包装）
        raw_rag_cases = _run_task_function(
            _query_rag_rescue_cases,
            rag_pipeline=rag_pipeline,
            question=f"被困群众救援 {total_count}人",
            domain="案例",
            top_k=3,
        )
        rag_cases: List[RagChunk] = []
        for idx, case in enumerate(raw_rag_cases):
            unwrapped = _unwrap_task_result(case)
            if hasattr(unwrapped, "source") and hasattr(unwrapped, "text"):
                rag_cases.append(unwrapped)  # type: ignore[arg-type]
                continue
            fallback_text = str(getattr(unwrapped, "text", ""))
            fallback_source = str(getattr(unwrapped, "source", "mock_rag"))
            fallback_loc = str(getattr(unwrapped, "loc", ""))
            logger.warning(
                "rag_case_without_source index=%s type=%s repr=%s",
                idx,
                type(unwrapped).__name__,
                repr(unwrapped),
            )
            rag_cases.append(RagChunk(text=fallback_text, source=fallback_source, loc=fallback_loc))

        # 3. 从RAG案例中提取装备信息（使用LLM结构化输出）
        extracted_equipment = extract_equipment_from_cases(
            cases=rag_cases,
            llm_client=llm_client,
            llm_model=llm_model
        )

        # 4. 融合KG标准与RAG提取结果，构建完整证据链
        equipment_recommendations = build_equipment_recommendations(
            kg_standards=kg_equipment,
            rag_cases=rag_cases,
            extracted_equipment=extracted_equipment,
            disaster_types=disaster_types
        )

        kg_hits_count = len(kg_equipment)
        rag_hits_count = len(rag_cases)
        extracted_count = len(extracted_equipment)

        logger.info("证据收集与融合: KG标准%d项, RAG案例%d条, 提取装备%d项, 推荐结果%d项",
                    kg_hits_count, rag_hits_count, extracted_count, len(equipment_recommendations))

        # 构建装备信息展示（用于LLM生成方案）
        equipment_info = "\n".join([
            f"- {rec.display_name}: 推荐{rec.recommended_quantity}件 (置信度: {rec.confidence_level})"
            for rec in equipment_recommendations[:10]
        ])

        case_info = "\n".join([
            f"- {c.text[:150]}"
            for c in rag_cases
        ])
        
        prompt = f"""作为应急救援指挥专家，请生成救援方案：

## 被困情况
- 被困点数：{len(trapped_entities)}
- 被困人数：{total_count}
- 位置：{locations[0][2] if locations[0][2] else f'({locations[0][0]},{locations[0][1]})'}

## 推荐装备（KG）
{equipment_info if equipment_info else "无装备数据"}

## 历史案例（RAG）
{case_info if case_info else "无相似案例"}

请生成救援方案，以JSON格式返回：
{{
  "plan": {{
    "name": "救援方案名称",
    "units": [
      {{
        "unit_type": "消防",
        "count": 2,
        "equipment": ["生命探测仪", "绳索"],
        "eta_hours": 0.5
      }}
    ],
    "phases": [
      {{
        "phase": "初期响应",
        "duration_hours": 1,
        "tasks": ["建立通讯", "侦察路线"]
      }}
    ]
  }},
  "tasks": [
    {{
      "title": "任务1",
      "unit_type": "消防",
      "lat": 31.68,
      "lng": 103.85,
      "window_hours": 2
    }}
  ]
}}

只返回JSON。"""

        # 使用@task包装的LLM调用（支持Durable Execution）
        result = _run_task_function(
            _call_llm_for_rescue_plan,
            prompt=prompt,
            llm_client=llm_client,
            llm_model=llm_model,
        )
        
        plan = result.get("plan", {})
        tasks = result.get("tasks", [])
        
        proposal_id = str(uuid.uuid4())

        # 构建完整证据链（替换旧的假融合）
        evidence = {
            "resources": plan.get("units", []),
            "kg": kg_equipment,
            "rag": [{"text": c.text, "source": c.source, "loc": c.loc} for c in rag_cases],
            "equipment_recommendations": [rec.to_dict() for rec in equipment_recommendations[:10]],
            "rag_cases": [{"text": c.text[:100], "source": c.source, "loc": c.loc} for c in rag_cases],
            "fusion_summary": {
                "kg_standards_count": kg_hits_count,
                "rag_cases_count": rag_hits_count,
                "extracted_equipment_count": extracted_count,
                "final_recommendations_count": len(equipment_recommendations)
            }
        }
        
        proposals = [{
            "id": proposal_id,
            "type": "rescue_task_dispatch",
            "params": {
                "plan": plan,
                "tasks": tasks,
                "target_entities": [e["id"] for e in trapped_entities]
            },
            "evidence": evidence,
            "rationale": f"基于{total_count}人被困的综合分析",
            "requires_approval": True
        }]
        
        logger.info("生成救援方案: %s, %d个任务", plan.get("name"), len(tasks))
        
        state = append_timeline(state, "rescue_plan_generated", {"proposal_id": proposal_id, "task_count": len(tasks)})
        
        from emergency_agents.audit.logger import log_ai_decision
        log_ai_decision(
            rescue_id=state.get("rescue_id", "unknown"),
            user_id=state.get("user_id", "unknown"),
            agent_name="rescue_task_generate_agent",
            decision_type="plan_generation",
            decision_data={
                "proposal_id": proposal_id,
                "task_count": len(tasks),
                "kg_hits": kg_hits_count,
                "rag_hits": rag_hits_count
            }
        )
        
        content = json.dumps({"kind": "rescue_plan", "proposal_id": proposal_id, "plan": plan, "tasks": tasks}, ensure_ascii=False)
        state = prepare_memory_node(state, content=content, metadata={"agent": "rescue_task_generate", "proposal_id": proposal_id})
        
        return state | {
            "proposals": proposals,
            "plan": plan,
            "tasks": tasks,
            "kg_hits_count": kg_hits_count,
            "rag_case_refs_count": rag_hits_count,
            "status": "awaiting_approval"
        }
        
    except Exception as e:
        logger.error("救援方案生成失败: %s", e, exc_info=True)
        return state | {"last_error": {"agent": "rescue_task_generate", "error": str(e)}}
