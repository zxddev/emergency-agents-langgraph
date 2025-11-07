"""基于数据库的救援队伍智能调度处理器。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import structlog
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from emergency_agents.external.orchestrator_client import (
    OrchestratorClient,
    OrchestratorClientError,
    RescueDispatchPayload,
)
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import RescueTaskGenerationSlots


logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class TeamEquipmentRecord:
    """救援队伍持有的装备信息。"""

    equipment_id: str
    name: str
    category: str
    equipment_type: str
    specs: Optional[str]
    quantity: int


@dataclass(slots=True)
class RescueTeamRecord:
    """救援队伍基础资料及能力画像。"""

    team_id: str
    name: str
    team_type: str
    headcount: int
    specialization: Optional[str]
    region: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    capability_level: Optional[int]
    response_minutes: Optional[int]
    equipment: Sequence[TeamEquipmentRecord]


@dataclass(slots=True)
class TeamScore:
    """用于排序的评分结果。"""

    record: RescueTeamRecord
    score: float
    distance_km: Optional[float]
    eta_minutes: Optional[int]


class RescueTeamDispatchHandler(IntentHandler[RescueTaskGenerationSlots]):
    """救援任务调度处理器：评估队伍 → 选择最佳 → 通知 Java。"""

    def __init__(
        self,
        pool: AsyncConnectionPool[Any],
        orchestrator_client: OrchestratorClient,
    ) -> None:
        # 保存数据库连接池
        if pool is None:
            raise ValueError("pool 不能为空")
        # 保存 Java 协同编排客户端
        if orchestrator_client is None:
            raise ValueError("orchestrator_client 不能为空")
        self._pool = pool
        self._orchestrator = orchestrator_client

    async def handle(
        self,
        slots: RescueTaskGenerationSlots,
        state: Dict[str, object],
    ) -> Dict[str, object]:
        """主流程：拉取队伍→打分筛选→通知后端。"""

        logger.info("rescue_dispatch_invoked", slots=slots, state_keys=list(state.keys()))

        # 解析坐标，作为评分及距离计算依据
        coordinates = getattr(slots, "coordinates", None)
        if not isinstance(coordinates, Mapping):
            raise ValueError("缺少救援坐标信息，无法派遣队伍。")

        lng_raw = coordinates.get("lng")
        lat_raw = coordinates.get("lat")
        if not isinstance(lng_raw, (int, float)) or not isinstance(lat_raw, (int, float)):
            raise ValueError("救援坐标无效，需提供精确经纬度。")

        target_lng = float(lng_raw)
        target_lat = float(lat_raw)

        conversation_context = dict(state.get("conversation_context") or {})
        incident_id = str(conversation_context.get("incident_id") or "fef8469f-5f78-4dd4-8825-dbc915d1b630")
        disaster_type = getattr(slots, "disaster_type", None)

        mission_type_value = getattr(slots, "mission_type", None)
        summary_text = getattr(slots, "situation_summary", "") or ""
        if not mission_type_value:
            inferred_type = self._infer_mission_type(summary_text)
            if inferred_type:
                setattr(slots, "mission_type", inferred_type)
                mission_type_value = inferred_type
        mission_type = (mission_type_value or "rescue").strip() or "rescue"

        logger.info(
            "rescue_dispatch_context_ready",
            incident_id=incident_id,
            mission_type=mission_type,
            disaster_type=disaster_type,
            target_lng=target_lng,
            target_lat=target_lat,
        )

        # 查询所有可调度队伍及装备
        teams = await self._load_team_profiles(disaster_type)
        if not teams:
            logger.warning("rescue_dispatch_no_team_available", incident_id=incident_id)
            message = "当前未找到可用救援队伍，请联系指挥部手动调度。"
            return {
                "response_text": message,
                "dispatch_status": "no_team",
                "conversation_context": conversation_context,
            }

        # 依据距离/能力/装备综合打分
        scores = self._score_teams(
            teams=teams,
            target_lng=target_lng,
            target_lat=target_lat,
        )

        if not scores:
            logger.error("rescue_dispatch_scoring_failed", team_count=len(teams))
            raise RuntimeError("救援队伍评分失败，请稍后重试。")

        # 选择最高分队伍
        scores.sort(key=lambda item: item.score, reverse=True)
        best = scores[0]

        logger.info(
            "rescue_dispatch_best_team",
            team_id=best.record.team_id,
            team_name=best.record.name,
            score=best.score,
            distance_km=best.distance_km,
            eta_minutes=best.eta_minutes,
        )

        reasons = self._build_reasons(best)

        # 向 Java 通知派遣动作
        dispatch_id = await self._notify_backend(
            incident_id=incident_id,
            best_team=best,
            mission_type=mission_type,
            disaster_type=disaster_type,
            target_lng=target_lng,
            target_lat=target_lat,
            reasons=reasons,
        )

        response_text = (
            f"已派遣 {best.record.name} 执行救援任务，编号 {dispatch_id}。"
            f" 综合评分 {best.score:.2f}，预计 {best.eta_minutes or '—'} 分钟抵达。"
        )

        return {
            "response_text": response_text,
            "dispatch_id": dispatch_id,
            "dispatch_team": {
                "team_id": best.record.team_id,
                "team_name": best.record.name,
                "team_type": best.record.team_type,
                "distance_km": best.distance_km,
                "eta_minutes": best.eta_minutes,
                "capability_level": best.record.capability_level,
                "equipment": [
                    {
                        "equipment_id": equipment.equipment_id,
                        "name": equipment.name,
                        "category": equipment.category,
                        "type": equipment.equipment_type,
                        "specs": equipment.specs,
                        "quantity": equipment.quantity,
                    }
                    for equipment in best.record.equipment
                ],
            },
            "dispatch_reason": reasons,
            "conversation_context": conversation_context,
        }

    async def _load_team_profiles(self, disaster_type: Optional[str]) -> List[RescueTeamRecord]:
        """查询救援队伍、装备及能力信息。"""

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT id, name, type, headcount, specialization, region, lng, lat
                    FROM operational.rescue_teams_2025
                    WHERE available = TRUE
                    ORDER BY name
                    """
                )
                team_rows = await cursor.fetchall()

        teams: Dict[str, RescueTeamRecord] = {}
        for row in team_rows:
            team_id = str(row.get("id") or "").strip()
            if not team_id:
                continue
            teams[team_id] = RescueTeamRecord(
                team_id=team_id,
                name=str(row.get("name") or "未知救援队伍").strip(),
                team_type=str(row.get("type") or "unknown").strip(),
                headcount=int(row.get("headcount") or 0),
                specialization=self._safe_str(row.get("specialization")),
                region=self._safe_str(row.get("region")),
                longitude=self._safe_float(row.get("lng")),
                latitude=self._safe_float(row.get("lat")),
                capability_level=None,
                response_minutes=None,
                equipment=tuple(),
            )

        team_ids = list(teams.keys())
        if not team_ids:
            return []

        capabilities = await self._load_capabilities(team_ids, disaster_type)
        for team_id, capability in capabilities.items():
            team = teams.get(team_id)
            if team is None:
                continue
            team.capability_level = capability.get("capability_level")
            team.response_minutes = capability.get("response_time_minutes")

        equipment_map = await self._load_equipment(team_ids)
        for team_id, equipment_list in equipment_map.items():
            team = teams.get(team_id)
            if team is None:
                continue
            team.equipment = tuple(equipment_list)

        return list(teams.values())

    async def _load_capabilities(
        self,
        team_ids: Sequence[str],
        disaster_type: Optional[str],
    ) -> Dict[str, Dict[str, Optional[int]]]:
        """提取队伍响应能力，优先匹配灾害类型，其次取最高等级。"""

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                if disaster_type:
                    await cursor.execute(
                        """
                        SELECT team_id, capability_level, response_time_minutes
                        FROM operational.team_response_capability_2025
                        WHERE team_id = ANY(%s) AND disaster_type = %s
                        """,
                        (team_ids, disaster_type),
                    )
                    rows = await cursor.fetchall()
                else:
                    rows = []

        capability: Dict[str, Dict[str, Optional[int]]] = {}
        for row in rows:
            team_id = str(row.get("team_id") or "").strip()
            if not team_id:
                continue
            capability[team_id] = {
                "capability_level": self._safe_int(row.get("capability_level")),
                "response_time_minutes": self._safe_int(row.get("response_time_minutes")),
            }

        missing_ids = [team_id for team_id in team_ids if team_id not in capability]
        if not missing_ids:
            return capability

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT DISTINCT ON (team_id)
                        team_id, capability_level, response_time_minutes
                    FROM operational.team_response_capability_2025
                    WHERE team_id = ANY(%s)
                    ORDER BY team_id, capability_level DESC NULLS LAST
                    """,
                    (missing_ids,),
                )
                fallback_rows = await cursor.fetchall()

        for row in fallback_rows:
            team_id = str(row.get("team_id") or "").strip()
            if not team_id:
                continue
            capability[team_id] = {
                "capability_level": self._safe_int(row.get("capability_level")),
                "response_time_minutes": self._safe_int(row.get("response_time_minutes")),
            }

        return capability

    async def _load_equipment(
        self,
        team_ids: Sequence[str],
    ) -> Dict[str, List[TeamEquipmentRecord]]:
        """查询队伍装备清单。"""

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        te.team_id,
                        te.quantity,
                        eq.id AS equipment_id,
                        eq.name,
                        eq.category,
                        eq.type,
                        eq.specs
                    FROM operational.team_equipment_2025 AS te
                    JOIN operational.equipment_2025 AS eq ON eq.id = te.equipment_id
                    WHERE te.team_id = ANY(%s)
                    ORDER BY te.team_id, eq.category
                    """,
                    (team_ids,),
                )
                rows = await cursor.fetchall()

        equipment_map: Dict[str, List[TeamEquipmentRecord]] = {}
        for row in rows:
            team_id = str(row.get("team_id") or "").strip()
            if not team_id:
                continue
            record = TeamEquipmentRecord(
                equipment_id=str(row.get("equipment_id") or "").strip(),
                name=str(row.get("name") or "未知装备").strip(),
                category=str(row.get("category") or "未知类别").strip(),
                equipment_type=str(row.get("type") or "unknown").strip(),
                specs=self._safe_str(row.get("specs")),
                quantity=int(row.get("quantity") or 0),
            )
            equipment_map.setdefault(team_id, []).append(record)

        return equipment_map

    def _score_teams(
        self,
        *,
        teams: Sequence[RescueTeamRecord],
        target_lng: float,
        target_lat: float,
    ) -> List[TeamScore]:
        """根据距离、能力、响应时间、装备情况综合评分。"""

        max_equipment = max(
            (sum(item.quantity for item in team.equipment) for team in teams),
            default=0,
        )

        scores: List[TeamScore] = []
        for team in teams:
            distance_km = None
            if team.longitude is not None and team.latitude is not None:
                distance_km = self._haversine_km(
                    team.longitude,
                    team.latitude,
                    target_lng,
                    target_lat,
                )

            distance_component = self._calc_distance_component(distance_km)
            capability_component = self._calc_capability_component(team.capability_level)
            response_component = self._calc_response_component(team.response_minutes)

            equipment_total = sum(item.quantity for item in team.equipment)
            equipment_component = (
                (equipment_total / max_equipment)
                if max_equipment > 0
                else 0.0
            )

            score = (
                distance_component * 0.35
                + capability_component * 0.3
                + response_component * 0.2
                + equipment_component * 0.15
            )

            eta_minutes = self._estimate_eta(distance_km, team.response_minutes)

            scores.append(
                TeamScore(
                    record=team,
                    score=round(score, 4),
                    distance_km=distance_km,
                    eta_minutes=eta_minutes,
                )
            )

        return scores

    def _build_reasons(self, score: TeamScore) -> List[str]:
        """生成面向指挥员的调度理由。"""

        reasons: List[str] = []
        distance = score.distance_km
        if distance is not None:
            reasons.append(f"距离目标约 {distance:.1f} 公里，可快速抵达现场")
        if score.record.capability_level is not None:
            reasons.append(
                f"灾害响应能力等级 {score.record.capability_level} 级，具备对应专业处置经验"
            )
        if score.eta_minutes is not None:
            reasons.append(f"预计 {score.eta_minutes} 分钟内到场，满足黄金救援时间要求")
        if score.record.equipment:
            key_equipment = ", ".join(
                f"{item.name}×{item.quantity}"
                for item in score.record.equipment[:3]
            )
            reasons.append(f"随队携带核心装备：{key_equipment}")
        if not reasons:
            reasons.append("队伍基础信息完整，符合派遣标准")
        return reasons

    async def _notify_backend(
        self,
        *,
        incident_id: str,
        best_team: TeamScore,
        mission_type: str,
        disaster_type: Optional[str],
        target_lng: float,
        target_lat: float,
        reasons: Sequence[str],
    ) -> str:
        """调用 Java 接口创建救援模拟实体。"""

        payload = RescueDispatchPayload(
            event_id=incident_id,
            team_id=best_team.record.team_id,
            team_name=best_team.record.name,
            team_type=best_team.record.team_type,
            team_longitude=best_team.record.longitude,
            team_latitude=best_team.record.latitude,
            target_longitude=target_lng,
            target_latitude=target_lat,
            mission_type=mission_type,
            disaster_type=disaster_type,
            score=best_team.score,
            eta_minutes=best_team.eta_minutes,
            capability_level=best_team.record.capability_level,
            response_minutes=best_team.record.response_minutes,
            equipment=[
                {
                    "equipment_id": item.equipment_id,
                    "name": item.name,
                    "category": item.category,
                    "type": item.equipment_type,
                    "quantity": item.quantity,
                }
                for item in best_team.record.equipment
            ],
            reasons=list(reasons),
        )

        try:
            response = self._orchestrator.publish_rescue_dispatch(payload)
        except OrchestratorClientError as exc:
            logger.error(
                "rescue_dispatch_backend_failed",
                team_id=best_team.record.team_id,
                error=str(exc),
                exc_info=True,
            )
            raise

        dispatch_id = str(response.get("dispatchId") or response.get("taskId") or "")
        if not dispatch_id:
            logger.warning("rescue_dispatch_missing_dispatch_id", response=response)
            dispatch_id = best_team.record.team_id

        logger.info(
            "rescue_dispatch_backend_success",
            team_id=best_team.record.team_id,
            dispatch_id=dispatch_id,
        )
        return dispatch_id

    @staticmethod
    def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Haversine 公式计算两点距离。"""

        radius = 6371.0
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a_val = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c_val = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))
        return radius * c_val

    @staticmethod
    def _calc_distance_component(distance_km: Optional[float]) -> float:
        """距离越近得分越高，超过 60km 降至 0。"""

        if distance_km is None:
            return 0.3
        return max(0.0, 1.0 - min(distance_km / 60.0, 1.0))

    @staticmethod
    def _calc_capability_component(level: Optional[int]) -> float:
        """能力等级 1-5 线性映射。"""

        if level is None:
            return 0.4
        return max(0.0, min(level / 5.0, 1.0))

    @staticmethod
    def _calc_response_component(response_minutes: Optional[int]) -> float:
        """响应时间越短得分越高，超 120 分钟视为 0。"""

        if response_minutes is None:
            return 0.4
        return max(0.0, 1.0 - min(response_minutes / 120.0, 1.0))

    @staticmethod
    def _infer_mission_type(summary: str) -> Optional[str]:
        """根据描述关键词推断任务类型。"""

        normalized = summary.lower()
        keyword_map: Sequence[Tuple[str, Sequence[str]]] = (
            ("medical", ("医疗", "医护", "救护", "伤员", "医务", "triage")),
            ("engineering", ("破拆", "加固", "清障", "吊装", "工程", "排险")),
            ("logistics", ("物资", "补给", "后勤", "保障", "供给", "转运")),
            ("water_rescue", ("落水", "溺水", "救生", "水域", "洪水", "冲刷")),
            ("firefighting", ("火灾", "明火", "烟雾", "灭火")),
            ("rescue", ("救援", "救出", "被困", "搜救", "营救")),
        )

        for mission, keywords in keyword_map:
            for keyword in keywords:
                if keyword in summary or keyword in normalized:
                    return mission
        return None

    @staticmethod
    def _estimate_eta(
        distance_km: Optional[float],
        response_minutes: Optional[int],
    ) -> Optional[int]:
        """综合响应时间与距离估算到场时间。"""

        if response_minutes is not None and response_minutes > 0:
            return int(response_minutes)
        if distance_km is None:
            return None
        travel_minutes = distance_km / 60.0 * 60.0
        return int(travel_minutes)

    @staticmethod
    def _safe_str(value: Any) -> Optional[str]:
        """安全转换字符串。"""

        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """安全转换浮点数。"""

        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """安全转换整数。"""

        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None


__all__ = ["RescueTeamDispatchHandler"]
