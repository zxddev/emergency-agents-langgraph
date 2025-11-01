"""设备目录查询，自 PostgreSQL 加载设备名称与 ID 映射。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Protocol

import structlog
from psycopg import errors
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from emergency_agents.control.models import DeviceType


_logger = structlog.get_logger(__name__)


_DEVICE_TYPE_MAP: Dict[str, DeviceType] = {
    "robotic_dog": DeviceType.ROBOTDOG,
    "robotdog": DeviceType.ROBOTDOG,
    "dog": DeviceType.ROBOTDOG,
    "uav": DeviceType.UAV,
    "drone": DeviceType.UAV,
    "usv": DeviceType.USV,
    "boat": DeviceType.USV,
    "ship": DeviceType.USV,
    "ugv": DeviceType.UGV,
    "robot": DeviceType.UGV,
    "ground_robot": DeviceType.UGV,
}


@dataclass(frozen=True)
class DeviceEntry:
    """设备条目，用于名称匹配。"""

    device_id: str
    name: str
    device_type: Optional[DeviceType]
    vendor: Optional[str]

    @property
    def name_lower(self) -> str:
        return self.name.lower()


class DeviceDirectory(Protocol):
    """设备查找协议，供语音流水线依赖。"""

    def match(self, command_text: str, device_type: DeviceType) -> Optional[DeviceEntry]:
        """基于指令文本和设备类型匹配设备信息。"""


class PostgresDeviceDirectory:
    """使用 Postgres 查询设备名称及 ID."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        self._entries: list[DeviceEntry] = []
        self.refresh()

    def refresh(self) -> None:
        """刷新设备缓存。"""

        query = (
            "SELECT id::text AS id, name, "
            "COALESCE(device_type::text, '') AS device_type, "
            "COALESCE(vendor::text, '') AS vendor "
            "FROM operational.device "
            "WHERE deleted_at IS NULL"
        )
        fallback_query = (
            "SELECT id::text AS id, name, COALESCE(device_type::text, '') AS device_type "
            "FROM operational.device"
        )

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                try:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    vendor_available = True
                except errors.UndefinedColumn:
                    conn.rollback()
                    cursor.execute(fallback_query)
                    rows = cursor.fetchall()
                    vendor_available = False

        entries: list[DeviceEntry] = []
        for row in rows:
            device_id = str(row.get("id") or "").strip()
            name = str(row.get("name") or "").strip()
            if not device_id or not name:
                continue
            raw_type = str(row.get("device_type") or "").strip().lower()
            vendor: Optional[str]
            if vendor_available:
                raw_vendor = str(row.get("vendor") or "").strip()
                vendor = raw_vendor or None
            else:
                vendor = None
            mapped_type = _DEVICE_TYPE_MAP.get(raw_type)
            entries.append(
                DeviceEntry(
                    device_id=device_id,
                    name=name,
                    device_type=mapped_type,
                    vendor=vendor,
                )
            )

        entries.sort(key=lambda item: len(item.name_lower), reverse=True)
        self._entries = entries
        _logger.info("device_directory_refreshed", total=len(entries))

    def match(self, command_text: str, device_type: DeviceType) -> Optional[DeviceEntry]:
        """在指令文本中匹配设备名称，优先使用最长命中。"""

        lowered = command_text.lower()
        candidates = self._match_entries(lowered, device_type)
        if not candidates:
            self.refresh()
            candidates = self._match_entries(lowered, device_type)
        if not candidates:
            return None
        if len(candidates) > 1:
            _logger.warning(
                "device_name_ambiguous",
                device_type=device_type.value,
                names=[item.name for item in candidates],
                command_text=command_text,
            )
        return candidates[0]

    def _match_entries(self, lowered_text: str, device_type: DeviceType) -> list[DeviceEntry]:
        matches: list[DeviceEntry] = []
        compact_text = lowered_text.replace(" ", "")
        for entry in self._entries:
            if entry.device_type is not None and entry.device_type is not device_type:
                continue
            if entry.name_lower and entry.name_lower in lowered_text:
                matches.append(entry)
                continue
            normalized_name = entry.name_lower.replace(" ", "")
            if normalized_name and normalized_name in compact_text:
                matches.append(entry)
        return matches

    def list_entries(self) -> Iterable[DeviceEntry]:
        return tuple(self._entries)
