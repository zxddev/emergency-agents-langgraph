from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional
import re
from urllib.parse import quote

import httpx
import structlog
import websockets

from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.intent.pipeline import intent_pipeline
from emergency_agents.intent.registry import IntentHandlerRegistry
from emergency_agents.intent.handlers.device_control import DeviceControlHandler, RobotDogControlHandler
from emergency_agents.intent.handlers.device_status import DeviceStatusQueryHandler
from emergency_agents.intent.handlers.system_data_query import SystemDataQueryHandler
from emergency_agents.intent.handlers.disaster_overview import DisasterOverviewHandler
from emergency_agents.intent.handlers.rescue_task_generation import (
    RescueSimulationHandler,
    RescueTaskGenerationHandler,
)
from emergency_agents.intent.handlers.rescue_team_dispatch import RescueTeamDispatchHandler
from emergency_agents.intent.handlers.scout_task_simple import SimpleScoutDispatchHandler
from emergency_agents.intent.handlers.task_progress import TaskProgressQueryHandler
from emergency_agents.intent.handlers.video_analysis import VideoAnalysisHandler
from emergency_agents.intent.schemas import INTENT_SLOT_TYPES, BaseSlots
from emergency_agents.memory.conversation_manager import ConversationManager, MessageRecord
from emergency_agents.context.service import ContextService, SessionContextRecord
from emergency_agents.memory.mem0_facade import MemoryFacade, DisabledMemoryFacade
from emergency_agents.ui.actions import serialize_actions

logger = structlog.get_logger(__name__)
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


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


def _extract_latest_task_id_from_history(history_records: List[MessageRecord]) -> Optional[str]:
    """从对话历史中提取最近出现的 UUID（用于任务ID指代）。"""
    for msg in reversed(history_records):
        try:
            if str(msg.role).lower() != "assistant":
                continue
            match = _UUID_RE.search(msg.content or "")
            if match:
                return match.group(0)
        except Exception:
            continue
    return None


def _is_task_assignee_followup(message: str) -> bool:
    """粗略检测“哪几台/哪两台参与了”类追问。"""
    text = message.strip()
    if not text:
        return False
    keywords = ["哪几台", "哪两台", "哪俩", "哪两个", "哪几辆", "哪两辆"]
    return any(kw in text for kw in keywords)


def _encode_intent_for_mem0(intent_type: str | None) -> str:
    """将意图名称转换为 Neo4j 合法的关系名。"""
    raw = str(intent_type or "").strip()
    if not raw:
        return "UNKNOWN"
    encoded = quote(raw, safe="")
    sanitized = encoded.replace("%", "_").replace("-", "_")
    sanitized = sanitized or "UNKNOWN"
    if not sanitized[0].isalpha():
        sanitized = f"A_{sanitized}"
    return sanitized.upper()


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
    action_raw = None
    if isinstance(slots, dict):
        action_raw = (
            slots.get("action")
            or slots.get("command")
            or slots.get("动作")
        )
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


def _normalize_memory_hits(raw: Any) -> List[Dict[str, Any]]:
    """将 mem0 返回的结构整理为列表。"""
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        candidates = raw.get("results") or raw.get("memories") or []
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
    return []


def _is_robotdog_talk_message(message: str) -> bool:
    """检测是否为机器狗侦察/识别类对话指令（走对话业务逻辑，而非本地识别/控制）。

    规则：包含“机器狗”或 robotdog，
    且包含侦察/识别/观察/前方/目标等"对话/识别"关键词之一，
    同时不包含典型的控制动作（起立/前进/后退/左转/停止 等），
    以避免把明确动作类指令误判为对话识别。
    """
    text = (message or "").strip()
    if not text:
        return False
    lowered = text.lower()
    has_robotdog = ("机器狗" in text) or ("robotdog" in lowered)
    if not has_robotdog:
        return False
    # 对话/识别类关键词
    talk_keywords = ["识别", "侦察", "侦查", "观察", "查看", "看看", "看一下", "前方", "前面", "目标"]
    if not any(kw in text for kw in talk_keywords):
        return False
    # 典型控制动作关键词：如果同时出现，则优先认为是控制意图而非对话识别
    control_keywords_cn = ["前进", "向前", "后退", "向后", "起立", "站立", "趴下", "坐下", "左转", "右转", "停止", "急停"]
    control_keywords_en = [
        "forward",
        "back",
        "backward",
        "up",
        "down",
        "turnleft",
        "turn_right",
        "turnright",
        "stop",
        "forcestop",
    ]
    if any(kw in text for kw in control_keywords_cn):
        return False
    if any(kw in lowered for kw in control_keywords_en):
        return False
    return True


