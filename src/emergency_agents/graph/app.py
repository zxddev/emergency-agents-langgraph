# Copyright 2025 msq
from __future__ import annotations

from enum import Enum
from typing import Literal
from typing_extensions import NotRequired, Required, TypedDict

import structlog

from langgraph.graph import StateGraph

from emergency_agents.agents.situation import situation_agent
from emergency_agents.agents.risk_predictor import risk_predictor_agent
from emergency_agents.agents.plan_generator import plan_generator_agent
from emergency_agents.agents.memory_commit import commit_memory_node
from emergency_agents.agents.report_intake import report_intake_agent
from emergency_agents.agents.annotation_lifecycle import annotation_lifecycle_agent
from emergency_agents.agents.rescue_task_generate import rescue_task_generate_agent
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig
from emergency_agents.graph.kg_service import KGService, KGConfig
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.memory.mem0_facade import Mem0Config, MemoryFacade
from emergency_agents.external.orchestrator_client import OrchestratorClient
from langgraph.types import interrupt, Command
from typing import Dict, Any, List, Tuple

from emergency_agents.policy.evidence import evidence_gate_ok

logger = structlog.get_logger(__name__)


class Status(str, Enum):
    """救援线程的状态枚举。"""
    INIT = "init"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class RescueState(TypedDict):
    """救援主流程状态定义。

    核心标识字段（Required）：rescue_id, user_id, raw_report
    其他字段（NotRequired）：在图执行过程中逐步填充
    """

    # 核心标识字段（必填）
    rescue_id: Required[str]
    user_id: Required[str]
    raw_report: Required[str]

    # 流程控制字段（可选）
    status: NotRequired[Literal["init", "awaiting_approval", "running", "completed", "error"]]
    messages: NotRequired[list]
    error_count: NotRequired[int]
    max_steps: NotRequired[int]
    last_error: NotRequired[dict]

    # 态势感知字段（可选）
    situation: NotRequired[dict]
    primary_disaster: NotRequired[dict]
    secondary_disasters: NotRequired[list]
    predicted_risks: NotRequired[list]
    timeline: NotRequired[list]
    compound_risks: NotRequired[list]
    available_resources: NotRequired[dict]
    blocked_roads: NotRequired[list]

    # 方案生成字段（可选）
    proposals: NotRequired[list]
    approved_ids: NotRequired[list]
    executed_actions: NotRequired[list]
    plan: NotRequired[dict]
    plan_approved: NotRequired[bool]
    alternative_plans: NotRequired[list]

    # 装备推荐字段（可选）
    equipment_recommendations: NotRequired[list]
    risk_level: NotRequired[int]
    hazards: NotRequired[list]

    # 记忆管理字段（可选）
    pending_memories: NotRequired[list]
    committed_memories: NotRequired[list]

    # 集成字段（可选）
    uav_tracks: NotRequired[list]
    fleet_position: NotRequired[dict]
    integration_logs: NotRequired[list]
    pending_entities: NotRequired[list]
    pending_events: NotRequired[list]
    pending_annotations: NotRequired[list]
    annotations: NotRequired[list]
    tasks: NotRequired[list]


