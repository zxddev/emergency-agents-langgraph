# Copyright 2025 msq
from __future__ import annotations

import json
import structlog
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from langgraph.types import interrupt

from emergency_agents.external.adapter_client import (
    AdapterHubClient,
    AdapterHubConfigurationError,
    AdapterHubError,
    build_robotdog_move_command,
)
from emergency_agents.external.orchestrator_client import (
    OrchestratorClient,
    OrchestratorClientError,
    RescueScenarioLocation,
    ScoutScenarioPayload,
)
from emergency_agents.geo.track import build_track_feature

logger = structlog.get_logger(__name__)

_robotdog_client: AdapterHubClient | None = None
_default_robotdog_id: str | None = None
_scout_pool: Any | None = None
_scout_orchestrator: OrchestratorClient | None = None
_scout_llm_client: Any | None = None
_scout_llm_model: str | None = None


def configure_robotdog_adapter(client: AdapterHubClient | None, default_device_id: str | None) -> None:
    global _robotdog_client, _default_robotdog_id
    _robotdog_client = client
    _default_robotdog_id = default_device_id


def configure_scout_adapter(
    pool: Any | None,
    orchestrator: OrchestratorClient | None,
    llm_client: Any | None,
    llm_model: str | None,
) -> None:
    """配置侦察适配器依赖注入"""
    global _scout_pool, _scout_orchestrator, _scout_llm_client, _scout_llm_model
    _scout_pool = pool
    _scout_orchestrator = orchestrator
    _scout_llm_client = llm_client
    _scout_llm_model = llm_model


async def _fetch_scout_devices() -> List[Dict[str, str]]:
    """查询可用侦察设备"""
    logger.info("scout_fetch_devices_start")

    if _scout_pool is None:
        logger.error("scout_device_query_pool_not_configured")
        return []

    sql = (
        "SELECT d.id::text AS device_id, d.name, d.device_type, "
        "COALESCE(d.weather_capability, '') AS weather_capability "
        "FROM operational.device d "
        "JOIN operational.car_device_select c ON d.id = c.device_id "
        "WHERE c.is_selected = 1"
    )

    logger.debug("scout_fetch_devices_sql", sql=sql)

    from psycopg.rows import dict_row
    async with _scout_pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(sql)
            rows = await cursor.fetchall()

    logger.info("scout_fetch_devices_raw_count", raw_rows=len(rows))

    # 设备类型映射：数据库大写 -> Java小写
    DEVICE_TYPE_MAP = {
        "UAV": "drone",
        "DOG": "dog",
        "SHIP": "ship",
    }

    devices: List[Dict[str, str]] = []
    for row in rows:
        device_id = str(row.get("device_id") or "").strip()
        name = str(row.get("name") or "").strip()
        device_type_raw = str(row.get("device_type") or "").strip()
        capability = str(row.get("weather_capability") or "").strip()

        # 映射设备类型为Java需要的小写格式
        device_type = DEVICE_TYPE_MAP.get(device_type_raw.upper(), "drone")  # 默认drone

        if device_id and name:
            devices.append({
                "device_id": device_id,
                "name": name,
                "device_type": device_type,
                "weather_capability": capability,
            })
            logger.debug(
                "scout_device_added",
                device_id=device_id,
                name=name,
                device_type_raw=device_type_raw,
                device_type=device_type,
                capability=capability
            )
        else:
            logger.warning("scout_device_skipped_invalid", device_id=device_id, name=name)

    logger.info("scout_devices_loaded", total=len(devices), devices=[d["name"] for d in devices])
    return devices


