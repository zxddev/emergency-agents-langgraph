# Copyright 2025 msq
from __future__ import annotations

from enum import Enum
from typing import TypedDict, Literal

from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from emergency_agents.agents.situation import situation_agent
from emergency_agents.agents.risk_predictor import risk_predictor_agent
from emergency_agents.agents.plan_generator import plan_generator_agent
from emergency_agents.agents.memory_commit import commit_memory_node
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig
from emergency_agents.graph.kg_service import KGService, KGConfig
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.memory.mem0_facade import Mem0Config, MemoryFacade
from langgraph.types import interrupt, Command
from typing import Dict, Any, List, Tuple

from emergency_agents.intent.classifier import intent_classifier_node
from emergency_agents.intent.validator import validate_and_prompt_node
from emergency_agents.intent.prompt_missing import prompt_missing_slots_node
from emergency_agents.intent.router import intent_router_node, route_from_router
from emergency_agents.policy.evidence import evidence_gate_ok


class Status(str, Enum):
    """救援线程的状态枚举。"""
    INIT = "init"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class RescueState(TypedDict, total=False):
    rescue_id: str
    user_id: str
    status: Literal["init", "awaiting_approval", "running", "completed", "error"]
    messages: list
    error_count: int
    max_steps: int
    last_error: dict
    
    raw_report: str
    situation: dict
    primary_disaster: dict
    secondary_disasters: list
    predicted_risks: list
    timeline: list
    compound_risks: list
    available_resources: dict
    blocked_roads: list
    
    proposals: list
    approved_ids: list
    executed_actions: list
    
    plan: dict
    plan_approved: bool
    alternative_plans: list
    
    equipment_recommendations: list
    risk_level: int
    hazards: list
    
    pending_memories: list
    committed_memories: list
    
    intent: dict
    uav_tracks: list
    fleet_position: dict
    integration_logs: list
    router_next: str
    validation_status: str
    validation_attempt: int
    prompt: str
    missing_fields: list
    kg_hits_count: int
    rag_case_refs_count: int


def build_app(sqlite_path: str = "./checkpoints.sqlite3", postgres_dsn: str | None = None):
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
    
    kg_service = KGService(KGConfig(
        uri=cfg.neo4j_uri or "bolt://localhost:7687",
        user=cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        password=cfg.neo4j_password or "example-neo4j"
    ))
    
    rag_pipeline = RagPipeline(
        qdrant_url=cfg.qdrant_url or "http://localhost:6333",
        embedding_model=cfg.embedding_model,
        embedding_dim=cfg.embedding_dim,
        openai_base_url=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        llm_model=cfg.llm_model
    )
    
    mem0_facade = MemoryFacade(Mem0Config(
        qdrant_url=cfg.qdrant_url or "http://localhost:6333",
        qdrant_collection="mem0_collection",
        embedding_model=cfg.embedding_model,
        embedding_dim=cfg.embedding_dim,
        neo4j_uri=cfg.neo4j_uri or "bolt://localhost:7687",
        neo4j_user=cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        neo4j_password=cfg.neo4j_password or "example-neo4j",
        openai_base_url=cfg.openai_base_url,
        # pragma: allowlist secret - placeholder credential for development
        openai_api_key=cfg.openai_api_key,
        graph_llm_model=cfg.llm_model
    ))

    def situation_node(state: RescueState) -> dict:
        return situation_agent(state, llm_client, cfg.llm_model)
    
    def risk_prediction_node(state: RescueState) -> dict:
        return risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)

    def plan_node(state: RescueState) -> dict:
        return plan_generator_agent(state, kg_service, llm_client, cfg.llm_model)

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

    def route_validation(state: RescueState) -> str:
        status = state.get("validation_status", "valid")
        if status not in ("valid", "invalid", "failed"):
            return "valid"
        return status

    # 新增：意图分类、校验与路由
    graph.add_node("intent", lambda s: intent_classifier_node(s, llm_client, cfg.llm_model))
    graph.add_node("validator", lambda s: validate_and_prompt_node(s, llm_client, cfg.llm_model))
    graph.add_node("prompt_slots", lambda s: prompt_missing_slots_node(s, llm_client, cfg.llm_model))
    graph.add_node("intent_router", intent_router_node)
    
    graph.add_conditional_edges("validator", route_validation, {
        "valid": "intent_router",
        "invalid": "prompt_slots",
        "failed": "fail"
    })
    graph.add_conditional_edges("intent_router", route_from_router, {"analysis": "situation", "done": "commit_memories"})

    graph.add_node("situation", situation_node)
    graph.add_node("risk_prediction", risk_prediction_node)
    graph.add_node("plan", plan_node)
    graph.add_node("await", await_node)
    graph.add_node("execute", execute_node)
    graph.add_node("commit_memories", commit_memories_node)
    graph.add_node("approve", approve_node)
    graph.add_node("error_handler", error_handler)
    graph.add_node("fail", fail_node)

    graph.set_entry_point("intent")
    graph.add_edge("intent", "validator")
    graph.add_edge("prompt_slots", "validator")
    graph.add_edge("situation", "risk_prediction")
    graph.add_edge("risk_prediction", "plan")
    graph.add_edge("plan", "await")
    graph.add_edge("await", "execute")
    graph.add_edge("execute", "commit_memories")
    graph.add_conditional_edges("error_handler", route_after_error, {"start": "situation", "fail": "fail"})

    checkpointer = None
    if postgres_dsn:
        try:
            pool = ConnectionPool(conninfo=postgres_dsn, max_size=5, open=False, kwargs={"options": "-c search_path=langgraph_checkpoint"})
            pool.open()
            with pool.connection() as conn:
                conn.autocommit = True
                conn.execute("CREATE SCHEMA IF NOT EXISTS langgraph_checkpoint")
                conn.execute("SET search_path TO langgraph_checkpoint")
                saver = PostgresSaver(conn)
                saver.setup()
            checkpointer = PostgresSaver(pool)
        except Exception:
            checkpointer = None
    if checkpointer is None:
        checkpointer = SqliteSaver.from_conn_string(sqlite_path)

    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["await"]  # 在审批节点前中断，HITL
    )
    return app
