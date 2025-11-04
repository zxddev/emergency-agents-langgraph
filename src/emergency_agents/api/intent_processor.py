from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

import structlog

from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.graph.intent_orchestrator_app import IntentOrchestratorState
from emergency_agents.intent.registry import IntentHandlerRegistry
from emergency_agents.intent.schemas import INTENT_SLOT_TYPES, BaseSlots
from emergency_agents.memory.conversation_manager import ConversationManager, MessageRecord
from emergency_agents.context.service import ContextService
from emergency_agents.memory.mem0_facade import MemoryFacade
from emergency_agents.ui.actions import serialize_actions

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class Mem0Metrics:
    """mem0 指标回调集合。"""

    inc_search_success: Callable[[], None]
    inc_search_failure: Callable[[str], None]
    observe_search_duration: Callable[[float], None]
    inc_add_success: Callable[[], None]
    inc_add_failure: Callable[[str], None]


@dataclass(slots=True)
class IntentProcessResult:
    """意图处理结果。"""

    status: str
    intent: Dict[str, Any]
    result: Dict[str, Any]
    history: List[Dict[str, Any]]
    memory_hits: List[Dict[str, Any]]
    audit_log: List[Dict[str, Any]]
    ui_actions: List[Dict[str, Any]] = field(default_factory=list)


def _normalize_intent_key(intent_type: str) -> str:
    """标准化意图名称，统一使用短横线命名。"""
    return intent_type.strip().replace(" ", "").replace("_", "-").lower()


def _extract_context_from_memories(memory_hits: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """从记忆中提取上下文字段。"""
    context: Dict[str, Any] = {}
    for hit in memory_hits:
        text = ""
        if isinstance(hit, dict):
            text = str(
                hit.get("memory")
                or hit.get("content")
                or hit.get("text")
                or hit.get("value")
                or ""
            )
        if not text:
            continue
        slot_json_start = text.find("槽位:")
        if slot_json_start == -1:
            continue
        json_part = text[slot_json_start + 3 :].strip()
        try:
            slots_dict = json.loads(json_part)
        except json.JSONDecodeError:
            continue
        if not isinstance(slots_dict, dict):
            continue
        for key in ("event_type", "location_name", "mission_type"):
            value = slots_dict.get(key)
            if value and key not in context:
                context[key] = value
    return context


def _build_robotdog_command_text(intent: Dict[str, Any]) -> str:
    slots = intent.get("slots") or {}
    action_raw = slots.get("action") if isinstance(slots, dict) else None
    action = str(action_raw).strip() if action_raw else "执行动作"
    return f"机器狗 {action}"


def _to_serializable_mapping(obj: Any) -> Dict[str, Any] | None:
    if obj is None:
        return None
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, dict):
        return dict(obj)
    return None


