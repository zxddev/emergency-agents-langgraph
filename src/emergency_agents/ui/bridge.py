from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Iterable, List

import httpx
import structlog

from emergency_agents.ui.actions import UIActionLike, serialize_actions


logger = structlog.get_logger(__name__)


class HttpUIBridge:
    """将 ui_actions 通过 Java 内部端点发布至 STOMP。

    默认基地址从环境变量 WEB_API_BASE_URL 读取，缺省为 http://localhost:28080/web-api。
    """

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self.base_url = base_url or os.getenv("WEB_API_BASE_URL", "http://localhost:28080/web-api")
        self.timeout = timeout
        self._client = httpx.Client(timeout=httpx.Timeout(connect=3.0, read=timeout, write=timeout, pool=5.0))

    def publish_ui_actions(self, actions: Iterable[UIActionLike], user_id: str = "commander") -> None:
        serialized = list(serialize_actions(actions))
        if not serialized:
            return
        url = f"{self.base_url.rstrip('/')}/internal/stomp/user/ui.control"
        for action in serialized:
            try:
                correlation_id = action.get("correlation_id") or str(uuid.uuid4())
                payload = {
                    "type": "ui",
                    "action": action.get("action"),
                    "payload": action.get("payload") or {},
                }
                for k in ("incident_id", "session_id", "correlation_id", "ts"):
                    v = action.get(k) if k in action else None
                    if k == "correlation_id":
                        v = v or correlation_id
                    if v is not None:
                        payload[k] = v
                body = {
                    "userId": user_id,
                    "payload": payload,
                    "correlation_id": payload.get("correlation_id"),
                    "incident_id": payload.get("incident_id"),
                    "session_id": payload.get("session_id"),
                    "ts": payload.get("ts"),
                }
                r = self._client.post(url, json=body)
                if r.status_code >= 300:
                    logger.warning("ui_bridge_publish_failed", status=r.status_code, text=r.text)
                else:
                    logger.info("ui_bridge_published", action=payload.get("action"), correlation_id=payload.get("correlation_id"))
            except Exception as e:
                logger.warning("ui_bridge_exception", error=str(e))
