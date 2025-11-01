from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

import structlog
from openai import AsyncOpenAI, OpenAI

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from emergency_agents.config import AppConfig

T = TypeVar("T")

logger = structlog.get_logger(__name__)


class LLMEndpointsExhaustedError(RuntimeError):
    """所有端点不可用时抛出。"""

    def __init__(self, operation: str, states: Dict[str, Dict[str, object]]) -> None:
        message = f"LLM endpoints exhausted during {operation}"  # 构造提示
        super().__init__(message)  # 调用父类初始化
        self.operation = operation  # 记录操作名
        self.states = states  # 保存端点状态


@dataclass(frozen=True)
class LLMEndpointConfig:
    """LLM端点配置。

    Attributes:
        name: 端点名称（用于日志与监控）。
        base_url: 模型服务的Base URL。
        api_key: 调用该端点时使用的API Key。
        priority: 优先级，数值越大优先选用。
        weight: 当多个端点同优先级时的权重（预留扩展）。
    """

    name: str
    base_url: str
    api_key: str
    priority: int = 100
    weight: int = 1


@dataclass
class LLMEndpointState:
    """LLM端点运行状态。

    Attributes:
        available: 当前是否可用。
        consecutive_failures: 连续失败次数。
        consecutive_successes: 连续成功次数。
        half_open: 是否处于半开尝试阶段。
        recovery_at: 允许重新尝试的时间戳（秒）。
    """

    available: bool = True
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    half_open: bool = False
    recovery_at: float = 0.0