async def _handle_robotdog_control(
    *,
    intent: Dict[str, Any],
    slots_payload: Dict[str, Any],
    voice_control_graph: Any | None,
    thread_id: str,
    router_state: Dict[str, Any], # Changed from IntentOrchestratorState to Dict
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

    logger.info(
        "robotdog_control_intent_received",
        thread_id=thread_id,
        user_id=user_id,
        intent_type=intent_type,
        slots=slots_payload,
        channel=channel,
    )

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
        logger.info(
            "robotdog_control_command_built",
            thread_id=thread_id,
            user_id=user_id,
            device_id=command_dict.get("device_id"),
            device_vendor=command_dict.get("device_vendor"),
            command_type=command_dict.get("command_type"),
            action=(command_dict.get("params") or {}).get("action") if isinstance(command_dict.get("params"), dict) else None,
            status=status,
        )
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


async def _handle_robotdog_talk(
    *,
    user_message: str,
    thread_id: str,
    user_id: str,
    persist_message: Callable[[str, Optional[str]], Awaitable[MessageRecord]],
    history_records: List[MessageRecord],
    build_history: Callable[[List[MessageRecord]], List[Dict[str, Any]]],
    stream_sink: Callable[[str], Awaitable[None]] | None,
) -> IntentProcessResult:
    """新业务逻辑：机器狗对话/侦察指令，改为调用 adapter-hub 的 talk 通道。

    - HTTP 固定调用 /adapter-hub/api/v3/device-access/control 下发 text
    - 然后连接 ws://.../adapter-hub/api/v3/ws/talk 流式读取回复
    - 将流式文本通过 stream_sink 推送到前端，并在结束后写入会话历史
    """
    http_url = "http://192.168.31.40:8082/adapter-hub/api/v3/device-access/control"
    ws_url = "ws://192.168.31.40:8082/adapter-hub/api/v3/ws/talk"

    # 通过 WebSocket 流式读取机器狗返回。
    # 为避免丢帧，先建立 WS 连接，再下发 HTTP 指令。
    chunks: list[str] = []
    ws_error: str | None = None

    async def _read_ws() -> None:
        nonlocal chunks, ws_error
        try:
            async with websockets.connect(ws_url) as ws:  # type: ignore[arg-type]
                # 1) 在 WS 建立成功后下发对话指令（HTTP）
                payload = {
                    "deviceId": "11",
                    "deviceVendor": "dqDog",
                    "commandType": "talk",
                    "params": {"text": user_message},
                }
                try:
                    async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                        resp = await client.post(http_url, json=payload)
                        resp.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    ws_error = str(exc)
                    logger.error(
                        "robotdog_talk_http_failed",
                        error=str(exc),
                        thread_id=thread_id,
                        user_id=user_id,
                    )
                    return

                # 2) 监听 WS，按 JSON 协议增量读取 {text, is_end}
                async for msg in ws:
                    if isinstance(msg, bytes):
                        raw = msg.decode("utf-8", errors="ignore")
                    else:
                        raw = str(msg)
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        # 非JSON时直接当作纯文本
                        text_part = raw
                        is_end = False
                    else:
                        if isinstance(data, dict):
                            # 优先使用标准字段 text，否则原样透传整个JSON字符串
                            text_value = data.get("text")
                            if text_value is None:
                                text_part = raw
                            else:
                                text_part = str(text_value).strip()
                            is_end = bool(data.get("is_end"))
                        else:
                            # 对于 list / 其他JSON类型，直接把原始内容当作文本返回给前端
                            text_part = raw
                            is_end = False

                    logger.info(
                        "robotdog_talk_ws_message",
                        thread_id=thread_id,
                        user_id=user_id,
                        raw_preview=raw[:200],
                        text=text_part,
                        is_end=is_end,
                    )

                    if text_part:
                        chunks.append(text_part)
                        if stream_sink is not None:
                            try:
                                await stream_sink(text_part)
                            except Exception as sink_err:  # noqa: BLE001
                                logger.error(
                                    "robotdog_talk_stream_sink_failed",
                                    error=str(sink_err),
                                    thread_id=thread_id,
                                    user_id=user_id,
                                )
                    if is_end:
                        break
        except Exception as exc:  # noqa: BLE001
            ws_error = str(exc)
            logger.error(
                "robotdog_talk_ws_failed",
                error=ws_error,
                thread_id=thread_id,
                user_id=user_id,
            )

    # 给WS一段合理时间收完整对话，避免无限等待
    try:
        await asyncio.wait_for(_read_ws(), timeout=30.0)
    except asyncio.TimeoutError:
        ws_error = ws_error or "ws_timeout"
        logger.warning(
            "robotdog_talk_ws_timeout",
            thread_id=thread_id,
            user_id=user_id,
        )

    full_text = "".join(chunks).strip()
    if not full_text:
        if ws_error:
            response_text = f"机器狗识别通道异常：{ws_error}"
        else:
            response_text = "机器狗已接收指令，但未返回可读文本。"
    else:
        response_text = full_text

    saved = await persist_message(response_text, "device_control_robotdog")
    history_records.append(saved)

    result_payload: Dict[str, Any] = {
        "response_text": response_text,
        "robotdog_talk": {
            "status": "success" if full_text else "no_text",
            "text": full_text,
        },
    }
    if ws_error:
        result_payload["robotdog_talk"]["ws_error"] = ws_error  # type: ignore[index]

    return IntentProcessResult(
        status="success" if full_text else "error",
        intent={
            "intent_type": "device_control_robotdog",
            "slots": {"text": user_message},
        },
        result=result_payload,
        history=build_history(history_records),
        memory_hits=[],
        audit_log=[{"event": "robotdog_talk_completed", "has_text": bool(full_text)}],
    )


async def _handle_dialogue_fallback(
    *,
    message: str,
    intent: Dict[str, Any],
    thread_id: str,
    user_id: str,
    persist_message: Callable[[str, Optional[str]], Awaitable[MessageRecord]],
    history_records: List[MessageRecord],
    build_history: Callable[[List[MessageRecord]], List[Dict[str, Any]]],
    memory_hits: List[Dict[str, Any]],
    audit_log: List[Dict[str, Any]],
    dialogue_graph: Any | None,
) -> IntentProcessResult:
    logger.info(
        "dialogue_fallback_invoked",
        thread_id=thread_id,
        user_id=user_id,
        message_preview=message[:80],
    )
    response_text = "收到，目前未识别到明确任务，我将根据现有信息提供研判。"
    dialogue_result: Dict[str, Any] = {}
    if dialogue_graph is not None:
        normalized_memories = _normalize_memory_hits(memory_hits)
        dialogue_state = {
            "thread_id": thread_id,
            "user_id": user_id,
            "raw_text": message,
            "conversation_history": build_history(history_records),
            "memory_hits": normalized_memories,
        }
        logger.info("dialogue_graph_invoke_start", thread_id=thread_id)
        dialogue_result = await dialogue_graph.ainvoke(
            dialogue_state,
            config={"configurable": {"thread_id": thread_id}},
        )
        logger.info(
            "dialogue_graph_invoke_complete",
            thread_id=thread_id,
            has_response=bool(isinstance(dialogue_result, dict) and dialogue_result.get("response_text")),
        )
        if isinstance(dialogue_result, dict):
            response_text = str(dialogue_result.get("response_text") or response_text)
            dialogue_audit = dialogue_result.get("audit_log")
            if isinstance(dialogue_audit, list):
                audit_log.extend(dialogue_audit)
    saved = await persist_message(response_text, intent.get("intent_type"))
    history_records.append(saved)
    result_payload: Dict[str, Any] = {"response_text": response_text, "echo": message}
    if isinstance(dialogue_result, dict):
        for key in ("suggestions", "context_block"):
            value = dialogue_result.get(key)
            if value:
                result_payload[key] = value
    return IntentProcessResult(
        status="dialogue",
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
    # orchestrator_graph: Any, # Removed
    voice_control_graph: Any | None,
    dialogue_graph: Any | None,
    mem: MemoryFacade | DisabledMemoryFacade,
    build_history: Callable[[List[MessageRecord]], List[Dict[str, Any]]],
    mem0_metrics: Mem0Metrics,
    channel: str = "text",
    context_service: ContextService | None = None,
    enable_mem0: bool = True,
    stream_sink: Callable[[str], Awaitable[None]] | None = None,
) -> IntentProcessResult:
    """统一意图处理核心逻辑。"""
    if not message or not message.strip():
        raise ValueError("message不能为空")

    cleaned_message = message.strip()
    logger.info(
        "intent_message_received",
        thread_id=thread_id,
        user_id=user_id,
        channel=channel,
        text=cleaned_message,
    )

    metadata_dict = dict(metadata or {})
    incident_id = str(metadata_dict.get("incident_id") or RESCUE_DEMO_INCIDENT_ID)
    conversation_metadata = metadata_dict | {"incident_id": incident_id}

    await manager.save_message(
        user_id=user_id,
        thread_id=thread_id,
        role="user",
        content=cleaned_message,
        intent_type=None,
        metadata=metadata_dict,
        conversation_metadata=conversation_metadata,
    )

    history_records = await manager.get_history(thread_id=thread_id, limit=50)
    history_payload = build_history(history_records)

    memory_hits: List[Dict[str, Any]] = []
    # 性能优化：对于设备状态查询类意图，跳过mem0搜索以减少延迟
    # 设备查询是无状态的，不需要历史记忆
    skip_mem0_for_device = "设备" in cleaned_message or "device" in cleaned_message.lower()

    if enable_mem0 and not skip_mem0_for_device:
        try:
            t0 = time.perf_counter()
            memory_hits = mem.search(
                query=cleaned_message,
                user_id=user_id,
                run_id=thread_id,
                top_k=3,
            )
            duration = max(time.perf_counter() - t0, 0.0)
            mem0_metrics.inc_search_success()
            mem0_metrics.observe_search_duration(duration)
            logger.info(
                "mem0_search_completed",
                thread_id=thread_id,
                duration_ms=int(duration * 1000),
                hits_count=len(memory_hits),
            )
        except Exception as exc:  # noqa: BLE001
            reason = exc.__class__.__name__
            mem0_metrics.inc_search_failure(reason)
            # 配置启用但搜索失败：直接抛出，遵循不兜底原则
            raise
    else:
        logger.info(
            "mem0_disabled_skip",
            thread_id=thread_id,
            channel=channel,
        )

    session_ctx: SessionContextRecord | None = None
    if context_service is not None:
        try:
            session_ctx = await context_service.get(thread_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("session_context_lookup_failed", error=str(exc))

    conversation_context = {"incident_id": incident_id} | _extract_context_from_memories(memory_hits)
    if session_ctx and session_ctx.get("last_intent_type"):
        conversation_context["last_intent_type"] = session_ctx.get("last_intent_type")

    messages_for_graph = [
        {"role": item.get("role", "user"), "content": item.get("content", "")}
        for item in history_payload
        if isinstance(item, dict)
    ]
    pending_rescue = False
    if session_ctx and session_ctx.get("last_intent_type") == "rescue-task-generate":
        for entry in reversed(history_payload):
            if isinstance(entry, dict) and entry.get("role") == "assistant":
                content = str(entry.get("content") or "")
                if any(keyword in content for keyword in ("救援任务", "情况概述", "任务坐标", "补充缺失")):
                    pending_rescue = True
                break
    if pending_rescue:
        messages_for_graph.append(
            {
                "role": "system",
                "content": "系统提示：当前正在补充救援任务相关信息，请继续按照救援任务意图解析用户输入。",
            }
        )
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

    initial_state: Dict[str, Any] = {
        "thread_id": thread_id,
        "user_id": user_id,
        "channel": channel,
        "raw_text": cleaned_message,
        "metadata": metadata_dict,
        "incident_id": incident_id,
        "messages": messages_for_graph,
        "memory_hits": memory_hits,
        "conversation_context": conversation_context,
        "history": messages_for_graph # Pass history to pipeline
    }

    # 在进入统一意图管线前，拦截机器狗侦察/识别类对话，改走新的对话业务逻辑
    if channel == "voice" and _is_robotdog_talk_message(cleaned_message):
        logger.info(
            "robotdog_talk_reroute",
            thread_id=thread_id,
            user_id=user_id,
            text_preview=cleaned_message[:50],
        )

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

        return await _handle_robotdog_talk(
            user_message=cleaned_message,
            thread_id=thread_id,
            user_id=user_id,
            persist_message=_persist_assistant_message,
            history_records=history_records,
            build_history=build_history,
            stream_sink=stream_sink,
        )

    # 添加精确的计时日志
    start_time = time.perf_counter()
    # logger.warning(
    #     "langgraph_ainvoke_starting",
    #     thread_id=thread_id,
    #     initial_state_keys=list(initial_state.keys()),
    #     start_time=start_time,
    # )

    # 性能优化：根据消息内容判断是否需要checkpoint
    # 只有复杂的救援和侦察任务需要checkpoint，简单查询不需要
    # needs_checkpoint = (
    #     "救援" in cleaned_message or "rescue" in cleaned_message.lower() or
    #     "侦察" in cleaned_message or "scout" in cleaned_message.lower() or
    #     "任务" in cleaned_message or "task" in cleaned_message.lower()
    # )

    graph_state: Dict[str, Any] = {}
    try:
        # REFACTORED: Use IntentPipeline instead of Graph
        pipeline_result = await intent_pipeline.process(cleaned_message, context=initial_state)
        
        # Map pipeline result to expected state format
        graph_state = pipeline_result.get("state") or {}
        
        # Backfill critical fields if missing
        if "intent" not in graph_state:
            graph_state["intent"] = pipeline_result.get("intent")
        if "router_next" not in graph_state:
            graph_state["router_next"] = pipeline_result.get("router_next")
        if "validation_status" not in graph_state:
             status = pipeline_result.get("status")
             graph_state["validation_status"] = "valid" if status == "complete" else "invalid"
        
        # Inject audit log placeholder
        if "audit_log" not in graph_state:
            graph_state["audit_log"] = []

    finally:
        end_time = time.perf_counter()
        elapsed_ms = int((end_time - start_time) * 1000)
        # logger.warning(
        #     "langgraph_ainvoke_completed",
        #     thread_id=thread_id,
        #     elapsed_ms=elapsed_ms,
        #     elapsed_seconds=f"{end_time - start_time:.2f}",
        # )

    intent = graph_state.get("intent") or {}
    validation_status = graph_state.get("validation_status", "valid")
    router_next = graph_state.get("router_next", "unknown")
    prompt_text = graph_state.get("prompt")

    # 预处理：机器狗前方侦察类指令 → 固定视频分析链路
    try:
        itype_raw0 = str((intent.get("intent_type") or "").strip()).lower()
        itype_norm0 = itype_raw0.replace(" ", "").replace("_", "-")
        text_lower = cleaned_message.lower()
        is_robotdog_phrase = ("机器狗" in cleaned_message) or ("robotdog" in text_lower)
        is_forward_scout = ("前方" in cleaned_message and ("侦察" in cleaned_message or "识别" in cleaned_message))

        if itype_norm0 in ("video-analysis", "video-analyze") and (is_robotdog_phrase or is_forward_scout):
            raw_slots: Dict[str, Any] = dict(intent.get("slots") or {})

            device_name = raw_slots.get("device_name") or "侦察巡逻机器狗"
            device_type = raw_slots.get("device_type") or "robotdog"
            analysis_goal = raw_slots.get("analysis_goal")
            if not analysis_goal:
                if "识别" in cleaned_message:
                    analysis_goal = "识别前方目标"
                elif "侦察" in cleaned_message:
                    analysis_goal = "侦察前方目标"
                else:
                    analysis_goal = "识别前方目标"

            # 仅保留 VideoAnalysisSlots 支持的字段，避免多余字段导致槽位构造失败
            new_slots: Dict[str, Any] = {
                "device_name": device_name,
                "device_type": device_type,
                "analysis_goal": analysis_goal,
            }
            if "analysis_params" in raw_slots and isinstance(raw_slots["analysis_params"], dict):
                new_slots["analysis_params"] = raw_slots["analysis_params"]

            intent = dict(intent or {})
            intent["slots"] = new_slots
            graph_state["intent"] = intent
            validation_status = "valid"
            graph_state["validation_status"] = "valid"
            router_next = "video-analysis"
    except Exception as exc:  # noqa: BLE001
        logger.warning("robotdog_video_autofill_failed", error=str(exc))

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

            ctx: SessionContextRecord | None = session_ctx
            if ctx is None and context_service is not None:
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
                    ctx2 = session_ctx
                    if ctx2 is None and context_service is not None:
                        try:
                            ctx2 = await context_service.get(thread_id)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("session_context_lookup_failed", error=str(exc))
                    if ctx2 and ctx2.get("last_device_name"):
                        recent_label = str(ctx2["last_device_name"])  # type: ignore[index]
                        last_id2 = ctx2.get("last_device_id")
                        recent_value = str(last_id2) if isinstance(last_id2, str) else None
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

            if context_service is not None:
                try:
                    intent_marker = intent.get("intent_type")
                    intent_to_store = str(intent_marker).strip() if isinstance(intent_marker, str) else None
                    await context_service.set_last_intent(
                        thread_id=thread_id,
                        intent_type=intent_to_store or None,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("session_context_intent_save_failed", error=str(exc))

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
        # 处理“哪几台/哪两台”指代上一任务的追问，避免掉入闲聊
        try:
            if _is_task_assignee_followup(cleaned_message):
                last_task_id = _extract_latest_task_id_from_history(history_records)
                if last_task_id:
                    router_next = "system-data-query"
                    canonical = router_next
                    intent = {
                        "intent_type": router_next,
                        "canonical_intent_type": canonical,
                        "slots": {
                            "query_type": "task_assignees",
                            "query_params": {"task_id": last_task_id},
                        },
                    }
                    logger.info(
                        "intent_auto_reroute_task_assignees",
                        task_id=last_task_id,
                        thread_id=thread_id,
                        user_id=user_id,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("intent_auto_reroute_failed", error=str(exc))

    if router_next in {"unknown", "error"}:
        logger.info(
            "intent_process_result_unknown",
            intent_type=intent.get("intent_type"),
            router_next=router_next,
            thread_id=thread_id,
        )
        return await _handle_dialogue_fallback(
            message=cleaned_message,
            intent=intent,
            thread_id=thread_id,
            user_id=user_id,
            persist_message=_persist_assistant_message,
            history_records=history_records,
            build_history=build_history,
            memory_hits=memory_hits,
            audit_log=graph_state.get("audit_log") or [],
            dialogue_graph=dialogue_graph,
        )

    slots_payload = intent.get("slots") or {}

    if router_next == "device_control_robotdog":
        logger.info(
            "intent_dispatch_ready",
            router_next=router_next,
            handler="RobotDogControlHandler",
            graph="VoiceControlGraph",
            graph_mode="robotdog",
            thread_id=thread_id,
            user_id=user_id,
            channel=channel,
        )
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

    graph_name: Optional[str] = None
    graph_mode: Optional[str] = None
    if isinstance(handler, RescueSimulationHandler):
        graph_name = "RescueTacticalGraph"
        graph_mode = "simulation"
    elif isinstance(handler, RescueTaskGenerationHandler):
        graph_name = "RescueTacticalGraph"
        graph_mode = "live"
    elif isinstance(handler, RescueTeamDispatchHandler):
        graph_name = "RescueTeamDispatch"
    elif isinstance(handler, SimpleScoutDispatchHandler):
        graph_name = "SimpleScoutDispatch"
    elif isinstance(handler, RobotDogControlHandler):
        graph_name = "VoiceControlGraph"
        graph_mode = "robotdog"
    elif isinstance(handler, DeviceControlHandler):
        graph_name = "DeviceControlPipeline"
    elif isinstance(handler, VideoAnalysisHandler):
        graph_name = "VideoAnalysisService"
    elif isinstance(handler, TaskProgressQueryHandler):
        graph_name = "TaskProgressQuery"
    elif isinstance(handler, DeviceStatusQueryHandler):
        graph_name = "DeviceStatusQuery"
    elif isinstance(handler, SystemDataQueryHandler):
        graph_name = "SystemDataQuery"
    elif isinstance(handler, DisasterOverviewHandler):
        graph_name = "DisasterOverview"

    raw_text_for_handler = str(graph_state.get("raw_text") or cleaned_message)
    # 将LangGraph传回的消息转换成字典列表，保证各Handler拿到稳定结构
    messages_from_graph = graph_state.get("messages")
    normalized_messages: list[dict[str, str]] = []
    if isinstance(messages_from_graph, list):
        normalized_messages = [
            {
                "role": str(item.get("role", "user")),
                "content": str(item.get("content", "")),
            }
            for item in messages_from_graph
            if isinstance(item, dict)
        ]
    else:
        normalized_messages = [
            {
                "role": str(item.get("role", "user")),
                "content": str(item.get("content", "")),
            }
            for item in messages_for_graph
            if isinstance(item, dict)
        ]

    logger.info(
        "intent_dispatch_ready",
        router_next=router_next,
        handler=handler.__class__.__name__,
        graph=graph_name,
        graph_mode=graph_mode,
        thread_id=thread_id,
        user_id=user_id,
        channel=channel,
        raw_text_length=len(raw_text_for_handler),  # 记录传递给Handler的文本长度，方便排查空prompt
        message_count=len(normalized_messages),  # 记录上下文数量，确保消息链路完整
    )

    handler_state: Dict[str, Any] = {
        "user_id": user_id,
        "thread_id": thread_id,
        "incident_id": incident_id,
        "conversation_context": conversation_context,
        "memory_hits": memory_hits,
        "metadata": metadata_dict,
        "raw_text": raw_text_for_handler,  # 让Handler拿到最新用户输入
        "messages": normalized_messages,  # 让Handler复用最近会话上下文
    }
    if stream_sink is not None:
        handler_state["stream_sink"] = stream_sink

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

    # 性能优化：对于设备查询类意图，跳过记忆添加
    intent_type_raw = intent.get("intent_type")
    skip_mem_for_device = intent_type_raw in {"device-status-query", "device_status_query", "system-data-query"}

    if not skip_mem_for_device:
        try:
            intent_type_encoded = _encode_intent_for_mem0(intent_type_raw)
            mem.add(
                content=f"意图: {intent_type_raw}, 槽位: {json.dumps(slots_payload, ensure_ascii=False)}",
                user_id=user_id,
                run_id=thread_id,
                metadata={
                    "incident_id": incident_id,
                    "intent_type": intent_type_encoded,
                    "intent_type_raw": intent_type_raw,
                },
            )
            mem0_metrics.inc_add_success()
        except Exception as exc:  # noqa: BLE001
            mem0_metrics.inc_add_failure(exc.__class__.__name__)
            raise
    else:
        logger.info(
            "mem0_add_skipped_for_device_query",
            thread_id=thread_id,
            intent_type=intent_type_raw,
        )

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
