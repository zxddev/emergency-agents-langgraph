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
    """构建 LangGraph 应用。

    节点职责：
    - situation：态势感知，提取结构化信息
    - plan：生成建议（若外部已注入则不覆盖）。
    - await：显式中断等待人工批准。
    - execute：仅执行已批准的建议。
    - approve：设置完成态。
    - error_handler：错误累加。
    - fail：终止节点，固定置为 error。
    """
    graph = StateGraph(RescueState)
    
    cfg = AppConfig.load_from_env()
    llm_client = get_openai_client(cfg)
    if not cfg.qdrant_url:
        raise RuntimeError("QDRANT_URL must be configured")
    
    kg_service = KGService(KGConfig(
        uri=cfg.neo4j_uri or "bolt://192.168.1.40:7687",
        user=cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        password=cfg.neo4j_password or "example-neo4j"
    ))
    
    rag_pipeline = RagPipeline(
        qdrant_url=cfg.qdrant_url,
        qdrant_api_key=cfg.qdrant_api_key,
        embedding_model=cfg.embedding_model,
        embedding_dim=cfg.embedding_dim,
        openai_base_url=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        llm_model=cfg.llm_model
    )
    
    mem0_facade = MemoryFacade(Mem0Config(
        qdrant_url=cfg.qdrant_url,
        qdrant_api_key=cfg.qdrant_api_key,
        qdrant_collection="mem0_collection",
        embedding_model=cfg.embedding_model,
        embedding_dim=cfg.embedding_dim,
        neo4j_uri=cfg.neo4j_uri or "bolt://192.168.1.40:7687",
        neo4j_user=cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        neo4j_password=cfg.neo4j_password or "example-neo4j",
        openai_base_url=cfg.openai_base_url,
        # pragma: allowlist secret - placeholder credential for development
        openai_api_key=cfg.openai_api_key,
        graph_llm_model=cfg.llm_model
    ))
    orchestrator_client = OrchestratorClient()

    def situation_node(state: RescueState) -> dict:
        return situation_agent(state, llm_client, cfg.llm_model)
    
    def risk_prediction_node(state: RescueState) -> dict:
        return risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)

    def plan_node(state: RescueState) -> dict:
        return plan_generator_agent(
            state,
            kg_service,
            llm_client,
            cfg.llm_model,
            orchestrator_client=orchestrator_client,
        )
    
    def report_intake_node(state: RescueState) -> dict:
        return report_intake_agent(state)
    
    def annotation_lifecycle_node(state: RescueState) -> dict:
        return annotation_lifecycle_agent(state)
    
    def rescue_task_generate_node(state: RescueState) -> dict:
        return rescue_task_generate_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)

    def approve_node(state: RescueState) -> dict:
        if state.get("status") == Status.COMPLETED.value:
            return {}
        return {"status": Status.COMPLETED.value}

    def await_node(state: RescueState) -> dict:
        """人工审批中断节点：将当前提案暴露给外部系统并等待恢复。

        返回值由 `Command(resume=approved_ids)` 注入。
        """
        payload = {"proposals": state.get("proposals", [])}
        approved_ids = interrupt(payload)

        # schema 校验：必须是字符串列表，且全部在提案ID集合中
        proposals_list = state.get("proposals") or []
        valid_ids = {p.get("id") for p in proposals_list if isinstance(p, dict) and p.get("id")}

        if approved_ids is None:
            approved_ids = []
        if not isinstance(approved_ids, list):
            raise TypeError("approved_ids must be a list of strings")
        for pid in approved_ids:
            if not isinstance(pid, str):
                raise TypeError("every approved_id must be a string")
            if pid not in valid_ids:
                raise ValueError(f"approved_id not found in proposals: {pid}")

        # 去重但保序
        seen = set()
        deduped = []
        for pid in approved_ids:
            if pid not in seen:
                seen.add(pid)
                deduped.append(pid)

        return {"approved_ids": deduped}

    def execute_node(state: RescueState) -> dict:
        proposals = {p.get("id"): p for p in (state.get("proposals") or []) if isinstance(p, dict) and p.get("id")}
        approved = [pid for pid in (state.get("approved_ids") or []) if pid in proposals]
        executed = [proposals[pid] for pid in approved]
        merged = (state.get("executed_actions") or []) + executed

        # 审计：记录每个执行的proposal
        if executed:
            from emergency_agents.audit.logger import log_execution
            for item in executed:
                # 证据化Gate：仅在通过时才视为可执行
                ok, reason = evidence_gate_ok(state)
                if not ok:
                    # 写入审计并保持待审批状态
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
        return commit_memory_node(state, mem0_facade)

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

    # 新增：意图分类、校验与路由
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
        raise RuntimeError("POSTGRES_DSN 未配置，无法构建救援编排子图。")
    logger.info("rescue_graph_create_checkpointer", schema="rescue_app_checkpoint")
    checkpointer, checkpoint_close = await create_async_postgres_checkpointer(
        dsn=postgres_dsn,
        schema="rescue_app_checkpoint",
        min_size=1,
        max_size=5,
    )

    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["await"]  # 在审批节点前中断，HITL
    )
    if checkpoint_close is not None:
        setattr(app, "_checkpoint_close", checkpoint_close)
    logger.info("rescue_graph_ready")
    return app
