from __future__ import annotations

import atexit
from threading import Lock

import httpx

from emergency_agents.intent.providers.base import IntentProvider


class HttpIntentProvider(IntentProvider):
    """带 HTTP 客户端的意图提供者基类，负责托管连接资源。"""

    def __init__(self, source: str, base_url: str, timeout: float) -> None:
        super().__init__(source)
        sanitized = base_url.rstrip("/")
        if not sanitized:
            raise ValueError("HTTP意图服务的base_url不能为空")
        self._client: httpx.Client = httpx.Client(base_url=sanitized, timeout=timeout)
        self._lock = Lock()
        self._closed = False
        atexit.register(self.close)

    @property
    def client(self) -> httpx.Client:
        return self._client

    def close(self) -> None:
        """释放HTTP连接资源。"""
        with self._lock:
            if self._closed:
                return
            self._client.close()
            self._closed = True

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


__all__ = ["HttpIntentProvider"]
