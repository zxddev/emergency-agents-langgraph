"""简化侦察任务处理器：绕过完整LangGraph，直接调度无人设备。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple
from uuid import uuid4

import structlog
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from emergency_agents.external.orchestrator_client import (
    OrchestratorClient,
    OrchestratorClientError,
    RescueScenarioLocation,
    ScoutScenarioPayload,
)
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from emergency_agents.llm.client import LLMClientProtocol


logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ReconDeviceRecord:
    """待选无人设备。"""

    device_id: str
    name: str
    device_type: str  # dog/ship/drone (已映射为小写)
    env_type: str
    weather_capability: str


class SimpleScoutDispatchHandler(IntentHandler[ScoutTaskGenerationSlots]):
    """简化侦察任务处理器：查询设备 → LLM 选择 → 调度通知。"""

    def __init__(
        self,
        pool: AsyncConnectionPool[Any],
        orchestrator_client: OrchestratorClient,
        llm_client: LLMClientProtocol,
        llm_model: str,
    ) -> None:
        if pool is None:
            raise ValueError("pool 不能为空")
        if orchestrator_client is None:
            raise ValueError("orchestrator_client 不能为空")
        if llm_client is None:
            raise ValueError("llm_client 不能为空")
        if not llm_model:
            raise ValueError("llm_model 不能为空")
        self._pool = pool
        self._orchestrator = orchestrator_client
        self._llm_client = llm_client
        self._llm_model = llm_model

    async def handle(self, slots: ScoutTaskGenerationSlots, state: Dict[str, object]) -> Dict[str, object]:
        """调度具备侦察能力的设备，并记录调度原因。"""
        logger.info("scout_handler_invoked", slots=slots, state_keys=list(state.keys()))

        conversation_context: Dict[str, Any] = dict(state.get("conversation_context") or {})
        incident_id = "fef8469f-5f78-4dd4-8825-dbc915d1b630"

        # 提取坐标
        coordinates = getattr(slots, "coordinates", None)
        logger.info("scout_coordinates_extracted", coordinates=coordinates, type=type(coordinates).__name__)

        lng = None
        lat = None
        if isinstance(coordinates, Mapping):
            lng = coordinates.get("lng")
            lat = coordinates.get("lat")

        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            logger.error("scout_invalid_coordinates", lng=lng, lat=lat, lng_type=type(lng).__name__, lat_type=type(lat).__name__)
            raise ValueError("缺少侦察目标坐标，无法派遣无人设备。")

        logger.info("scout_coordinates_validated", lng=lng, lat=lat)

        devices = await self._fetch_selected_devices()
        logger.info("scout_devices_fetched", device_count=len(devices))

        if not devices:
            message = "当前未筛选出可用的无人侦察设备，请指挥员协调具备侦察能力的装备。"
            logger.warning("scout_no_device_available", incident_id=incident_id)
            return {
                "response_text": message,
                "dispatch_status": "missing_device",
                "required_capabilities": ["无人侦察装备"],
                "conversation_context": conversation_context,
            }

        target_description = getattr(slots, "objective_summary", "") or "侦察现场态势"
        logger.info("scout_llm_selection_start", device_count=len(devices), objective=target_description, lat=lat, lng=lng)

        selection = self._choose_device_with_llm(
            devices=devices,
            objective=target_description,
            latitude=float(lat),
            longitude=float(lng),
        )

        selected = selection[0]
        reasons = selection[1]
        dispatch_id = f"simple-scout-{uuid4()}"

        logger.info(
            "scout_device_selected",
            device_name=selected.name,
            device_id=selected.device_id,
            reasons=reasons,
            dispatch_id=dispatch_id,
        )

        await self._notify_backend(
            incident_id=incident_id,
            dispatch_id=dispatch_id,
            lng=float(lng),
            lat=float(lat),
            device=selected,
            objective_summary=target_description,
            slots=slots,
        )

        reasons_text = "；".join(f"{idx}. {text}" for idx, text in enumerate(reasons, start=1))
        response_text = (
            f"已派遣 {selected.name} 执行无人侦察，任务编号 {dispatch_id}。原因：（{reasons_text}）。"
        )

        logger.info(
            "scout_dispatched_success",
            incident_id=incident_id,
            dispatch_id=dispatch_id,
            device_id=selected.device_id,
            device_name=selected.name,
            response_preview=response_text[:100],
        )

        return {
            "response_text": response_text,
            "dispatch_id": dispatch_id,
            "dispatch_device": {
                "device_id": selected.device_id,
                "name": selected.name,
                "weather_capability": selected.weather_capability,
            },
            "dispatch_reason": reasons_text,
            "conversation_context": conversation_context,
            "llm_reasons": reasons,
        }

    async def _fetch_selected_devices(self) -> List[ReconDeviceRecord]:
        sql = (
            "SELECT d.id::text AS device_id, d.name, d.device_type, COALESCE(d.env_type, '') AS env_type, "
            "COALESCE(d.weather_capability, '') AS weather_capability "
            "FROM operational.device d "
            "JOIN operational.car_device_select c ON d.id = c.device_id "
            "WHERE c.is_selected = 1"
        )

        # 设备类型映射：数据库大写 -> Java小写
        DEVICE_TYPE_MAP = {
            "UAV": "drone",
            "DOG": "dog",
            "SHIP": "ship",
        }

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()

        devices: List[ReconDeviceRecord] = []
        for row in rows:
            device_id = str(row.get("device_id") or "").strip()
            name = str(row.get("name") or "").strip()
            device_type_raw = str(row.get("device_type") or "").strip()
            env_type = str(row.get("env_type") or "").strip()
            capability = str(row.get("weather_capability") or "").strip()

            # 映射设备类型为Java需要的小写格式
            default_type = device_type_raw.lower() if device_type_raw else ""
            device_type = DEVICE_TYPE_MAP.get(device_type_raw.upper(), default_type or "unknown")

            if not device_id or not name:
                continue
            devices.append(
                ReconDeviceRecord(
                    device_id=device_id,
                    name=name,
                    device_type=device_type,
                    env_type=env_type,
                    weather_capability=capability,
                )
            )

        logger.info("simple_scout_devices_loaded", total=len(devices))
        return devices

    @staticmethod
    def _label_device_type(device_type: str) -> str:
        mapping = {
            "drone": "空中无人机",
            "uav": "空中无人机",
            "ship": "水域无人艇",
            "usv": "水域无人艇",
            "dog": "地面机器狗",
            "robotic_dog": "地面机器狗",
        }
        normalized = (device_type or "").strip().lower()
        return mapping.get(normalized, device_type or "未知类型")

    @staticmethod
    def _label_env_type(env_type: str) -> str:
        mapping = {
            "air": "空域",
            "sea": "水域",
            "sea ": "水域",
            "land": "陆地",
        }
        normalized = (env_type or "").strip().lower()
        return mapping.get(normalized, env_type or "未知环境")

    def _choose_device_with_llm(
        self,
        *,
        devices: Sequence[ReconDeviceRecord],
        objective: str,
        latitude: float,
        longitude: float,
    ) -> Tuple[ReconDeviceRecord, Tuple[str, str, str]]:
        devices_block = "\n".join(
            f"- ID: {item.device_id}\n  名称: {item.name}\n  类型: {self._label_device_type(item.device_type)}（环境：{self._label_env_type(item.env_type)}）\n  能力: {item.weather_capability or '未提供'}"
            for item in devices
        )
        system_prompt = (
            "你是应急救援指挥车的无人装备调度官，负责从候选装备中选择最适合执行侦察任务的设备。\n"
            "你的职责：\n"
            "1. 分析任务目标与各装备能力的匹配度\n"
            "2. 评估装备在当前环境下的适应性\n"
            "3. 识别潜在风险并说明为何选择该装备\n"
            "4. 如果所有装备都不合适，必须明确指出缺少哪些关键能力\n"
            "优先级规则：\n"
            "- 默认优先调度空中无人机执行侦察任务。\n"
            "- 仅当任务描述明确指向水域/海域/湖泊等水上目标，或明确需要进入建筑物内部搜寻，或为化工厂/工业园等需要地面装备干预的场景时，才考虑选择水域无人艇或地面装备。\n"
            "- 一旦选择非无人机，必须在理由中引用任务描述里的关键词，说明为何无人机不适用。"
        )
        user_prompt = (
            "任务信息：\n"
            f"- 目标描述：{objective or '侦察现场态势'}\n"
            f"- 目标坐标：纬度 {latitude:.6f}°，经度 {longitude:.6f}°\n\n"
            "可用装备清单：\n"
            f"{devices_block}\n\n"
            "分析要求：\n"
            "1. 从候选装备中选择最合适的 1 台设备执行侦察任务\n"
            "2. 提供 3 条专业理由，说明为什么选择该装备（能力匹配/环境适应/风险控制）\n"
            "3. 理由必须具体，避免泛泛而谈（例如：具备夜视能力适合当前时段，而非仅说'能力强'）\n"
            "4. 严禁虚构装备或能力，仅基于上述清单分析，如能力未知需说明\n\n"
            "输出格式（严格JSON，无额外文本）：\n"
            '{"device_name": "装备名称", "reasons": ["理由1", "理由2", "理由3"]}\n\n'
            "示例：\n"
            '{"device_name": "四旋翼无人机-A01", "reasons": ["具备光学+红外双模传感器适合复杂环境侦察", "续航60分钟满足长时间监控需求", "抗风等级7级可应对当前气象条件"]}'
        )

        logger.info("simple_scout_llm_request", objective_preview=objective[:60], candidates=len(devices))
        response = self._llm_client.chat.completions.create(  # type: ignore[call-arg]
            model=self._llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = getattr(response.choices[0].message, "content", "") if getattr(response, "choices", None) else ""
        logger.info(
            "simple_scout_llm_response",
            response_id=getattr(response, "id", None),
            content_preview=content[:200],
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM 返回内容无法解析为 JSON: {exc}") from exc

        device_name = str(parsed.get("device_name") or "").strip()
        reasons_raw = parsed.get("reasons")
        if not device_name:
            raise ValueError("LLM 未返回 device_name")
        if not isinstance(reasons_raw, list):
            raise ValueError("LLM 返回的 reasons 不是列表")
        reasons: List[str] = []
        for item in reasons_raw[:3]:
            text = str(item or "").strip()
            if text:
                reasons.append(text)
        if len(reasons) < 3:
            raise ValueError("LLM 返回的理由不足 3 条")

        device_map = {item.name: item for item in devices}
        selected = device_map.get(device_name)
        if selected is None:
            raise ValueError(f"LLM 选择的设备 '{device_name}' 不在候选列表中")

        return selected, (reasons[0], reasons[1], reasons[2])

    async def _notify_backend(
        self,
        *,
        incident_id: str,
        dispatch_id: str,
        lng: float,
        lat: float,
        device: ReconDeviceRecord,
        objective_summary: str,
        slots: ScoutTaskGenerationSlots,
    ) -> None:
        """通知Java后台API派遣侦察设备"""
        logger.info(
            "scout_notify_backend_start",
            incident_id=incident_id,
            dispatch_id=dispatch_id,
            device_id=device.device_id,
            device_name=device.name,
            lng=lng,
            lat=lat,
        )

        # 构造简化版ScoutScenarioPayload（适配Java后端需求）
        payload = ScoutScenarioPayload(
            event_id=incident_id,
            device_id=device.device_id,
            device_type=device.device_type,
            end_lon=lng,
            end_lat=lat,
            title=f"侦察任务-{device.name}",
            content=objective_summary or "侦察现场态势",
        )

        logger.info(
            "scout_payload_constructed",
            event_id=incident_id,
            device_id=device.device_id,
            device_type=device.device_type,
            end_lon=lng,
            end_lat=lat,
            title=payload.title,
        )

        # 调用Java后端API派遣设备
        try:
            response = self._orchestrator.publish_scout_scenario(payload)
            logger.info(
                "scout_notify_backend_success",
                incident_id=incident_id,
                dispatch_id=dispatch_id,
                device_id=device.device_id,
                device_name=device.name,
                device_type=device.device_type,
                end_lon=lng,
                end_lat=lat,
                response=response,
            )
        except OrchestratorClientError as exc:
            logger.error(
                "scout_notify_backend_failed",
                incident_id=incident_id,
                dispatch_id=dispatch_id,
                device_id=device.device_id,
                device_name=device.name,
                device_type=device.device_type,
                error=str(exc),
                exc_info=True,
            )
            raise


__all__ = ["SimpleScoutDispatchHandler"]
