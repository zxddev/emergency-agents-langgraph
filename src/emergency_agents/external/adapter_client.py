from __future__ import annotations

import logging
import re
from typing import Any, Mapping

import httpx

logger = logging.getLogger(__name__)


class AdapterHubError(RuntimeError):
    """Adapter Hub 客户端基础异常。"""


class AdapterHubConfigurationError(AdapterHubError):
    """缺少 Adapter Hub 访问配置。"""


class AdapterHubRequestError(AdapterHubError):
    """调用 Adapter Hub 时发生网络/HTTP 错误。"""


class AdapterHubResponseError(AdapterHubError):
    """Adapter Hub 返回业务错误或无法解析的响应。"""


class AdapterHubClient:
    """Adapter Hub HTTP 客户端封装。"""

    def __init__(
        self,
        base_url: str | None,
        timeout: float = 5.0,
        *,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._timeout = httpx.Timeout(timeout, connect=timeout)
        self._async_client = async_client

    async def _get_async_client(self) -> httpx.AsyncClient:
        if not self._base_url:
            raise AdapterHubConfigurationError("adapter hub base url not configured")
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                trust_env=False,
            )
        return self._async_client

    async def aclose(self) -> None:
        if self._async_client is not None:
            await self._async_client.aclose()

    async def send_device_command(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        client = await self._get_async_client()
        logger.info(
            "adapter_hub_request",
            extra={
                "payload": dict(command),
                "base_url": self._base_url,
                "path": "/api/v3/device-access/control",
            },
        )
        try:
            response = await client.post("/api/v3/device-access/control", json=command)
        except httpx.HTTPError as exc:
            raise AdapterHubRequestError(f"adapter hub request failed: {exc}") from exc
        logger.info(
            "adapter_hub_response",
            extra={
                "status_code": response.status_code,
                "text": response.text,
            },
        )
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: httpx.Response) -> Mapping[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise AdapterHubResponseError("adapter hub response is not valid JSON") from exc

        if response.status_code >= 400:
            raise AdapterHubResponseError(
                f"adapter hub responded with {response.status_code}: {data}"
            )

        if isinstance(data, dict):
            code = data.get("code")
            if code is not None and str(code) not in {"0", "200"}:
                raise AdapterHubResponseError(f"adapter hub business error: {data}")
        return data


_ROBOTDOG_ACTION_MAP: dict[str, str] = {
    "forward": "forward",
    "front": "forward",
    "向前": "forward",
    "前进": "forward",
    "back": "back",
    "backward": "back",
    "向后": "back",
    "后退": "back",
    "up": "up",
    "standup": "up",
    "起立": "up",
    "站立": "up",
    "down": "down",
    "sit": "down",
    "sitdown": "down",
    "趴下": "down",
    "坐下": "down",
    "turnleft": "turnLeft",
    "turn_left": "turnLeft",
    "左转": "turnLeft",
    "turnright": "turnRight",
    "turn_right": "turnRight",
    "右转": "turnRight",
    "stop": "stop",
    "停止": "stop",
    "急停": "forceStop",
    "forcestop": "forceStop",
}


def normalize_robotdog_action(action: str) -> str:
    """将自然语言动作映射为统一动作枚举。"""
    if not action:
        raise ValueError("action is empty")
    key = re.sub(r"[\s_\-]", "", action.strip().lower())
    normalized = _ROBOTDOG_ACTION_MAP.get(key)
    if not normalized:
        normalized = _ROBOTDOG_ACTION_MAP.get(action.strip())
    if not normalized:
        raise ValueError(f"unsupported robotdog action: {action}")
    return normalized


def build_robotdog_move_command(device_id: str, action: str, *, control_target: str = "main") -> dict[str, Any]:
    """构造鼎桥机器狗移动命令。"""
    # 控制目标固定主控通道，避免缺少字段导致适配器拒绝请求
    normalized_action = normalize_robotdog_action(action)
    if not device_id:
        raise ValueError("device id is required for robotdog command")
    if not control_target:
        raise ValueError("control target is required for robotdog command")
    return {
        "deviceId": str(device_id),
        "deviceVendor": "dqDog",
        "controlTarget": control_target,
        "commandType": "move",
        "params": {"action": normalized_action},
    }
