from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ServiceStatus:
    name: str
    available: bool
    last_check_time: float
    last_check_success: bool
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class HealthChecker:
    """健康检查服务：定期检查各个服务的可用性，并维护状态。"""

    def __init__(self, check_interval: int = 30) -> None:
        self.check_interval = check_interval
        self.services: dict[str, ServiceStatus] = {}
        self.check_functions: dict[str, Callable[[], Awaitable[bool]]] = {}
        self._task: asyncio.Task | None = None
        self._running = False

        logger.info("health_checker_initialized", check_interval=check_interval)

    def register_service(
        self,
        service_name: str,
        check_function: Callable[[], Awaitable[bool]],
    ) -> None:
        self.check_functions[service_name] = check_function
        self.services[service_name] = ServiceStatus(
            name=service_name,
            available=False,
            last_check_time=0,
            last_check_success=False,
            consecutive_failures=0,
            consecutive_successes=0,
        )
        logger.info("service_registered", service_name=service_name)

    async def start(self) -> None:
        if self._running:
            logger.warning("health_checker_already_running")
            return

        self._running = True
        await self._check_all_services()
        self._task = asyncio.create_task(self._check_loop())
        logger.info("health_checker_started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("health_checker_stopped")

    async def _check_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_all_services()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_check_loop_error", error=str(e), exc_info=True)

    async def _check_all_services(self) -> None:
        if not self.check_functions:
            logger.debug("no_services_registered")
            return

        tasks = []
        service_names = []
        for service_name, check_fn in self.check_functions.items():
            tasks.append(self._check_single_service(service_name, check_fn))
            service_names.append(service_name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for service_name, result in zip(service_names, results):
            if isinstance(result, Exception):
                logger.error(
                    "health_check_exception",
                    service_name=service_name,
                    error=str(result),
                )
                self._update_service_status(service_name, False)
            elif isinstance(result, bool):
                self._update_service_status(service_name, result)
            else:
                logger.warning(
                    "health_check_unexpected_result",
                    service_name=service_name,
                    result=result,
                )
                self._update_service_status(service_name, False)

        summary = {name: status.available for name, status in self.services.items()}
        logger.info("health_check_complete", summary=summary)

    async def _check_single_service(
        self,
        service_name: str,
        check_fn: Callable[[], Awaitable[bool]],
    ) -> bool:
        start_time = time.time()
        try:
            is_available = await asyncio.wait_for(check_fn(), timeout=10.0)
            latency_ms = int((time.time() - start_time) * 1000)
            logger.debug(
                "service_health_check",
                service_name=service_name,
                available=is_available,
                latency_ms=latency_ms,
            )
            return is_available
        except asyncio.TimeoutError:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                "service_health_check_timeout",
                service_name=service_name,
                latency_ms=latency_ms,
            )
            return False
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                "service_health_check_error",
                service_name=service_name,
                error=str(e),
                latency_ms=latency_ms,
            )
            return False

    def _update_service_status(self, service_name: str, is_available: bool) -> None:
        if service_name not in self.services:
            return

        status = self.services[service_name]
        status.last_check_time = time.time()
        status.last_check_success = is_available

        if is_available:
            status.consecutive_successes += 1
            status.consecutive_failures = 0
            if status.consecutive_successes >= 2:
                status.available = True
        else:
            status.consecutive_failures += 1
            status.consecutive_successes = 0
            if status.consecutive_failures >= 2:
                status.available = False

    def is_service_available(self, service_name: str) -> bool:
        if service_name not in self.services:
            logger.debug("service_not_registered", service_name=service_name)
            return False
        return self.services[service_name].available

    def get_service_status(self, service_name: str) -> ServiceStatus | None:
        return self.services.get(service_name)

    def get_all_statuses(self) -> dict[str, ServiceStatus]:
        return self.services.copy()


