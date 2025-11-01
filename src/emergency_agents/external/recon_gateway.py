"""Postgres 侦察数据网关。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

try:
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - 测试环境兜底
    dict_row = None  # type: ignore[assignment]
try:
    from psycopg_pool import ConnectionPool
except ModuleNotFoundError:  # pragma: no cover - 测试环境兜底
    class ConnectionPool:  # type: ignore[override]
        """测试环境占位连接池。"""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("psycopg_pool 未安装，无法创建 Postgres 连接池")

from psycopg import errors


from emergency_agents.planner.recon_models import (
    GeoPoint,
    HazardSnapshot,
    ReconAgent,
    ReconDevice,
    ReconPlan,
    ReconTask,
    TaskPlanPayload,
)
from emergency_agents.planner.recon_pipeline import ReconDataGateway, ReconPipeline


_SEVERITY_MAP: Dict[int, str] = {
    1: "critical",
    2: "high",
    3: "medium",
    4: "low",
}


@dataclass(slots=True)
class ReconPlanDraft:
    """侦察方案草稿结构。"""

    summary: str
    plan_payload: Dict[str, Any]
    tasks_payload: List[TaskPlanPayload]


class PostgresReconGateway(ReconDataGateway):
    """Postgres 实现的侦察网关。"""

    def __init__(self, pool: ConnectionPool) -> None:
        if pool is None:
            raise ValueError("pool 不可为空")
        self._pool = pool

    def fetch_hazard_snapshot(self, event_id: str) -> HazardSnapshot:
        """查询最新主灾害情报生成快照。"""

        query = """
            SELECT hazard_type::text AS hazard_type,
                   alert_level,
                   coalesce(content, '') AS summary
            FROM operational.event_alerts
            WHERE event_id = %(event_id)s
              AND deleted_at IS NULL
            ORDER BY occurred_at DESC
            LIMIT 1
        """
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
                cursor.execute(query, {"event_id": event_id})
                row = cursor.fetchone()
            if row is None:
                fallback_query = """
                    SELECT type::text AS hazard_type,
                           priority AS alert_level,
                           coalesce(description, '') AS summary
                    FROM operational.events
                    WHERE id = %(event_id)s
                      AND deleted_at IS NULL
                    LIMIT 1
                """
                with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
                    cursor.execute(fallback_query, {"event_id": event_id})
                    row = cursor.fetchone()
            if row is None:
                raise LookupError(f"未找到事件 {event_id} 的灾情快照数据")
        record = _row_mapping(row, cursor)
        severity_code = int(record.get("alert_level") or 3)
        severity = _SEVERITY_MAP.get(severity_code, "medium")
        return HazardSnapshot(
            hazard_type=str(record.get("hazard_type") or "unknown"),
            severity=severity,  # type: ignore[arg-type]
            description=record.get("summary") or None,
        )

    def fetch_available_devices(self, event_id: str) -> List[ReconDevice]:
        """列出可调度设备及其定位。"""

        query = """
            SELECT DISTINCT d.id,
                            d.name,
                            d.device_type,
                            d.env_type,
                            d.model,
                            d.vendor,
                            d.is_recon,
                            tv.position,
                            tv.status,
                            tv.timestamp
            FROM operational.device AS d
            JOIN operational.car_device_select AS cds
              ON cds.device_id = d.id AND cds.is_selected = 1
            JOIN operational.car_supply_select AS css
              ON css.car_id = cds.car_id AND css.is_selected = 1
            LEFT JOIN operational.telemetry_virtual AS tv
              ON tv.device_id = d.id
            WHERE d.is_recon = TRUE
        """

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
                try:
                    cursor.execute(query)
                except errors.UndefinedColumn as exc:
                    raise RuntimeError("operational.device 缺少 is_recon 列，请执行数据库升级脚本") from exc
                rows = cursor.fetchall()
            records = [_row_mapping(row, cursor) for row in rows]
            device_ids = [str(record["id"]) for record in records]
            capabilities_map = _fetch_device_capabilities(conn, device_ids)
            occupied_ids = _fetch_occupied_device_ids(conn)

        devices: List[ReconDevice] = []
        for record in records:
            device_id = str(record["id"])
            if device_id in occupied_ids:
                continue
            category = _normalize_category(str(record.get("device_type") or "other"), record.get("env_type"))
            capabilities = capabilities_map.get(device_id)
            if not capabilities:
                capabilities = _default_capabilities(category)
            if not capabilities:
                raise ValueError(f"设备 {device_id} 缺少能力配置")
            status_blob = _safe_json(record.get("status"))
            available = bool(status_blob.get("isOnline", 1))
            endurance = _extract_endurance(status_blob)
            devices.append(
                ReconDevice(
                    device_id=device_id,
                    name=record.get("name"),
                    category=category,
                    environment=_normalize_environment(str(record.get("env_type") or "other")),
                    capabilities=capabilities,
                    endurance_minutes=endurance,
                    payloads=[],
                    location=_parse_position(record.get("position")),
                    available=available,
                )
            )
        return devices

    def fetch_available_agents(self, event_id: str) -> List[ReconAgent]:
        """列出可执行侦察的队伍。"""

        query = """
            SELECT rescuer_id,
                   name,
                   rescuer_type,
                   availability,
                   status,
                   skills,
                   ST_X(current_location::geometry) AS lon,
                   ST_Y(current_location::geometry) AS lat
            FROM operational.rescuers
            WHERE availability = true
              AND status = 'available'
        """
        agents: List[ReconAgent] = []
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
            for row in rows:
                record = _row_mapping(row, cursor)
                if record.get("lon") is None or record.get("lat") is None:
                    location = None
                else:
                    location = GeoPoint(lon=float(record["lon"]), lat=float(record["lat"]))
                skills = _convert_skill_array(record.get("skills"))
                agents.append(
                    ReconAgent(
                        unit_id=str(record["rescuer_id"]),
                        name=record.get("name"),
                        kind=_normalize_agent_kind(str(record.get("rescuer_type") or "other")),
                        capabilities=skills,
                        contact=None,
                        location=location,
                        available=bool(record.get("availability", True)),
                    )
                )
        return agents

    def fetch_blocked_routes(self, event_id: str) -> List[str]:
        """查询事件涉及的道路阻断标记。"""

        query = """
            SELECT properties->>'code' AS code
            FROM operational.entities
            WHERE type = 'road_blockage'
              AND (properties->>'eventId' = %(event_id)s OR properties->>'eventId' IS NULL)
              AND deleted_at IS NULL
        """
        blocked: List[str] = []
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
                cursor.execute(query, {"event_id": event_id})
                rows = cursor.fetchall()
            for row in rows:
                record = _row_mapping(row, cursor)
                code = record.get("code")
                if code:
                    blocked.append(str(code))
        return blocked

    def fetch_existing_recon_tasks(self, event_id: str) -> List[str]:
        """列出已存在的侦察任务编号。"""

        query = """
            SELECT code
            FROM operational.tasks
            WHERE event_id = %(event_id)s
              AND type = 'uav_recon'
              AND deleted_at IS NULL
        """
        existing: List[str] = []
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
                cursor.execute(query, {"event_id": event_id})
                rows = cursor.fetchall()
            for row in rows:
                record = _row_mapping(row, cursor)
                code = record.get("code")
                if code:
                    existing.append(str(code))
        return existing

    def prepare_plan_draft(
        self,
        *,
        event_id: str,
        command_text: str,
        plan: ReconPlan,
        pipeline: ReconPipeline,
    ) -> ReconPlanDraft:
        """生成可供外部系统落库的方案草稿。"""

        summary = _render_plan_summary(plan=plan, command_text=command_text)
        scheme_draft_id = str(uuid4())
        plan_payload = plan.model_dump(mode="json")
        tasks_payload: List[TaskPlanPayload] = [
            pipeline.build_task_payload(scheme_id=scheme_draft_id, task=task) for task in plan.tasks
        ]
        return ReconPlanDraft(summary=summary, plan_payload=plan_payload, tasks_payload=tasks_payload)


def _row_mapping(row: Any, cursor: Any) -> Dict[str, Any]:
    """把游标行转换为字典结构。"""

    if isinstance(row, dict):
        return row
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    columns = getattr(cursor, "description", None)
    if not columns:
        return {}
    names: List[str] = []
    for col in columns:
        name = getattr(col, "name", None)
        if name is None and isinstance(col, tuple) and col:
            name = col[0]
        names.append(str(name))
    return {names[idx]: value for idx, value in enumerate(row)}


def _parse_position(raw: Any) -> Optional[GeoPoint]:
    """把 telemetry 位置 JSON 转换为 GeoPoint。"""

    if raw is None:
        return None
    try:
        payload = raw if isinstance(raw, dict) else json.loads(raw)
        geo = payload.get("geoCoordinate") or {}
        lon = float(geo.get("longitude"))
        lat = float(geo.get("latitude"))
        return GeoPoint(lon=lon, lat=lat)
    except Exception:
        return None


def _default_capabilities(category: str) -> List[str]:
    """按类别给出默认能力标签。"""

    if category == "uav":
        return ["aerial_recon", "thermal_imaging", "gas_detection"]
    if category == "robot_dog":
        return ["close_inspection"]
    if category == "usv":
        return ["water_recon"]
    return []


def _normalize_category(raw: str, env_type: Optional[str]) -> str:
    """把设备类型映射至 ReconDevice 分类。"""

    lowered = raw.lower()
    if lowered in {"drone", "uav"}:
        return "uav"
    if lowered in {"dog", "robot", "robot_dog"}:
        return "robot_dog"
    if lowered in {"ship", "usv"}:
        return "usv"
    return "other"


def _normalize_environment(raw: Optional[str]) -> str:
    """归一化设备环境标签。"""

    if raw is None:
        return "other"
    lowered = raw.strip().lower()
    if lowered in {"air", "land", "sea", "mixed"}:
        return lowered
    return "other"


def _safe_json(raw: Any) -> Dict[str, Any]:
    """安全解析 JSON 字符串。"""

    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _extract_endurance(status_blob: Dict[str, Any]) -> Optional[int]:
    """从状态字段提取剩余续航。"""

    life = status_blob.get("batteryLife") or status_blob.get("endurance")
    if life is None:
        return None
    try:
        return int(life)
    except (TypeError, ValueError):
        return None


def _convert_skill_array(raw: Any) -> List[str]:
    """把数据库数组转换为字符串列表。"""

    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _normalize_agent_kind(raw: str) -> str:
    """映射救援人员类型到 ReconAgent kind。"""

    lowered = raw.lower()
    if "drone" in lowered:
        return "uav_team"
    if "dog" in lowered:
        return "robot_dog_team"
    if "rescue" in lowered:
        return "rescue_team"
    return "other"


def _fetch_device_capabilities(conn: Any, device_ids: List[str]) -> Dict[str, List[str]]:
    """读取设备能力映射。"""

    if not device_ids:
        return {}
    query = """
        SELECT device_id, capability
        FROM operational.device_capability
        WHERE device_id = ANY(%s)
    """
    try:
        with conn.cursor(row_factory=dict_row) if dict_row is not None else conn.cursor() as cursor:
            cursor.execute(query, (device_ids,))
            rows = cursor.fetchall()
    except errors.UndefinedTable as exc:
        raise RuntimeError("缺少表 operational.device_capability，请先创建设备能力配置") from exc

    capabilities: Dict[str, List[str]] = {}
    for row in rows:
        record = _row_mapping(row, cursor)
        device_id = str(record.get("device_id"))
        capability = str(record.get("capability"))
        if device_id and capability:
            capabilities.setdefault(device_id, []).append(capability)
    return capabilities


def _fetch_occupied_device_ids(conn: Any) -> Set[str]:
    """查询当前被侦察任务占用的设备。"""

    query = """
        SELECT DISTINCT elem #>> '{}' AS device_id
        FROM operational.tasks,
             jsonb_array_elements(plan_step->'recommended_devices') AS elem
        WHERE type = 'uav_recon'
          AND status IN ('pending', 'in_progress')
          AND plan_step ? 'recommended_devices'
    """
    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return {row[0] for row in rows if row and row[0]}


def _render_plan_summary(*, plan: ReconPlan, command_text: str) -> str:
    """构造写入 scheme.plan_data 的摘要文本。"""

    objective_lines = "\n".join(f"- {item}" for item in plan.objectives)
    task_lines = "\n".join(f"1.{idx+1} {task.title}: {task.objective}" for idx, task in enumerate(plan.tasks))
    return (
        f"指令：{command_text}\n"
        f"目标：\n{objective_lines}\n"
        f"任务：\n{task_lines}\n"
        f"约束：{', '.join(c.name for c in plan.constraints) or '无'}"
    )


def _select_task_type(task: ReconTask) -> str:
    """根据 ReconTask 推断任务类型枚举。"""

    phase = task.mission_phase.lower()
    if phase == "recon":
        return "uav_recon"
    if phase == "alert":
        return "set_perimeter"
    if phase == "rescue":
        return "rescue_target"
    if phase == "logistics":
        return "material_transport"
    return "uav_recon"


def _priority_to_int(priority: str) -> int:
    """把任务优先级映射为整数分值。"""

    mapping = {
        "critical": 90,
        "high": 70,
        "medium": 50,
        "low": 30,
    }
    return mapping.get(priority, 50)


def _compute_deadline(task: ReconTask) -> Optional[datetime]:
    """生成任务截止时间。"""

    if task.duration_minutes is None:
        return None
    return datetime.now(timezone.utc) + timedelta(minutes=int(task.duration_minutes))