class LLMEndpointManager:
    """LLM端点管理器：负责主备切换、熔断与恢复。

    说明：
    - 通过状态机记录每个端点的成功/失败情况；
    - 当主端点失败达到阈值时短暂熔断，转而使用备用端点；
    - 到达恢复时间窗口后，会进入半开状态尝试恢复；
    - 同步 / 异步客户端均通过此管理器生成，确保选用相同策略。
    """

    def __init__(
        self,
        endpoints: List[LLMEndpointConfig],
        *,
        failure_threshold: int = 3,
        recovery_seconds: int = 60,
        sync_client_builder: Callable[[LLMEndpointConfig], OpenAI],
        async_client_builder: Callable[[LLMEndpointConfig], AsyncOpenAI],
        max_concurrency: int = 5,
        request_timeout: float = 60.0,
    ) -> None:
        if not endpoints:
            raise ValueError("至少需要一个LLM端点配置")

        # 按优先级排序，优先级越高越靠前
        self._order: List[LLMEndpointConfig] = sorted(
            endpoints, key=lambda e: e.priority, reverse=True
        )
        self._states: Dict[str, LLMEndpointState] = {
            endpoint.name: LLMEndpointState() for endpoint in self._order
        }
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_seconds = max(10, recovery_seconds)
        self._sync_builder = sync_client_builder
        self._async_builder = async_client_builder
        self._request_timeout = max(1.0, float(request_timeout))

        # 端点对应的客户端缓存，减少重复创建开销
        self._sync_clients: Dict[str, OpenAI] = {}
        self._async_clients: Dict[str, AsyncOpenAI] = {}

        # 线程锁保证多协程/线程同时访问时状态安全
        self._lock = threading.Lock()

        # 并发控制
        self._max_concurrency = max(1, int(max_concurrency))
        self._sync_semaphore = threading.Semaphore(self._max_concurrency)
        self._async_semaphore = asyncio.Semaphore(self._max_concurrency)

        logger.info(
            "llm_endpoint_manager_initialized",
            endpoints=[e.name for e in self._order],
            failure_threshold=self._failure_threshold,
            recovery_seconds=self._recovery_seconds,
            max_concurrency=self._max_concurrency,
            request_timeout_seconds=self._request_timeout,
        )

    @classmethod
    def from_config(cls, cfg: "AppConfig") -> "LLMEndpointManager":
        """基于AppConfig构建端点管理器。"""

        return cls.from_endpoints(
            cfg.llm_endpoints,
            failure_threshold=cfg.llm_failure_threshold,
            recovery_seconds=cfg.llm_recovery_seconds,
            max_concurrency=cfg.llm_max_concurrency,
            request_timeout=cfg.llm_request_timeout_seconds,
        )

    @classmethod
    def from_endpoints(
        cls,
        endpoints: Iterable[LLMEndpointConfig],
        *,
        failure_threshold: int,
        recovery_seconds: int,
        max_concurrency: int,
        request_timeout: float,
    ) -> "LLMEndpointManager":
        endpoint_list = list(endpoints)
        if not endpoint_list:
            raise ValueError("endpoints 不能为空")

        import httpx

        def build_sync(endpoint: LLMEndpointConfig) -> OpenAI:
            timeout = httpx.Timeout(connect=5.0, read=request_timeout, write=request_timeout, pool=request_timeout)
            http_client = httpx.Client(trust_env=False, timeout=timeout)
            return OpenAI(
                base_url=endpoint.base_url,
                api_key=endpoint.api_key,
                http_client=http_client,
                timeout=request_timeout,
            )

        def build_async(endpoint: LLMEndpointConfig) -> AsyncOpenAI:
            timeout = httpx.Timeout(connect=5.0, read=request_timeout, write=request_timeout, pool=request_timeout)
            http_client = httpx.AsyncClient(trust_env=False, timeout=timeout)
            return AsyncOpenAI(
                base_url=endpoint.base_url,
                api_key=endpoint.api_key,
                http_client=http_client,
                timeout=request_timeout,
            )

        return cls(
            endpoints=endpoint_list,
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
            sync_client_builder=build_sync,
            async_client_builder=build_async,
            max_concurrency=max(1, max_concurrency),
            request_timeout=request_timeout,
        )

    def _select_endpoint(self) -> LLMEndpointConfig:
        """选择一个可用端点，若都不可用则返回优先级最高的端点做最终尝试。"""
        now = time.time()
        candidate: Optional[LLMEndpointConfig] = None

        for endpoint in self._order:
            state = self._states[endpoint.name]
            if not state.available and now >= state.recovery_at:
                # 中文注释：到达恢复时间后，允许端点以半开状态试探
                state.available = True
                state.half_open = True

            if state.available:
                candidate = endpoint
                break

        if candidate is None:
            candidate = self._order[0]
            logger.warning(
                "llm_all_endpoints_unavailable",
                fallback=candidate.name,
                states=self._snapshot(),
            )

        return candidate

    def _acquire_sync_client(self, endpoint: LLMEndpointConfig) -> OpenAI:
        client = self._sync_clients.get(endpoint.name)
        if client is None:
            client = self._sync_builder(endpoint)
            self._sync_clients[endpoint.name] = client
        return client

    def _acquire_async_client(self, endpoint: LLMEndpointConfig) -> AsyncOpenAI:
        client = self._async_clients.get(endpoint.name)
        if client is None:
            client = self._async_builder(endpoint)
            self._async_clients[endpoint.name] = client
        return client

    def _on_success(self, endpoint: LLMEndpointConfig, latency_ms: int) -> None:
        state = self._states[endpoint.name]
        state.consecutive_successes += 1
        state.consecutive_failures = 0
        state.available = True
        state.half_open = False

        logger.info(
            "llm_endpoint_success",
            endpoint=endpoint.name,
            latency_ms=latency_ms,
            status=self._snapshot(),
        )

    def _on_failure(self, endpoint: LLMEndpointConfig, latency_ms: int, error: Exception) -> None:
        state = self._states[endpoint.name]
        state.consecutive_failures += 1
        state.consecutive_successes = 0

        status_code = getattr(error, "status_code", None)
        try:
            status_code_int = int(status_code) if status_code is not None else None
        except (TypeError, ValueError):
            status_code_int = None
        error_text = str(error)
        is_rate_limit = status_code_int == 429 or ('429' in error_text)
        cooldown = self._recovery_seconds * (2 if is_rate_limit else 1)

        if state.consecutive_failures >= self._failure_threshold or is_rate_limit:
            state.available = False
            state.half_open = False
            state.recovery_at = time.time() + cooldown

        logger.warning(
            'llm_endpoint_failure',
            endpoint=endpoint.name,
            latency_ms=latency_ms,
            failure_count=state.consecutive_failures,
            marked_unavailable=not state.available,
            error=str(error),
            rate_limited=is_rate_limit,
            status=self._snapshot(),
        )

    def _snapshot(self) -> Dict[str, Dict[str, object]]:
        return {
            name: {
                "available": state.available,
                "half_open": state.half_open,
                "failures": state.consecutive_failures,
                "recovery_at": state.recovery_at,
            }
            for name, state in self._states.items()
        }

    def call_sync(
        self,
        operation: str,
        caller: Callable[[OpenAI, LLMEndpointConfig], T],
    ) -> T:
        """同步调用入口，自动处理主备切换。"""

        last_exc: Optional[Exception] = None
        attempts = 0
        max_attempts = len(self._order) + self._failure_threshold

        while attempts < max_attempts:
            t_qs = time.time()
            self._sync_semaphore.acquire()
            queued_ms = int((time.time() - t_qs) * 1000)
            if queued_ms > 2000:
                logger.warning("llm_queue_wait", operation=operation, queued_ms=queued_ms)
            elif queued_ms > 0:
                logger.info("llm_queue_wait", operation=operation, queued_ms=queued_ms)
            try:
                with self._lock:
                    endpoint = self._select_endpoint()
                attempts += 1

                client = self._acquire_sync_client(endpoint)
                start = time.time()

                try:
                    result = caller(client, endpoint)
                    latency_ms = int((time.time() - start) * 1000)
                    with self._lock:
                        self._on_success(endpoint, latency_ms)
                    return result
                except Exception as exc:  # noqa: BLE001
                    latency_ms = int((time.time() - start) * 1000)
                    with self._lock:
                        self._on_failure(endpoint, latency_ms, exc)
                    last_exc = exc
                    continue
            finally:
                self._sync_semaphore.release()

        assert last_exc is not None
        snapshot = self._snapshot()  # 捕获当前状态
        logger.error("llm_endpoints_exhausted", operation=operation, states=snapshot)  # 记录致命错误
        raise LLMEndpointsExhaustedError(operation, snapshot) from last_exc  # 抛出自定义异常

    async def call_async(
        self,
        operation: str,
        caller: Callable[[AsyncOpenAI, LLMEndpointConfig], T],
    ) -> T:
        """异步调用入口，自动处理主备切换。"""

        last_exc: Optional[Exception] = None
        attempts = 0
        max_attempts = len(self._order) + self._failure_threshold

        while attempts < max_attempts:
            t_qs = time.time()
            await self._async_semaphore.acquire()
            queued_ms = int((time.time() - t_qs) * 1000)
            if queued_ms > 2000:
                logger.warning("llm_queue_wait", operation=operation, queued_ms=queued_ms)
            elif queued_ms > 0:
                logger.info("llm_queue_wait", operation=operation, queued_ms=queued_ms)
            try:
                with self._lock:
                    endpoint = self._select_endpoint()
                attempts += 1

                client = self._acquire_async_client(endpoint)
                start = time.time()

                try:
                    call = caller(client, endpoint)
                    if self._request_timeout > 0:
                        result = await asyncio.wait_for(call, timeout=self._request_timeout)
                    else:
                        result = await call
                    latency_ms = int((time.time() - start) * 1000)
                    with self._lock:
                        self._on_success(endpoint, latency_ms)
                    return result
                except Exception as exc:  # noqa: BLE001
                    latency_ms = int((time.time() - start) * 1000)
                    with self._lock:
                        self._on_failure(endpoint, latency_ms, exc)
                    last_exc = exc
                    continue
            finally:
                self._async_semaphore.release()

        assert last_exc is not None
        snapshot = self._snapshot()  # 捕获当前状态
        logger.error("llm_endpoints_exhausted", operation=operation, states=snapshot)  # 记录致命错误
        raise LLMEndpointsExhaustedError(operation, snapshot) from last_exc  # 抛出自定义异常

    def status_snapshot(self) -> Dict[str, Dict[str, object]]:
        """供监控/日志使用的状态快照。"""
        with self._lock:
            return self._snapshot()
