"""意图编排 LangGraph 子图实现。"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Literal, Optional

import structlog
from typing_extensions import Annotated, TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

from emergency_agents.config import AppConfig
from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer

logger = structlog.get_logger(__name__)


class IntentOrchestratorState(TypedDict, total=False):
    """意图编排状态。"""

    thread_id: str
    user_id: str
    channel: Literal["voice", "text", "system"]
    incident_id: str
    raw_text: str
    metadata: Dict[str, Any]
    messages: Annotated[list[Dict[str, Any]], add_messages]
    intent: Dict[str, Any]
    intent_prediction: Dict[str, Any]
    validation_status: Literal["valid", "invalid", "failed"]
    missing_fields: list[str]
    prompt: Optional[str]
    validation_attempt: int
    memory_hits: list[Dict[str, Any]]
    router_next: str
    router_payload: Dict[str, Any]
    audit_log: list[Dict[str, Any]]


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
        return {
            "incident_id": incident_id,
            "audit_log": audit,
        }

    def classify(state: IntentOrchestratorState) -> Dict[str, Any]:
        """调用提供的意图分类节点。"""
        updated = classifier_node(state)
        intent = (updated.get("intent") or state.get("intent") or {}).copy()
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
            "rescue-task-generate": "rescue-task-generate",
            "rescue-task-generation": "rescue-task-generate",
            "rescue-simulation": "rescue-simulation",
            "scout-task-generate": "scout-task-generate",
            "scout-task-generation": "scout-task-generate",  # 兼容性别名
            "device-control": "device-control",
            "device-control-robotdog": "device_control_robotdog",
            "task-progress-query": "task-progress-query",
            "location-positioning": "location-positioning",
            "video-analysis": "video-analysis",
            "ui-camera-flyto": "ui_camera_flyto",
            "ui-toggle-layer": "ui_toggle_layer",
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
        if router_next == "scout-task-generate":
            logger.info(
                "scout_task_routed",
                thread_id=state.get("thread_id"),
                incident_id=state.get("incident_id"),
                slots=intent.get("slots", {}),
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
    state_graph.add_edge("route", "__end__")

    if not cfg.postgres_dsn:
        raise RuntimeError("POSTGRES_DSN 未配置，无法构建意图编排子图。")
    checkpointer, close_cb = await create_async_postgres_checkpointer(
        dsn=cfg.postgres_dsn,
        schema="intent_checkpoint",
        min_size=1,
        max_size=1,
    )
    logger.info("intent_graph_checkpointer_ready", schema="intent_checkpoint")
    compiled = state_graph.compile(checkpointer=checkpointer)
    setattr(compiled, "_checkpoint_close", close_cb)
    return compiled