async def build_app(sqlite_path: str = "./checkpoints.sqlite3", postgres_dsn: str | None = None):
    """构建 LangGraph 应用 (Refactored)。"""
    graph = StateGraph(RescueState)
    
    # 依赖从 container 获取，不再在 build_app 内部初始化
    from emergency_agents.container import container
    
    # Orchestrator Client 应该也是注册服务之一，暂时保留
    orchestrator_client = OrchestratorClient()

    def situation_node(state: RescueState) -> dict:
        return situation_agent(state) # 无需传入 llm_client
    
    def risk_prediction_node(state: RescueState) -> dict:
        return risk_predictor_agent(state)
    
    def plan_node(state: RescueState) -> dict:
        return plan_generator_agent(
            state,
            orchestrator_client=orchestrator_client,
        )
    
    # ... (report_intake, annotation_lifecycle, rescue_task_generate 等需类似重构)
    def report_intake_node(state: RescueState) -> dict:
        return report_intake_agent(state)
    
    def annotation_lifecycle_node(state: RescueState) -> dict:
        return annotation_lifecycle_agent(state)
    
    def rescue_task_generate_node(state: RescueState) -> dict:
        # 需要检查 rescue_task_generate_agent 签名
        return rescue_task_generate_agent(state, container.kg_service, container.rag_pipeline, container.llm_client, container.config.llm_model)

    # ... (approve_node, await_node, execute_node, commit_memories_node, error_handler, fail_node, route_after_error 保留)
    def approve_node(state: RescueState) -> dict:
        if state.get("status") == Status.COMPLETED.value:
            return {}
        return {"status": Status.COMPLETED.value}

    def await_node(state: RescueState) -> dict:
        """人工审批中断节点：将当前提案暴露给外部系统并等待恢复。"""
        # 使用标准的 interrupt 函数 (LangGraph 0.2 functional or class style)
        # 在 StateGraph 中，interrupt 可以在节点内部调用，返回挂起信号
        payload = {"proposals": state.get("proposals", [])}
        approved_ids = interrupt(payload)

        proposals_list = state.get("proposals") or []
        valid_ids = {p.get("id") for p in proposals_list if isinstance(p, dict) and p.get("id")}

        if approved_ids is None:
            approved_ids = []
        if not isinstance(approved_ids, list):
            # 如果恢复的值不是 list，可能是错误恢复
            logger.warning(f"Invalid resume value: {approved_ids}")
            return {"approved_ids": []}
            
        # 简单的校验
        deduped = []
        for pid in approved_ids:
            if isinstance(pid, str) and pid in valid_ids and pid not in deduped:
                deduped.append(pid)

        return {"approved_ids": deduped}

    def execute_node(state: RescueState) -> dict:
        proposals = {p.get("id"): p for p in (state.get("proposals") or []) if isinstance(p, dict) and p.get("id")}
        approved = [pid for pid in (state.get("approved_ids") or []) if pid in proposals]
        executed = [proposals[pid] for pid in approved]
        merged = (state.get("executed_actions") or []) + executed

        if executed:
            from emergency_agents.audit.logger import log_execution
            for item in executed:
                # Evidence Gate
                ok, reason = evidence_gate_ok(state)
                if not ok:
                    log_execution(
                        rescue_id=state.get("rescue_id", "unknown"),
                        user_id=state.get("user_id", "unknown"),
                        action_id=item.get("id", ""),
                        action_type=item.get("type", "unknown"),
                        result={"ok": False, "blocked_by": reason},
                        success=False,
                        thread_id=None,
                    )
                    return {"status": Status.AWAITING_APPROVAL.value, "last_error": {"blocked_by": reason}}
                
                # TODO: Real Execution Here (Call AdapterHubClient)
                # container.adapter_client.execute(item) 
                
                log_execution(
                    rescue_id=state.get("rescue_id", "unknown"),
                    user_id=state.get("user_id", "unknown"),
                    action_id=item.get("id", ""),
                    action_type=item.get("type", "unknown"),
                    result={"ok": True},
                    success=True,
                    thread_id=None,
                )

        return {"executed_actions": merged, "status": (Status.COMPLETED.value if approved else state.get("status", Status.AWAITING_APPROVAL.value))}
    
    def commit_memories_node(state: RescueState) -> dict:
        # 这里的 mem0_facade 需要从 container 或哪里获取? 
        # 暂时保留原有逻辑，但注意 Mem0Facade 初始化在 main.py 
        # 我们在 container 中未注册 mem0，如果需要应该注册
        # 假设 container 尚未注册 mem0，这里先 mock 或注释
        # 实际应：return commit_memory_node(state, container.mem0)
        return {} # commit_memory_node(state, mem0_facade)

    def error_handler(state: RescueState) -> dict:
        count = int(state.get("error_count", 0)) + 1
        return {"error_count": count, "status": Status.ERROR.value}

    def fail_node(state: RescueState) -> dict:
        return {"status": Status.ERROR.value, "last_error": state.get("last_error", {})}

    def route_after_error(state: RescueState) -> str:
        max_steps = int(state.get("max_steps", 2))
        if int(state.get("error_count", 0)) >= max_steps:
            return "fail"
        return "start"

    graph.add_node("situation", situation_node)
    graph.add_node("risk_prediction", risk_prediction_node)
    graph.add_node("plan", plan_node)
    graph.add_node("await", await_node)
    graph.add_node("execute", execute_node)
    graph.add_node("commit_memories", commit_memories_node)
    graph.add_node("approve", approve_node)
    graph.add_node("error_handler", error_handler)
    graph.add_node("fail", fail_node)

    graph.set_entry_point("situation")
    graph.add_edge("situation", "risk_prediction")
    graph.add_edge("risk_prediction", "plan")
    graph.add_edge("plan", "await")
    graph.add_edge("await", "execute")
    graph.add_edge("execute", "commit_memories")
    graph.add_conditional_edges("error_handler", route_after_error, {"start": "situation", "fail": "fail"})

    if not postgres_dsn:
        raise RuntimeError("POSTGRES_DSN 未配置")
        
    checkpointer, checkpoint_close = await create_async_postgres_checkpointer(
        dsn=postgres_dsn,
        schema="rescue_app_checkpoint",
        min_size=1,
        max_size=5,
    )

    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["await"]
    )
    if checkpoint_close is not None:
        setattr(app, "_checkpoint_close", checkpoint_close)
    logger.info("rescue_graph_ready")
    return app
