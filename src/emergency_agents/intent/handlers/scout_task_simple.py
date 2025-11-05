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

        conversation_context: Dict[str, Any] = dict(state.get("conversation_context") or {})
        incident_id = "fef8469f-5f78-4dd4-8825-dbc915d1b630"

        coordinates = getattr(slots, "coordinates", None)
        lng = None
        lat = None
        if isinstance(coordinates, Mapping):
            lng = coordinates.get("lng")
            lat = coordinates.get("lat")
        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            raise ValueError("缺少侦察目标坐标，无法派遣无人设备。")

        devices = await self._fetch_selected_devices()
        if not devices:
            message = "当前未筛选出可用的无人侦察设备，请指挥员协调具备侦察能力的装备。"
            logger.warning("simple_scout_no_device", incident_id=incident_id)
            return {
                "response_text": message,
                "dispatch_status": "missing_device",
                "required_capabilities": ["无人侦察装备"],
                "conversation_context": conversation_context,
            }

        target_description = getattr(slots, "objective_summary", "") or "侦察现场态势"
        selection = self._choose_device_with_llm(
            devices=devices,
            objective=target_description,
            latitude=float(lat),
            longitude=float(lng),
        )

        selected = selection[0]
        reasons = selection[1]
        dispatch_id = f"simple-scout-{uuid4()}"

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
            "simple_scout_dispatched",
            incident_id=incident_id,
            dispatch_id=dispatch_id,
            device_id=selected.device_id,
            reasons=reasons,
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
            "SELECT d.id::text AS device_id, d.name, COALESCE(d.weather_capability, '') AS weather_capability "
            "FROM operational.device d "
            "JOIN operational.car_device_select c ON d.id = c.device_id "
            "WHERE c.is_selected = 1"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()

        devices: List[ReconDeviceRecord] = []
        for row in rows:
            device_id = str(row.get("device_id") or "").strip()
            name = str(row.get("name") or "").strip()
            capability = str(row.get("weather_capability") or "").strip()
            if not device_id or not name:
                continue
            devices.append(
                ReconDeviceRecord(
                    device_id=device_id,
                    name=name,
                    weather_capability=capability,
                )
            )

        logger.info("simple_scout_devices_loaded", total=len(devices))
        return devices

    def _choose_device_with_llm(
        self,
        *,
        devices: Sequence[ReconDeviceRecord],
        objective: str,
        latitude: float,
        longitude: float,
    ) -> Tuple[ReconDeviceRecord, Tuple[str, str, str]]:
        devices_block = "\n".join(
            f"- ID: {item.device_id}\n  名称: {item.name}\n  能力: {item.weather_capability or '未提供'}"
            for item in devices
        )
        system_prompt = (
            "你是应急救援指挥车的无人装备调度官，需要从候选名单中挑选最适合的装备执行侦察任务。"
            "必须综合任务目标、场景以及设备能力，给出专业理由。"
        )
        user_prompt = (
            "任务信息：\n"
            f"- 目标描述：{objective or '待补充'}\n"
            f"- 目标坐标：lat={latitude:.6f}, lng={longitude:.6f}\n"
            "候选设备列表：\n"
            f"{devices_block}\n\n"
            "请从候选设备中精确挑选 1 台执行侦察任务，并输出 JSON，格式如下：\n"
            '{"device_id": "设备ID", "reasons": ["原因1", "原因2", "原因3"]}\n'
            "要求：\n"
            "1. reasons 必须严格包含 3 条理由，每条用专业语言描述能力/匹配度/风险控制。\n"
            "2. 不得虚构候选列表不存在的设备或能力；若能力为空，也要说明选择依据。\n"
            "3. 输出必须是合法 JSON，不要包含额外文本。"
        )

        logger.info("simple_scout_llm_request", objective_preview=objective[:60], candidates=len(devices))
        response = self._llm_client.chat.completions.create(  # type: ignore[call-arg]
            model=self._llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
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

        device_id = str(parsed.get("device_id") or "").strip()
        reasons_raw = parsed.get("reasons")
        if not device_id:
            raise ValueError("LLM 未返回 device_id")
        if not isinstance(reasons_raw, list):
            raise ValueError("LLM 返回的 reasons 不是列表")
        reasons: List[str] = []
        for item in reasons_raw[:3]:
            text = str(item or "").strip()
            if text:
                reasons.append(text)
        if len(reasons) < 3:
            raise ValueError("LLM 返回的理由不足 3 条")

        device_map = {item.device_id: item for item in devices}
        selected = device_map.get(device_id)
        if selected is None:
            raise ValueError(f"LLM 选择的设备 {device_id} 不在候选列表中")

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
        location = RescueScenarioLocation(
            longitude=lng,
            latitude=lat,
            name=getattr(slots, "location_name", None) or None,
        )
        payload = ScoutScenarioPayload(
            event_id=incident_id,
            task_id=dispatch_id,
            location=location,
            title="简化侦察调度",
            content=objective_summary,
            targets=None,
            sensors=None,
        )

        try:
            self._orchestrator.publish_scout_scenario(payload)
        except OrchestratorClientError:
            logger.error(
                "simple_scout_notify_failed",
                incident_id=incident_id,
                dispatch_id=dispatch_id,
                device_id=device.device_id,
            )
            raise


__all__ = ["SimpleScoutDispatchHandler"]
