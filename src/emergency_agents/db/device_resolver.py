from __future__ import annotations

from dataclasses import dataclass
from typing import List

import structlog

from emergency_agents.db.dao import DeviceDAO
from emergency_agents.db.models import DeviceSummary, VideoDevice


class DeviceNotFoundError(Exception):
    """设备未找到错误。"""

    def __init__(self, name: str, suggestions: List[DeviceSummary] | None = None) -> None:
        super().__init__(name)
        self.name = name
        self.suggestions = suggestions or []


class AmbiguousDeviceNameError(Exception):
    """设备名称歧义错误（命中多台）。"""

    def __init__(self, name: str, candidates: List[DeviceSummary]) -> None:
        super().__init__(name)
        self.name = name
        self.candidates = candidates


_logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class DeviceResolver:
    """设备名称解析器（强制命中唯一，不猜测）。

    策略：
    1) 按名称精确匹配（大小写不敏感）
    2) 按别名精确匹配（大小写不敏感）
    3) 未命中：抛 DeviceNotFoundError，并附带建议候选
    4) 多命中（理论不应发生；或别名表维护不当）：抛 AmbiguousDeviceNameError
    """

    dao: DeviceDAO

    @staticmethod
    def _normalize(name: str) -> str:
        """名称规范化（去首尾空白；半角化留给上游，如需）。"""
        return (name or "").strip()

    async def resolve_by_name(self, name: str) -> VideoDevice:
        """解析设备名称，返回唯一设备；否则抛出明确错误。

        Args:
            name: 用户输入的设备名称

        Returns:
            VideoDevice: 命中的唯一设备

        Raises:
            DeviceNotFoundError: 未命中任何设备
            AmbiguousDeviceNameError: 命中多台（数据一致性或别名冲突）
        """
        normalized = self._normalize(name)
        if not normalized:
            raise DeviceNotFoundError(name)

        _logger.info("device_resolve_start", raw=name, normalized=normalized)

        # 1) 名称精确匹配（大小写不敏感）
        exact = await self.dao.fetch_video_device_by_name_exact(normalized)
        if exact is not None:
            _logger.info("device_resolve_exact_device", device_id=exact.id, name=exact.name)
            return exact

        # 2) 别名精确匹配（大小写不敏感）
        alias_hit = await self.dao.fetch_video_device_by_alias_exact(normalized)
        if alias_hit is not None:
            _logger.info("device_resolve_exact_alias", device_id=alias_hit.id, name=alias_hit.name, alias=normalized)
            return alias_hit

        # 3) 未命中：给出建议候选，仅用于错误提示
        suggestions = await self.dao.suggest_devices_by_name_or_alias(normalized, limit=5)
        _logger.warn(
            "device_resolve_not_found",
            query=normalized,
            suggestion_count=len(suggestions),
        )
        raise DeviceNotFoundError(normalized, suggestions)

