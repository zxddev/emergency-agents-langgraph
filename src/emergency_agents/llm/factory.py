from __future__ import annotations

import threading
from typing import Dict, Iterable, Optional

import structlog
from emergency_agents.config import AppConfig
from emergency_agents.llm.client import FailoverAsyncLLMClient, FailoverLLMClient
from emergency_agents.llm.endpoint_manager import LLMEndpointConfig, LLMEndpointManager


class LLMClientFactory:
    """根据子图/业务作用域提供独立的 LLM 客户端。"""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._manager_cache: Dict[str, LLMEndpointManager] = {}
        self._sync_cache: Dict[str, FailoverLLMClient] = {}
        self._async_cache: Dict[str, FailoverAsyncLLMClient] = {}
        self._lock = threading.Lock()
        self._logger = structlog.get_logger(__name__)

    def get_sync(self, scope: str | None = None) -> FailoverLLMClient:
        key = scope or "default"
        with self._lock:
            cached = self._sync_cache.get(key)
            if cached is not None:
                return cached
            manager = self._ensure_manager(key)
            client = FailoverLLMClient(manager)
            self._sync_cache[key] = client
            return client

    def get_async(self, scope: str | None = None) -> FailoverAsyncLLMClient:
        key = scope or "default"
        with self._lock:
            cached = self._async_cache.get(key)
            if cached is not None:
                return cached
            manager = self._ensure_manager(key)
            client = FailoverAsyncLLMClient(manager)
            self._async_cache[key] = client
            return client

    def _ensure_manager(self, scope: str) -> LLMEndpointManager:
        manager = self._manager_cache.get(scope)
        if manager is not None:
            return manager
        endpoints = self._resolve_endpoints(scope)
        endpoint_list = list(endpoints)
        manager = LLMEndpointManager.from_endpoints(
            endpoints,
            failure_threshold=self._config.llm_failure_threshold,
            recovery_seconds=self._config.llm_recovery_seconds,
            max_concurrency=self._config.llm_max_concurrency,
            request_timeout=self._config.llm_request_timeout_seconds,
        )
        self._manager_cache[scope] = manager
        self._logger.info(
            "llm_scope_manager_initialized",
            scope=scope,
            endpoints=[endpoint.name for endpoint in endpoint_list],
            max_concurrency=self._config.llm_max_concurrency,
            request_timeout_seconds=self._config.llm_request_timeout_seconds,
        )
        return manager

    def _resolve_endpoints(self, scope: str) -> Iterable[LLMEndpointConfig]:
        groups = self._config.llm_endpoint_groups
        if scope in groups and groups[scope]:
            return groups[scope]
        if "default" in groups and groups["default"]:
            return groups["default"]
        return self._config.llm_endpoints