async def _handle_robotdog_control(
    *,
    intent: Dict[str, Any],
    slots_payload: Dict[str, Any],
    voice_control_graph: Any | None,
    thread_id: str,
    router_state: IntentOrchestratorState,
    persist_message: Callable[[str, Optional[str]], "MessageRecord"],
    history_records: List["MessageRecord"],
    build_history: Callable[[List["MessageRecord"]], List[Dict[str, Any]]],
    user_id: str,
    incident_id: str,
    mem: MemoryFacade,
    mem0_metrics: Mem0Metrics,
    channel: str,
    memory_hits: List[Dict[str, Any]],
) -> IntentProcessResult:
    audit_log = list(router_state.get("audit_log") or [])
    intent_type = intent.get("intent_type")

    if voice_control_graph is None:
        response_text = "语音控制子图未启用，无法执行机器狗控制。"
        saved = await persist_message(response_text, intent_type)
        history_records.append(saved)
        audit_log.append({"event": "robotdog_control_unavailable"})
        return IntentProcessResult(
            status="error",
            intent=intent,
            result={"response_text": response_text},
            history=build_history(history_records),
            memory_hits=memory_hits,
            audit_log=audit_log,
        )

    command_text = _build_robotdog_command_text(intent)
    voice_state_input: Dict[str, Any] = {
        "raw_text": command_text,
        "auto_confirm": True,
        "device_type": "robotdog",
    }
    slot_device_id = slots_payload.get("device_id")
    if slot_device_id:
        voice_state_input["device_id"] = str(slot_device_id)

    try:
        voice_state = await voice_control_graph.ainvoke(
            voice_state_input,
            config={
                "configurable": {"thread_id": f"robotdog-{thread_id}"},
                "durability": "exit",  # 短流程（设备控制），使用默认高性能模式
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "robotdog_voice_control_failed",
            error=str(exc),
            thread_id=thread_id,
        )
        response_text = f"机器狗控制执行失败：{exc}"
        saved = await persist_message(response_text, intent_type)
        history_records.append(saved)
        audit_log.append({"event": "robotdog_control_failed", "error": str(exc)})
        return IntentProcessResult(
            status="error",
            intent=intent,
            result={"response_text": response_text},
            history=build_history(history_records),
            memory_hits=memory_hits,
            audit_log=audit_log,
        )

    status = voice_state.get("status", "error")
    command_dict = _to_serializable_mapping(voice_state.get("device_command"))
    adapter_result = _to_serializable_mapping(voice_state.get("adapter_result"))
    audit_trail = list(voice_state.get("audit_trail") or [])
    error_detail = voice_state.get("error_detail")

    robotdog_payload: Dict[str, Any] = {
        "status": status,
        "audit_trail": audit_trail,
    }
    if command_dict:
        robotdog_payload["command"] = command_dict
        robotdog_payload.setdefault("device_id", command_dict.get("device_id"))
    elif slot_device_id:
        robotdog_payload["device_id"] = slot_device_id
    if adapter_result:
        robotdog_payload["adapter_result"] = adapter_result
    if error_detail:
        robotdog_payload["error_detail"] = error_detail

    action_name = None
    if command_dict:
        params = command_dict.get("params")
        if isinstance(params, dict):
            action_name = params.get("action")

    if status == "dispatched":
        response_text = f"已向机器狗发送动作：{action_name or '执行动作'}。"
    else:
        response_text = error_detail or "机器狗控制指令执行失败，请稍后重试。"

    saved = await persist_message(response_text, intent_type)
    history_records.append(saved)

    if status == "dispatched":
        try:
            mem.add(
                content=f"意图: {intent_type}, 槽位: {json.dumps(slots_payload, ensure_ascii=False)}",
                user_id=user_id,
                run_id=thread_id,
                metadata={"incident_id": incident_id, "intent_type": intent_type, "channel": channel},
            )
            mem0_metrics.inc_add_success()
        except Exception as exc:  # noqa: BLE001
            mem0_metrics.inc_add_failure(exc.__class__.__name__)
            raise

    audit_log.append(
        {
            "event": "robotdog_control",
            "status": status,
            "action": action_name,
        }
    )

    result_payload = {
        "response_text": response_text,
        "robotdog_control": robotdog_payload,
    }

    return IntentProcessResult(
        status="success" if status == "dispatched" else "error",
        intent=intent,
        result=result_payload,
        history=build_history(history_records),
        memory_hits=memory_hits,
        audit_log=audit_log,
    )


async def process_intent_core(
    *,
    user_id: str,
    thread_id: str,
    message: str,
    metadata: Mapping[str, Any] | None,
    manager: ConversationManager,
    registry: IntentHandlerRegistry,
    orchestrator_graph: Any,
    voice_control_graph: Any | None,
    mem: MemoryFacade,
    build_history: Callable[[List[MessageRecord]], List[Dict[str, Any]]],
    mem0_metrics: Mem0Metrics,
    channel: str = "text",
    context_service: ContextService | None = None,
) -> IntentProcessResult:
    """统一意图处理核心逻辑。"""
    if not message or not message.strip():
        raise ValueError("message不能为空")

    metadata_dict = dict(metadata or {})
    incident_id = str(metadata_dict.get("incident_id") or RESCUE_DEMO_INCIDENT_ID)
    conversation_metadata = metadata_dict | {"incident_id": incident_id}

    await manager.save_message(
        user_id=user_id,
        thread_id=thread_id,
        role="user",
        content=message,
        intent_type=None,
        metadata=metadata_dict,
        conversation_metadata=conversation_metadata,
    )

    history_records = await manager.get_history(thread_id=thread_id, limit=50)
    history_payload = build_history(history_records)

    memory_hits: List[Dict[str, Any]] = []
    enable_mem0 = os.getenv("ENABLE_MEM0", "false").lower() == "true"
    if enable_mem0:
        try:
            t0 = time.perf_counter()
            memory_hits = mem.search(
                query=message,
                user_id=user_id,
                run_id=thread_id,
                top_k=3,
            )
            duration = max(time.perf_counter() - t0, 0.0)
            mem0_metrics.inc_search_success()
            mem0_metrics.observe_search_duration(duration)
        except Exception as exc:  # noqa: BLE001
            reason = exc.__class__.__name__
            mem0_metrics.inc_search_failure(reason)
            # 配置启用但搜索失败：直接抛出，遵循不兜底原则
            raise

    conversation_context = {"incident_id": incident_id} | _extract_context_from_memories(memory_hits)

    messages_for_graph = [
        {"role": item.get("role", "user"), "content": item.get("content", "")}
        for item in history_payload
        if isinstance(item, dict)
    ]
    if memory_hits:
        summary_lines = []
        for record in memory_hits:
            text = ""
            if isinstance(record, dict):
                text = str(
                    record.get("memory")
                    or record.get("content")
                    or record.get("text")
                    or record.get("value")
                    or ""
                )
            if text:
                summary_lines.append(text)
        if summary_lines:
            messages_for_graph.append({"role": "system", "content": "历史记忆:\n" + "\n".join(summary_lines)})

    initial_state: IntentOrchestratorState = {
        "thread_id": thread_id,
        "user_id": user_id,
        "channel": channel,
        "raw_text": message,
        "metadata": metadata_dict,
        "incident_id": incident_id,
        "messages": messages_for_graph,
        "memory_hits": memory_hits,
    }

    logger.warning(
        "intent_graph_checkpointer_type",
        checkpointer_type=type(getattr(orchestrator_graph, "checkpointer", None)).__name__,
    )

    graph_state: IntentOrchestratorState = await orchestrator_graph.ainvoke(
        initial_state,
        config={
            "configurable": {"thread_id": thread_id},
            "durability": "async",  # 中流程（意图编排），异步保存checkpoint平衡性能
        },
    )

    intent = graph_state.get("intent") or {}
    validation_status = graph_state.get("validation_status", "valid")
    router_next = graph_state.get("router_next", "unknown")
    prompt_text = graph_state.get("prompt")

    async def _persist_assistant_message(content: str, intent_type: Optional[str]) -> MessageRecord:
        return await manager.save_message(
            user_id=user_id,
            thread_id=thread_id,
            role="assistant",
            content=content,
            intent_type=intent_type,
            metadata={"incident_id": incident_id, "channel": channel},
            conversation_metadata=conversation_metadata,
        )

    if validation_status == "invalid":
        response_text = prompt_text or "请补充缺失信息以便继续处理。"
        ui_actions_payload: list[Dict[str, Any]] = []

        # 1) 谨慎自动策略：若缺失项全部可由会话上下文补齐，则直接补齐并视为有效
        try:
            itype_raw = str((intent.get("intent_type") or "").strip()).lower()
            itype_norm = itype_raw.replace(" ", "").replace("_", "-")
            missing_fields: List[str] = list(graph_state.get("missing_fields") or [])

            policy_task = os.getenv("AUTO_BINDING_POLICY_TASK", "strict").strip().lower()
            policy_incident = os.getenv("AUTO_BINDING_POLICY_INCIDENT", "strict").strip().lower()

            ctx: SessionContextRecord | None = None
            if context_service is not None:
                try:
                    ctx = await context_service.get(thread_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("session_context_lookup_failed", error=str(exc))

            can_autofill = True if missing_fields else False
            new_slots = dict((intent.get("slots") or {}))
            applied: dict[str, Any] = {}
            for field in missing_fields:
                if field == "incident_id" and policy_incident == "cautious" and ctx and ctx.get("last_incident_id"):
                    new_slots["incident_id"] = ctx["last_incident_id"]  # type: ignore[index]
                    applied[field] = new_slots["incident_id"]
                    continue
                if field in ("task_id", "task_code") and policy_task == "cautious" and ctx and (ctx.get("last_task_id") or ctx.get("last_task_code")):
                    if field == "task_id" and ctx.get("last_task_id"):
                        new_slots["task_id"] = ctx["last_task_id"]  # type: ignore[index]
                        applied[field] = new_slots["task_id"]
                    elif field == "task_code" and ctx.get("last_task_code"):
                        new_slots["task_code"] = ctx["last_task_code"]  # type: ignore[index]
                        applied[field] = new_slots["task_code"]
                    else:
                        can_autofill = False
                    continue
                # 其它缺失字段不可由上下文自动填
                can_autofill = False

            if missing_fields and can_autofill and applied:
                logger.info(
                    "context_autofill_applied",
                    intent_type=itype_norm,
                    fields=list(applied.keys()),
                    thread_id=thread_id,
                )
                intent = dict(intent or {})
                intent["slots"] = new_slots
                validation_status = "valid"
        except Exception as exc:  # noqa: BLE001
            logger.warning("context_autofill_decision_failed", error=str(exc))

        # 2) 若仍无效，构造结构化澄清（设备严格策略A；任务/事件未能全量自动填时亦走澄清）
        if validation_status == "invalid":
            try:
                itype_raw = str((intent.get("intent_type") or "").strip()).lower()
                itype_norm = itype_raw.replace(" ", "").replace("_", "-")
                missing_fields2 = graph_state.get("missing_fields") or []
                if itype_norm in ("video-analysis", "video-analyze") and ("device_name" in missing_fields2 or not (intent.get("slots") or {}).get("device_name")):
                    import psycopg
                    options: list[Dict[str, Any]] = []
                    # recent device
                    recent_label: str | None = None
                    recent_value: str | None = None
                    if context_service is not None:
                        try:
                            ctx2 = await context_service.get(thread_id)
                            if ctx2 and ctx2.get("last_device_name"):
                                recent_label = str(ctx2["last_device_name"])  # type: ignore[index]
                                last_id2 = ctx2.get("last_device_id")
                                recent_value = str(last_id2) if isinstance(last_id2, str) else None
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("session_context_lookup_failed", error=str(exc))
                    sql = (
                        "WITH candidates AS (\n"
                        "  SELECT d.id::text AS id, d.name AS name\n"
                        "    FROM operational.device d\n"
                        "    JOIN operational.device_video_link dvl ON dvl.id = d.id\n"
                        "   WHERE COALESCE(NULLIF(dvl.video_link, ''), '') <> ''\n"
                        "  UNION ALL\n"
                        "  SELECT d.id::text AS id, d.name AS name\n"
                        "    FROM operational.device d\n"
                        "    JOIN operational.device_detail dd ON dd.device_id = d.id\n"
                        "   WHERE COALESCE(NULLIF(dd.device_detail->>'stream_url', ''), '') <> ''\n"
                        ") SELECT id, name FROM candidates GROUP BY id, name ORDER BY name ASC LIMIT 10"
                    )
                    with psycopg.connect(os.getenv("POSTGRES_DSN")) as conn:
                        with conn.cursor() as cur:
                            cur.execute(sql)
                            for dev_id, name in cur.fetchall():
                                options.append({"label": name or dev_id, "device_id": dev_id})
                    if recent_label:
                        already = any(o.get("label") == recent_label for o in options)
                        if not already:
                            options.insert(0, {"label": recent_label, "device_id": recent_value or recent_label})
                    clarify = {
                        "type": "clarify",
                        "slot": "device_name",
                        "options": options,
                        "reason": "视频分析需指定设备名称",
                        "default_index": 0 if options else None,
                    }
                    ui_actions_payload = [clarify]
            except Exception as exc:  # noqa: BLE001
                logger.warning("build_clarify_ui_actions_failed", error=str(exc))

            saved = await _persist_assistant_message(response_text, intent.get("intent_type"))
            history_records.append(saved)
            logger.info(
                "intent_process_result_needs_input",
                intent_type=intent.get("intent_type"),
                missing_fields=graph_state.get("missing_fields") or [],
                thread_id=thread_id,
            )
            return IntentProcessResult(
                status="needs_input",
                intent=intent,
                result={
                    "response_text": response_text,
                    "missing_fields": graph_state.get("missing_fields") or [],
                },
                history=build_history(history_records),
                memory_hits=memory_hits,
                audit_log=graph_state.get("audit_log") or [],
                ui_actions=ui_actions_payload,
            )

    if validation_status == "failed":
        missing_fields = graph_state.get("missing_fields") or []
        if not missing_fields:
            router_payload = graph_state.get("router_payload") or {}
            payload_missing = router_payload.get("missing_fields")
            if isinstance(payload_missing, list):
                missing_fields = [
                    str(item).strip()
                    for item in payload_missing
                    if isinstance(item, str) and str(item).strip()
                ]
        response_text = prompt_text
        if not response_text:
            if missing_fields:
                response_text = f"请补充以下关键信息：{', '.join(missing_fields)}。"
            else:
                response_text = "请补充关键信息后再试。"
        saved = await _persist_assistant_message(response_text, intent.get("intent_type"))
        history_records.append(saved)
        logger.info(
            "intent_process_validation_failed_prompt",
            intent_type=intent.get("intent_type"),
            missing_fields=missing_fields,
            thread_id=thread_id,
        )
        return IntentProcessResult(
            status="needs_input",
            intent=intent,
            result={
                "response_text": response_text,
                "missing_fields": missing_fields,
            },
            history=build_history(history_records),
            memory_hits=memory_hits,
            audit_log=graph_state.get("audit_log") or [],
        )

    if router_next in {"unknown", "error"}:
        response_text = "当前请求无法识别，请调整描述后重试。"
        saved = await _persist_assistant_message(response_text, intent.get("intent_type"))
        history_records.append(saved)
        logger.info(
            "intent_process_result_unknown",
            intent_type=intent.get("intent_type"),
            router_next=router_next,
            thread_id=thread_id,
        )
        return IntentProcessResult(
            status="unknown",
            intent=intent,
            result={
                "response_text": response_text,
            },
            history=build_history(history_records),
            memory_hits=memory_hits,
            audit_log=graph_state.get("audit_log") or [],
        )

    slots_payload = intent.get("slots") or {}

    if router_next == "device_control_robotdog":
        robotdog_result = await _handle_robotdog_control(
            intent=intent,
            slots_payload=slots_payload,
            voice_control_graph=voice_control_graph,
            thread_id=thread_id,
            router_state=graph_state,
            persist_message=_persist_assistant_message,
            history_records=history_records,
            build_history=build_history,
            user_id=user_id,
            incident_id=incident_id,
            mem=mem,
            mem0_metrics=mem0_metrics,
            channel=channel,
            memory_hits=memory_hits,
        )
        return robotdog_result

    canonical = _normalize_intent_key(router_next)
    slot_model = INTENT_SLOT_TYPES.get(router_next) or INTENT_SLOT_TYPES.get(canonical)

    slots_instance: BaseSlots | None = None
    if slot_model is not None:
        try:
            slots_instance = slot_model(**slots_payload)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "slot_model_instantiation_failed",
                intent_type=router_next,
                error=str(exc),
            )
            response_text = f"槽位解析失败：{exc}"
            saved = await _persist_assistant_message(response_text, intent.get("intent_type"))
            history_records.append(saved)
            return IntentProcessResult(
                status="error",
                intent=intent,
                result={"response_text": response_text},
                history=build_history(history_records),
                memory_hits=memory_hits,
                audit_log=graph_state.get("audit_log") or [],
            )

    # 使用短横线形式作为最终意图标识，保持对外一致
    intent = dict(intent or {})
    intent["intent_type"] = canonical
    intent["canonical_intent_type"] = canonical

    handler = registry.get(router_next) or registry.get(canonical)
    if handler is None:
        response_text = "当前意图缺少处理器，请联系系统维护人员。"
        saved = await _persist_assistant_message(response_text, intent.get("intent_type"))
        history_records.append(saved)
        return IntentProcessResult(
            status="error",
            intent=intent,
            result={"response_text": response_text},
            history=build_history(history_records),
            memory_hits=memory_hits,
            audit_log=graph_state.get("audit_log") or [],
        )

    handler_state: Dict[str, Any] = {
        "user_id": user_id,
        "thread_id": thread_id,
        "incident_id": incident_id,
        "conversation_context": conversation_context,
        "memory_hits": memory_hits,
        "metadata": metadata_dict,
    }

    handler_result = await handler.handle(slots_instance or slots_payload, handler_state)

    raw_ui_actions = None
    if isinstance(handler_result, Mapping):
        raw_ui_actions = handler_result.get("ui_actions")
    ui_actions_serialized: List[Dict[str, Any]] = []
    if raw_ui_actions:
        if isinstance(raw_ui_actions, list):
            ui_actions_serialized = serialize_actions(raw_ui_actions)
        else:
            ui_actions_serialized = serialize_actions([raw_ui_actions])
    if ui_actions_serialized:
        logger.info(
            "ui_actions_emitted",
            intent_type=intent.get("intent_type"),
            thread_id=thread_id,
            count=len(ui_actions_serialized),
        )

    response_text = (
        handler_result.get("response_text")
        or handler_result.get("response")
        or "处理完成。"
    )

    saved_assistant = await _persist_assistant_message(response_text, intent.get("intent_type"))
    history_records.append(saved_assistant)

    try:
        mem.add(
            content=f"意图: {intent.get('intent_type')}, 槽位: {json.dumps(slots_payload, ensure_ascii=False)}",
            user_id=user_id,
            run_id=thread_id,
            metadata={"incident_id": incident_id, "intent_type": intent.get("intent_type")},
        )
        mem0_metrics.inc_add_success()
    except Exception as exc:  # noqa: BLE001
        reason = exc.__class__.__name__
        mem0_metrics.inc_add_failure(reason)
        raise

    # 会话记忆写回（事件与任务，谨慎且安全）
    try:
        if context_service is not None:
            # 事件：使用本次 incident_id 作为最近事件
            await context_service.set_last_incident(
                thread_id=thread_id,
                incident_id=incident_id,
                intent_type=intent.get("intent_type"),
            )
            # 任务：若此次槽位携带了 task_id/task_code，则写回。
            slots_for_write = intent.get("slots") or {}
            task_id_val = slots_for_write.get("task_id") if isinstance(slots_for_write, dict) else None
            task_code_val = slots_for_write.get("task_code") if isinstance(slots_for_write, dict) else None
            if isinstance(task_id_val, str) or isinstance(task_code_val, str):
                await context_service.set_last_task(
                    thread_id=thread_id,
                    task_id=task_id_val if isinstance(task_id_val, str) else None,
                    task_code=task_code_val if isinstance(task_code_val, str) else None,
                    intent_type=intent.get("intent_type"),
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("session_context_write_failed", error=str(exc))

    # 会话记忆写回：视频分析成功后记录最近设备
    if context_service is not None and intent.get("intent_type") in ("video-analysis",):
        try:
            vi = None
            if isinstance(handler_result, Mapping):
                vi = handler_result.get("video_analysis")
            if isinstance(vi, Mapping) and str(vi.get("status")) == "success":
                await context_service.set_last_device(
                    thread_id=thread_id,
                    device_id=vi.get("device_id") if isinstance(vi.get("device_id"), str) else None,
                    device_name=vi.get("device_name") if isinstance(vi.get("device_name"), str) else None,
                    device_type=None,
                    intent_type="video-analysis",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("session_context_write_failed", error=str(exc))

    return IntentProcessResult(
        status="success",
        intent=intent,
        result=handler_result,
        history=build_history(history_records),
        memory_hits=memory_hits,
        audit_log=graph_state.get("audit_log") or [],
        ui_actions=ui_actions_serialized,
    )