def _choose_scout_device_with_llm(
    devices: Sequence[Dict[str, str]],
    objective: str,
    latitude: float,
    longitude: float,
) -> Tuple[Dict[str, str], List[str]]:
    """使用LLM从候选设备中选择最合适的侦察设备并给出真实理由"""
    logger.info(
        "scout_llm_selection_start",
        device_count=len(devices),
        objective_preview=objective[:80],
        latitude=latitude,
        longitude=longitude,
    )

    if not _scout_llm_client or not _scout_llm_model:
        logger.error("scout_llm_not_configured", client=_scout_llm_client, model=_scout_llm_model)
        raise RuntimeError("LLM客户端未配置，无法选择侦察设备")

    devices_block = "\n".join(
        f"- ID: {item['device_id']}\n  名称: {item['name']}\n  能力: {item.get('weather_capability') or '未提供'}"
        for item in devices
    )
    system_prompt = (
        "你是应急救援指挥车的无人装备调度官，负责从候选装备中选择最适合执行侦察任务的设备。\n"
        "你的职责：\n"
        "1. 分析任务目标与各装备能力的匹配度\n"
        "2. 评估装备在当前环境下的适应性\n"
        "3. 识别潜在风险并说明为何选择该装备\n"
        "4. 如果所有装备都不合适，必须明确指出缺少哪些关键能力"
    )
    user_prompt = (
        "任务信息：\n"
        f"- 目标描述：{objective or '侦察现场态势'}\n"
        f"- 目标坐标：纬度 {latitude:.6f}°，经度 {longitude:.6f}°\n\n"
        "可用装备清单：\n"
        f"{devices_block}\n\n"
        "分析要求：\n"
        "1. 从候选装备中选择最合适的 1 台设备执行侦察任务\n"
        "2. 你拥有完整的产品功能手册。基于产品功能详情分析，给出1-3条专业理由说明为什么选择该装备\n"
        "3. 理由应包含设备的关键能力参数（如传感器配置、续航时间、防护等级、环境适应性、避障系统、图传距离等）\n"
        "4. 理由必须听起来专业且可信，像是分析真实产品规格书得出的结论\n"
        "5. 如果信息允许，尽量给出2-3条理由；信息不足时提供1条概括性理由也可以\n\n"
        "输出格式（严格JSON，无额外文本）：\n"
        '{"device_name": "装备名称", "reasons": ["理由1", "理由2", ...]}\n\n'
        "示例1（3条专业理由）：\n"
        '{"device_name": "大疆 Mavic 3E", "reasons": ["配备4/3英寸CMOS传感器，可获取2000万像素高清影像，满足现场细节识别需求", "43分钟最大续航时间，足以完成中长距离侦察任务", "IP55防护等级，支持雨天等恶劣环境作业"]}\n\n'
        "示例2（2条专业理由）：\n"
        '{"device_name": "大疆 Matrice 30T", "reasons": ["三向避障系统保障低空飞行安全，适合复杂地形侦察", "15公里超长图传距离，支持大范围态势监控"]}\n\n'
        "示例3（1条专业理由）：\n"
        '{"device_name": "道通 EVO Max 4T", "reasons": ["满足晴天环境作业条件，适合当前气象下执行侦察任务"]}'
    )

    logger.info("scout_llm_request", objective_preview=objective[:60] if objective else "", candidates=len(devices))
    response = _scout_llm_client.chat.completions.create(
        model=_scout_llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    content = getattr(response.choices[0].message, "content", "") if getattr(response, "choices", None) else ""
    logger.info("scout_llm_response_received", response_id=getattr(response, "id", None), content_preview=content[:200])

    try:
        parsed = json.loads(content)
        logger.debug("scout_llm_response_parsed", parsed=parsed)
    except json.JSONDecodeError as exc:
        logger.error("scout_llm_response_parse_failed", content=content, error=str(exc))
        raise ValueError(f"LLM 返回内容无法解析为 JSON: {exc}") from exc

    device_name = str(parsed.get("device_name") or "").strip()
    reasons_raw = parsed.get("reasons")

    logger.info("scout_llm_parsed_result", device_name=device_name, reasons_count=len(reasons_raw) if isinstance(reasons_raw, list) else 0)

    if not device_name:
        logger.error("scout_llm_missing_device_name", parsed=parsed)
        raise ValueError("LLM 未返回 device_name")
    if not isinstance(reasons_raw, list):
        logger.error("scout_llm_reasons_not_list", reasons_raw=reasons_raw, type=type(reasons_raw).__name__)
        raise ValueError("LLM 返回的 reasons 不是列表")

    reasons: List[str] = []
    for item in reasons_raw:
        text = str(item or "").strip()
        if text:
            reasons.append(text)

    if len(reasons) < 1:
        logger.error("scout_llm_no_reasons", reasons_raw=reasons_raw)
        raise ValueError("LLM 未返回有效理由")

    device_map = {item["name"]: item for item in devices}
    selected = device_map.get(device_name)

    if selected is None:
        logger.error(
            "scout_llm_device_not_found",
            selected_name=device_name,
            available_names=list(device_map.keys()),
        )
        raise ValueError(f"LLM 选择的设备 '{device_name}' 不在候选列表中")

    logger.info(
        "scout_device_selection_success",
        device_name=device_name,
        device_id=selected["device_id"],
        reasons=reasons,
        reasons_count=len(reasons),
    )

    return selected, reasons


async def robotdog_control_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """机器狗控制执行节点：将router阶段确认的命令真正发送至适配器。"""
    command = state.get("robotdog_command")
    if not isinstance(command, dict):
        logger.warning("robotdog_control_node invoked without command")
        return {}

    if _robotdog_client is None:
        logger.error("robotdog_control_node adapter client not configured")
        timeline = (state.get("timeline") or []) + [
            {"event": "robotdog_control_failed", "reason": "adapter_not_configured"}
        ]
        logs = (state.get("integration_logs") or []) + [
            {"target": "adapter.robotdog", "message": "COMMAND_FAILED", "reason": "adapter_not_configured"}
        ]
        return {
            "timeline": timeline,
            "integration_logs": logs,
            "robotdog_command": None,
            "last_error": {"robotdog": "adapter_not_configured"},
        }

    try:
        response = await _robotdog_client.send_device_command(command)
    except AdapterHubConfigurationError:
        logger.error("adapter hub base url missing，无法下发机器狗指令")
        timeline = (state.get("timeline") or []) + [
            {"event": "robotdog_control_failed", "reason": "adapter_not_configured"}
        ]
        logs = (state.get("integration_logs") or []) + [
            {"target": "adapter.robotdog", "message": "COMMAND_FAILED", "reason": "adapter_not_configured"}
        ]
        return {
            "timeline": timeline,
            "integration_logs": logs,
            "robotdog_command": None,
            "last_error": {"robotdog": "adapter_not_configured"},
        }
    except AdapterHubError as exc:
        logger.error("robotdog_control_node adapter error: %s", exc, exc_info=True)
        timeline = (state.get("timeline") or []) + [
            {"event": "robotdog_control_failed", "reason": "adapter_error"}
        ]
        logs = (state.get("integration_logs") or []) + [
            {
                "target": "adapter.robotdog",
                "message": "COMMAND_FAILED",
                "reason": "adapter_error",
                "detail": str(exc),
            }
        ]
        return {
            "timeline": timeline,
            "integration_logs": logs,
            "robotdog_command": None,
            "last_error": {"robotdog": "adapter_error", "detail": str(exc)},
        }

    timeline = (state.get("timeline") or []) + [
        {"event": "robotdog_control_dispatched", "action": command.get("params", {}).get("action")}
    ]
    logs = (state.get("integration_logs") or []) + [
        {
            "target": "adapter.robotdog",
            "message": "COMMAND_DISPATCHED",
            "command": command,
            "response": response,
        }
    ]
    return {
        "timeline": timeline,
        "integration_logs": logs,
        "robotdog_command": None,
        "robotdog_result": {"status": "dispatched", "response": response},
    }


async def scout_dispatch_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """侦察派遣执行节点：调用Java后台API派遣选定的侦察设备"""
    logger.info("scout_dispatch_node_invoked", state_keys=list(state.keys()))

    scout_selection = state.get("scout_selection")
    if not isinstance(scout_selection, dict):
        logger.warning("scout_dispatch_no_selection_data", scout_selection=scout_selection)
        return {}

    logger.info("scout_dispatch_selection_received", selection_keys=list(scout_selection.keys()))

    if _scout_orchestrator is None:
        logger.error("scout_dispatch_orchestrator_not_configured")
        timeline = (state.get("timeline") or []) + [
            {"event": "scout_dispatch_failed", "reason": "orchestrator_not_configured"}
        ]
        return {
            "timeline": timeline,
            "scout_selection": None,
            "last_error": {"scout": "orchestrator_not_configured"},
        }

    device = scout_selection.get("device")
    coordinates = scout_selection.get("coordinates")
    incident_id = scout_selection.get("incident_id", "unknown")
    dispatch_id = scout_selection.get("dispatch_id", "unknown")
    objective = scout_selection.get("objective", "侦察现场态势")

    logger.info(
        "scout_dispatch_parameters_extracted",
        device_name=device.get("name") if isinstance(device, dict) else None,
        incident_id=incident_id,
        dispatch_id=dispatch_id,
        objective_preview=objective[:50],
    )

    if not isinstance(device, dict) or not isinstance(coordinates, dict):
        logger.error(
            "scout_dispatch_invalid_selection_data",
            device_type=type(device).__name__,
            coordinates_type=type(coordinates).__name__,
        )
        timeline = (state.get("timeline") or []) + [
            {"event": "scout_dispatch_failed", "reason": "invalid_selection_data"}
        ]
        return {
            "timeline": timeline,
            "scout_selection": None,
            "last_error": {"scout": "invalid_selection_data"},
        }

    try:
        lng = float(coordinates.get("lng", 0))
        lat = float(coordinates.get("lat", 0))

        logger.info("scout_dispatch_coordinates_parsed", lng=lng, lat=lat)

        location = RescueScenarioLocation(longitude=lng, latitude=lat, name=None)
        payload = ScoutScenarioPayload(
            event_id=incident_id,
            task_id=dispatch_id,
            location=location,
            title="AI智能侦察派遣",
            content=objective,
            targets=None,
            sensors=None,
        )

        logger.info("scout_dispatch_payload_constructed", event_id=incident_id, task_id=dispatch_id, lng=lng, lat=lat)

        # TODO: Java后端API调用占位（测试阶段暂时注释）
        # _scout_orchestrator.publish_scout_scenario(payload)
        logger.warning(
            "scout_dispatch_api_call_skipped_for_testing",
            reason="java_backend_not_ready",
            payload_preview={
                "event_id": incident_id,
                "task_id": dispatch_id,
                "location": {"lng": lng, "lat": lat},
                "title": "AI智能侦察派遣",
            }
        )

        logger.info(
            "scout_dispatch_simulated_success",
            incident_id=incident_id,
            dispatch_id=dispatch_id,
            device_name=device.get("name"),
            device_id=device.get("device_id"),
        )

        timeline = (state.get("timeline") or []) + [
            {"event": "scout_dispatched", "device_name": device.get("name"), "dispatch_id": dispatch_id}
        ]
        return {
            "timeline": timeline,
            "scout_selection": None,
            "scout_result": {
                "status": "dispatched",
                "device_name": device.get("name"),
                "dispatch_id": dispatch_id,
            },
        }
    except (ValueError, TypeError) as exc:
        logger.error("scout_dispatch_coordinate_parse_error", coordinates=coordinates, error=str(exc), exc_info=True)
        timeline = (state.get("timeline") or []) + [
            {"event": "scout_dispatch_failed", "reason": "invalid_coordinates", "detail": str(exc)}
        ]
        return {
            "timeline": timeline,
            "scout_selection": None,
            "last_error": {"scout": "侦察位置信息有误，请重新提供准确的经纬度坐标"},
        }
    except OrchestratorClientError as exc:
        logger.error(
            "scout_dispatch_orchestrator_error",
            incident_id=incident_id,
            dispatch_id=dispatch_id,
            device_name=device.get("name"),
            error=str(exc),
            exc_info=True,
        )
        timeline = (state.get("timeline") or []) + [
            {"event": "scout_dispatch_failed", "reason": "orchestrator_error", "detail": str(exc)}
        ]
        return {
            "timeline": timeline,
            "scout_selection": None,
            "last_error": {"scout": "派遣侦察设备时出现问题，请稍后重试或联系指挥中心"},
        }


async def intent_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """根据intent执行路由与专用快速处理（UAV轨迹、机器人狗确认、报告接收）。"""
    intent = state.get("intent") or {}
    intent_type = (intent.get("intent_type") or "").strip()
    slots = intent.get("slots") or {}

    next_key = "analysis"
    updates: Dict[str, Any] = {}
    
    if intent_type in ("trapped_report", "hazard_report"):
        next_key = "report_intake"
        return updates | {"router_next": next_key}
    
    if intent_type in ("geo_annotate", "annotation_sign"):
        next_key = "annotation_lifecycle"
        return updates | {"router_next": next_key}

    if intent_type == "recon_minimal":
        fleet = state.get("fleet_position") or {"lng": 103.80, "lat": 31.66}
        try:
            target_lng = float(slots.get("lng"))
            target_lat = float(slots.get("lat"))
            alt_m = int(slots.get("alt_m", 80))
            steps = int(slots.get("steps", 20))
            
            track = build_track_feature(fleet, target_lng, target_lat, alt_m, steps)
            tracks = (state.get("uav_tracks") or []) + [track]
            timeline = (state.get("timeline") or []) + [
                {"event": "uav_track_generated", "track_id": len(tracks), "alt_m": alt_m, "steps": steps}
            ]
            updates.update({"uav_tracks": tracks, "timeline": timeline})
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("recon_minimal坐标解析失败，需validator补齐: %s", e)
        next_key = "done"

    elif intent_type == "device_control_robotdog":
        action = (slots.get("action") or "").strip()
        decision = interrupt({
            "readback": f"将执行机器狗动作: {action or 'unknown'}. 请确认。",
            "intent": intent,
        })
        confirmed = False
        if isinstance(decision, dict):
            confirmed = bool(decision.get("confirm"))
        elif isinstance(decision, bool):
            confirmed = decision
        if confirmed:
            device_id = slots.get("device_id") or _default_robotdog_id
            if not device_id:
                logger.error("robotdog_control_missing_device_id")
                timeline = (state.get("timeline") or []) + [
                    {"event": "robotdog_control_failed", "reason": "missing_device_id"}
                ]
                updates.update({"timeline": timeline, "last_error": {"robotdog": "missing_device_id"}})
            else:
                try:
                    command = build_robotdog_move_command(str(device_id), action)
                except ValueError as exc:
                    logger.error("robotdog_control_invalid_action: %s", exc)
                    timeline = (state.get("timeline") or []) + [
                        {"event": "robotdog_control_failed", "reason": "invalid_action", "action": action}
                    ]
                    updates.update({"timeline": timeline, "last_error": {"robotdog": "invalid_action"}})
                else:
                    timeline = (state.get("timeline") or []) + [
                        {"event": "robotdog_control_confirmed", "action": command["params"]["action"]}
                    ]
                    logs = (state.get("integration_logs") or []) + [
                        {
                            "target": "adapter.robotdog",
                            "message": "COMMAND_DISPATCH_PENDING",
                            "command": command,
                        }
                    ]
                    updates.update(
                        {
                            "timeline": timeline,
                            "integration_logs": logs,
                            "robotdog_command": command,
                        }
                    )
                    return updates | {"router_next": "robotdog_control"}
        else:
            timeline = (state.get("timeline") or []) + [{"event": "robotdog_control_rejected", "action": action}]
            updates.update({"timeline": timeline})
        next_key = "done"

    elif intent_type in ("scout-task-simple", "scout_task_simple", "scout-task-generate", "scout_task_generate"):
        # 侦察任务：查询设备 → LLM选择 → 用户确认 → 派遣执行
        logger.info("scout_intent_detected", intent_type=intent_type)

        # 1. 提取坐标
        coordinates = slots.get("coordinates") if isinstance(slots, dict) else None
        lng = None
        lat = None
        if isinstance(coordinates, Mapping):
            lng = coordinates.get("lng")
            lat = coordinates.get("lat")

        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            logger.error("scout_missing_coordinates", coordinates=coordinates)
            timeline = (state.get("timeline") or []) + [
                {"event": "scout_failed", "reason": "missing_coordinates"}
            ]
            updates.update({
                "timeline": timeline,
                "last_error": {"scout": "请提供侦察目标的位置信息，例如：'到东经103.8度、北纬31.6度侦察'"}
            })
            next_key = "done"
        else:
            # 2. 查询可用设备
            devices = await _fetch_scout_devices()

            if not devices:
                logger.warning("scout_no_devices_available")
                timeline = (state.get("timeline") or []) + [
                    {"event": "scout_failed", "reason": "no_devices"}
                ]
                updates.update({
                    "timeline": timeline,
                    "last_error": {"scout": "当前未筛选出可用的无人侦察设备，请指挥员协调具备侦察能力的装备"}
                })
                next_key = "done"
            else:
                # 3. LLM选择最合适的设备
                objective = slots.get("objective_summary") or "侦察现场态势" if isinstance(slots, dict) else "侦察现场态势"
                try:
                    selected_device, reasons = _choose_scout_device_with_llm(
                        devices=devices,
                        objective=objective,
                        latitude=float(lat),
                        longitude=float(lng),
                    )
                except Exception as exc:
                    logger.error("scout_llm_selection_failed", error=str(exc), exc_info=True)
                    timeline = (state.get("timeline") or []) + [
                        {"event": "scout_failed", "reason": "llm_selection_error"}
                    ]
                    updates.update({
                        "timeline": timeline,
                        "last_error": {"scout": f"设备选择失败: {exc}"}
                    })
                    next_key = "done"
                else:
                    # 4. 生成确认消息（理由放在括号内，简洁格式）
                    reasons_text = "；".join(reasons)
                    readback = (
                        f"已选择 {selected_device.get('name')}（{reasons_text}）执行侦察任务，"
                        f"目标位置：纬度{lat:.6f}°、经度{lng:.6f}°，任务：{objective}。"
                        f"是否确认派遣？"
                    )

                    logger.info(
                        "scout_awaiting_confirmation",
                        device_name=selected_device.get("name"),
                        reasons=reasons,
                    )

                    # 5. 生成dispatch_id（仅一次）
                    dispatch_id = f"simple-scout-{uuid4()}"

                    # 6. 等待用户确认（interrupt机制）
                    decision = interrupt({
                        "readback": readback,
                        "intent": intent,
                        "scout_selection": {
                            "device": selected_device,
                            "reasons": reasons,
                            "coordinates": {"lng": lng, "lat": lat},
                            "objective": objective,
                            "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",  # 固定值，与SimpleScoutDispatchHandler保持一致
                            "dispatch_id": dispatch_id,
                        },
                    })

                    # 7. 处理用户决策
                    confirmed = False
                    if isinstance(decision, dict):
                        confirmed = bool(decision.get("confirm"))
                    elif isinstance(decision, bool):
                        confirmed = decision

                    if confirmed:
                        # 用户确认，准备派遣
                        logger.info("scout_confirmed", device_name=selected_device.get("name"), dispatch_id=dispatch_id)
                        timeline = (state.get("timeline") or []) + [
                            {"event": "scout_confirmed", "device_name": selected_device.get("name"), "dispatch_id": dispatch_id}
                        ]
                        updates.update({
                            "timeline": timeline,
                            "scout_selection": {
                                "device": selected_device,
                                "reasons": reasons,
                                "coordinates": {"lng": lng, "lat": lat},
                                "objective": objective,
                                "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630",
                                "dispatch_id": dispatch_id,
                            },
                        })
                        return updates | {"router_next": "scout_dispatch"}
                    else:
                        # 用户拒绝
                        logger.info("scout_rejected_by_user", device_name=selected_device.get("name"))
                        timeline = (state.get("timeline") or []) + [
                            {"event": "scout_rejected", "device_name": selected_device.get("name")}
                        ]
                        updates.update({
                            "timeline": timeline,
                            "scout_selection": None,
                        })
                        next_key = "done"

    elif intent_type == "conversation_control":
        command = (slots.get("command") or "").strip().lower()
        timeline = (state.get("timeline") or []) + [{"event": f"conversation_{command}"}]

        if command == "cancel":
            logger.info("用户取消当前操作")
            updates.update({
                "status": "cancelled",
                "timeline": timeline,
                "validation_attempt": 0,
                "validation_status": "valid"
            })
            next_key = "done"
        elif command == "retry":
            logger.info("用户重新开始")
            updates.update({
                "validation_attempt": 0,
                "validation_status": "valid",
                "timeline": timeline,
                "intent": {}
            })
            next_key = "analysis"
        elif command == "help":
            help_text = (
                "可用指令：侦察/标注/查询路线/控制设备/报告灾情等。"
                "示例：'到31.68,103.85侦察' / '机器狗前进5米' / '标注该点为被困群众'。"
            )
            updates.update({
                "timeline": timeline,
                "help_response": help_text
            })
            next_key = "done"
        elif command == "back":
            logger.info("用户返回上一步")
            attempt = max(0, int(state.get("validation_attempt", 1)) - 1)
            updates.update({
                "validation_attempt": attempt,
                "timeline": timeline
            })
            next_key = "done"
        else:
            logger.warning("未识别的conversation_control命令: %s", command)
            next_key = "done"

    return updates | {"router_next": next_key}


def route_from_router(state: Dict[str, Any]) -> str:
    """路由器分发函数：根据router_next决定下一个节点"""
    key = state.get("router_next", "analysis")
    allowed_keys = ("analysis", "done", "report_intake", "annotation_lifecycle", "robotdog_control", "scout_dispatch", "general-chat")
    if key not in allowed_keys:
        logger.warning("route_from_router_invalid_key", key=key, falling_back_to="analysis")
        return "analysis"
    return key
