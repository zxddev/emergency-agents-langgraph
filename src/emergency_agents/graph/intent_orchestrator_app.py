"""意图编排 LangGraph 子图实现。"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Literal, Optional

import structlog
from typing_extensions import Annotated, NotRequired, Required, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from emergency_agents.config import AppConfig
from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
from emergency_agents.intent.router import scout_dispatch_node, route_from_router

logger = structlog.get_logger(__name__)


class IntentOrchestratorState(TypedDict):
    """意图编排状态。

    核心标识字段（Required）：thread_id, user_id, channel, raw_text
    其他字段（NotRequired）：在图执行过程中逐步填充
    """

    # 核心标识字段（必填）
    thread_id: Required[str]
    user_id: Required[str]
    channel: Required[Literal["voice", "text", "system"]]
    raw_text: Required[str]

    # 业务字段（可选）
    incident_id: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]
    messages: NotRequired[Annotated[list[Dict[str, Any]], add_messages]]

    # 意图识别流程字段（可选）
    intent: NotRequired[Dict[str, Any]]
    intent_prediction: NotRequired[Dict[str, Any]]
    validation_status: NotRequired[Literal["valid", "invalid", "failed"]]
    missing_fields: NotRequired[list[str]]
    prompt: NotRequired[Optional[str]]
    validation_attempt: NotRequired[int]
    memory_hits: NotRequired[list[Dict[str, Any]]]

    # 路由字段（可选）
    router_next: NotRequired[str]
    router_payload: NotRequired[Dict[str, Any]]

    # 审计字段（可选）
    audit_log: NotRequired[list[Dict[str, Any]]]


async def build_intent_orchestrator_graph(
    *,
    cfg: AppConfig,
    llm_client: Any,
    llm_model: str,
    classifier_node: Callable[[Dict[str, Any]], Dict[str, Any]],
    validator_node: Callable[[Dict[str, Any], Any, str], Dict[str, Any]],
    prompt_node: Callable[[Dict[str, Any], Any, str], Dict[str, Any]],
) -> Any:
    """构建意图编排子图。"""

    state_graph = StateGraph(IntentOrchestratorState)

    def _append_audit(state: IntentOrchestratorState, event: Dict[str, Any]) -> list[Dict[str, Any]]:
        audit = list(state.get("audit_log") or [])
        audit.append(event)
        return audit

    def ingest(state: IntentOrchestratorState) -> Dict[str, Any]:
        """入口节点：补齐事件ID并记录审计。"""
        start_time = time.perf_counter()
        incident_id = state.get("incident_id") or RESCUE_DEMO_INCIDENT_ID
        audit = _append_audit(
            state,
            {
                "event": "intent_ingest",
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "timestamp": time.time(),
            },
        )
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.debug(
            "node_ingest_completed",
            thread_id=state.get("thread_id"),
            elapsed_ms=elapsed_ms,
        )
        return {
            "incident_id": incident_id,
            "audit_log": audit,
        }

    def classify(state: IntentOrchestratorState) -> Dict[str, Any]:
        """调用提供的意图分类节点。"""
        start_time = time.perf_counter()
        updated = classifier_node(state)
        intent = (updated.get("intent") or state.get("intent") or {}).copy()
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.debug(
            "node_classify_completed",
            thread_id=state.get("thread_id"),
            elapsed_ms=elapsed_ms,
            intent_type=intent.get("intent_type", "unknown"),
        )
        audit = _append_audit(
            state,
            {
                "event": "intent_classified",
                "intent_type": intent.get("intent_type", "unknown"),
                "confidence": (intent.get("meta") or {}).get("confidence"),
            },
        )
        return updated | {"audit_log": audit}

    def validate(state: IntentOrchestratorState) -> Dict[str, Any]:
        """槽位验证节点。"""
        updated = validator_node(state, llm_client, llm_model)
        audit = _append_audit(
            state,
            {
                "event": "intent_validated",
                "status": updated.get("validation_status", "unknown"),
                "missing": updated.get("missing_fields", []),
            },
        )
        return updated | {"audit_log": audit}

    def prompt_missing(state: IntentOrchestratorState) -> Dict[str, Any]:
        """缺槽追问节点。"""
        updated = prompt_node(state, llm_client, llm_model)
        audit = _append_audit(
            state,
            {
                "event": "intent_prompt_missing",
                "prompt": state.get("prompt"),
            },
        )
        return updated | {"audit_log": audit}

    def finalize_failure(state: IntentOrchestratorState) -> Dict[str, Any]:
        """验证多次失败的终止节点。"""
        audit = _append_audit(
            state,
            {
                "event": "intent_validation_failed",
                "attempt": state.get("validation_attempt", 0),
                "missing": state.get("missing_fields", []),
            },
        )
        return {
            "router_next": "error",
            "router_payload": {
                "reason": "validation_failed",
                "missing_fields": state.get("missing_fields", []),
            },
            "audit_log": audit,
        }

    def route(state: IntentOrchestratorState) -> Dict[str, Any]:
        """根据意图类型确定后续执行节点。"""
        intent = state.get("intent") or {}
        intent_type = str(intent.get("intent_type") or "unknown").strip()
        normalized = intent_type.replace(" ", "").replace("_", "-").lower()

        route_map: Dict[str, str] = {
            # 战术救援 / 模拟
            "rescue-task-generate": "rescue-task-generate",
            "rescue-task-generation": "rescue-task-generate",
            "rescue-simulation": "rescue-simulation",
            # 侦察任务（默认转入简化调度）
            "scout-task-simple": "scout-task-simple",
            "scout-task-generation": "scout-task-simple",
            "scout-task-generate": "scout-task-simple",
            # 设备控制
            "device-control": "device-control",
            "device-control-robotdog": "device_control_robotdog",
            # 任务状态查询
            "task-progress-query": "task-progress-query",
            # 视频分析
            "video-analysis": "video-analysis",
            "video-analyze": "video-analysis",
            # 设备状态查询
            "device-status-query": "device-status-query",
            "device_status_query": "device-status-query",
            # 态势研判，占位实现
            "disaster-analysis": "disaster-analysis",
            "situation-overview": "disaster-analysis",
            # 统一数据查询
            "system-data-query": "system-data-query",
            # 通用对话（新增）
            "general-chat": "general-chat",
        }
        router_next = route_map.get(normalized, "unknown")

        # 结构化日志：记录路由决策过程
        logger.info(
            "intent_routing",
            raw_intent=intent_type,
            normalized_intent=normalized,
            router_target=router_next,
            thread_id=state.get("thread_id"),
            user_id=state.get("user_id"),
        )

        # Scout任务额外日志（用于监控侦察任务流量）
        if router_next == "scout-task-simple":
            logger.info(
                "scout_task_routed",
                thread_id=state.get("thread_id"),
                incident_id=state.get("incident_id"),
                slots=intent.get("slots", {}),
            )

        # 系统数据查询额外日志（用于监控查询类型）
        if router_next == "system-data-query":
            slots = intent.get("slots", {})
            logger.info(
                "system_data_query_routed",
                thread_id=state.get("thread_id"),
                query_type=slots.get("query_type"),
                has_params=bool(slots.get("query_params")),
            )

        audit = _append_audit(
            state,
            {
                "event": "intent_routed",
                "intent_type": intent_type,
                "router_next": router_next,
            },
        )

        payload = {
            "intent": intent,
            "incident_id": state.get("incident_id"),
            "memory_hits": list(state.get("memory_hits") or []),
        }
        return {
            "router_next": router_next,
            "router_payload": payload,
            "audit_log": audit,
        }

    def route_validation(state: IntentOrchestratorState) -> str:
        status = state.get("validation_status", "valid")
        if status not in {"valid", "invalid", "failed"}:
            return "valid"
        return status

    state_graph.add_node("ingest", ingest)
    state_graph.add_node("classify", classify)
    state_graph.add_node("validate", validate)
    state_graph.add_node("prompt", prompt_missing)
    state_graph.add_node("failure", finalize_failure)
    state_graph.add_node("route", route)
    state_graph.add_node("scout_dispatch", scout_dispatch_node)

    state_graph.set_entry_point("ingest")
    state_graph.add_edge("ingest", "classify")
    state_graph.add_edge("classify", "validate")
    state_graph.add_conditional_edges(
        "validate",
        route_validation,
        {
            "valid": "route",
            "invalid": "prompt",
            "failed": "failure",
        },
    )
    state_graph.add_edge("prompt", "validate")
    state_graph.add_edge("failure", "__end__")
    # route节点根据router_next条件路由到不同节点
    state_graph.add_conditional_edges(
        "route",
        route_from_router,
        {
            "scout_dispatch": "scout_dispatch",  # 侦察派遣流程
            "analysis": "__end__",  # 默认结束
            "done": "__end__",  # 完成
            "report_intake": "__end__",  # 报告受理（TODO: 对接子图）
            "annotation_lifecycle": "__end__",  # 标注生命周期（TODO: 对接子图）
            "robotdog_control": "__end__",  # 机器狗控制（TODO: 对接子图）
            "general-chat": "__end__",  # 通用对话（新增）
        },
    )
    state_graph.add_edge("scout_dispatch", "__end__")

    if not cfg.postgres_dsn:
        raise RuntimeError("POSTGRES_DSN 未配置，无法构建意图编排子图。")
    # 修复性能问题：大幅增加连接池大小以支持高并发checkpoint操作
    # 之前 min_size=1, max_size=1 导致严重的连接瓶颈
    checkpointer, close_cb = await create_async_postgres_checkpointer(
        dsn=cfg.postgres_dsn,
        schema="intent_checkpoint",
        min_size=20,  # 保持20个常驻连接，避免频繁创建连接的开销
        max_size=100,  # 支持最多100个并发连接，应对高峰流量
    )
    logger.info("intent_graph_checkpointer_ready", schema="intent_checkpoint")
    compiled = state_graph.compile(checkpointer=checkpointer)
    setattr(compiled, "_checkpoint_close", close_cb)
    return compiled
