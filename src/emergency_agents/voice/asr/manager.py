# Copyright 2025 msq
from __future__ import annotations

"""ASR管理器：负责Provider选择、自动降级和健康检查。

摘要：实现多Provider管理，支持阿里云优先、本地备用的自动降级策略。
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

from .base import ASRConfig, ASRProvider, ASRResult

logger = structlog.get_logger(__name__)


@dataclass
class ProviderStatus:
    """Provider健康状态。
    
    Args:
        available: 是否可用。
        consecutive_successes: 连续成功次数。
        consecutive_failures: 连续失败次数。
        last_check_time: 最后检查时间戳。
        last_check_latency_ms: 最后一次检查延迟（毫秒）。
    """

    available: bool = False
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_check_time: float = 0.0
    last_check_latency_ms: int = 0


class ASRManager:
    """ASR管理器：管理多个Provider，实现自动降级。
    
    核心功能：
    1. Provider选择：根据健康状态和优先级选择最佳Provider
    2. 自动降级：主Provider失败时自动切换到备用Provider
    3. 健康检查：后台定期检查各Provider健康状态
    4. 故障恢复：服务恢复后自动切回高优先级Provider
    """

    def __init__(self, providers: list[ASRProvider] | None = None) -> None:
        """初始化ASR管理器。
        
        Args:
            providers: Provider列表，None时自动创建默认Provider（阿里云+本地）。
        """
        # 创建默认Provider
        if providers is None:
            providers = self._create_default_providers()

        # Provider字典：{name: provider}
        self._providers: dict[str, ASRProvider] = {p.name: p for p in providers}

        # 从环境变量读取配置
        self._ENV_PRIMARY = os.getenv("ASR_PRIMARY_PROVIDER", "aliyun")
        self._ENV_FALLBACK = os.getenv("ASR_FALLBACK_PROVIDER", "local")
        self._ENV_HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))

        # 健康状态字典：{name: ProviderStatus}
        self._provider_status: dict[str, ProviderStatus] = {
            name: ProviderStatus() for name in self._providers
        }

        # 健康检查任务
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_running = False

        logger.info(
            "asr_manager_initialized",
            providers=list(self._providers.keys()),
            primary=self._ENV_PRIMARY,
            fallback=self._ENV_FALLBACK,
            health_check_interval=self._ENV_HEALTH_CHECK_INTERVAL,
        )

    def _create_default_providers(self) -> list[ASRProvider]:
        """创建默认的Provider列表（阿里云+本地）。
        
        Returns:
            list[ASRProvider]: Provider列表。
        """
        providers: list[ASRProvider] = []

        # 尝试创建阿里云Provider
        try:
            from .aliyun_provider import AliyunASRProvider

            dashscope_key = os.getenv("DASHSCOPE_API_KEY")
            if dashscope_key:
                providers.append(AliyunASRProvider(api_key=dashscope_key))
                logger.info("asr_provider_created", provider="aliyun")
            else:
                logger.warning("dashscope_api_key_missing", provider="aliyun")
        except Exception as e:
            logger.warning("asr_provider_creation_failed", provider="aliyun", error=str(e))

        # 尝试创建本地Provider
        try:
            from .local_provider import LocalFunASRProvider

            providers.append(LocalFunASRProvider())
            logger.info("asr_provider_created", provider="local")
        except Exception as e:
            logger.warning("asr_provider_creation_failed", provider="local", error=str(e))

        if not providers:
            raise RuntimeError("No ASR providers available")

        return providers

    async def recognize(
        self, audio_data: bytes, config: ASRConfig | None = None
    ) -> ASRResult:
        """执行语音识别，支持自动降级。
        
        流程：
        1. 选择Provider（根据健康状态和优先级）
        2. 尝试识别
        3. 失败时自动降级到备用Provider
        4. 返回识别结果
        
        Args:
            audio_data: 原始音频二进制数据。
            config: 识别配置，None表示使用默认值。
            
        Returns:
            ASRResult: 识别结果。
            
        Raises:
            RuntimeError: 所有Provider都失败时抛出。
        """
        # 1. 选择Provider
        provider = self._select_provider()

        logger.info(
            "asr_recognize_start",
            provider=provider.name,
            audio_size=len(audio_data),
            当前使用=f"{provider.name} (优先级={provider.priority})",
        )

        start_ts = time.time()

        try:
            # 2. 尝试识别
            result = await provider.recognize(audio_data, config)
            latency_ms = int((time.time() - start_ts) * 1000)

            logger.info(
                "asr_recognize_success",
                provider=result.provider,
                text_preview=result.text[:50] if result.text else "",
                latency_ms=latency_ms,
                使用的ASR=result.provider,
            )
            return result

        except Exception as e:
            latency_ms = int((time.time() - start_ts) * 1000)
            logger.warning(
                "asr_recognize_failed",
                provider=provider.name,
                error=str(e),
                latency_ms=latency_ms,
            )

            # 3. 自动降级
            # 尝试获取备用Provider（优先级次高的或配置的fallback）
            fallback_provider = self._get_fallback_provider()
            
            # 确保fallback不是刚刚失败的provider
            if fallback_provider and fallback_provider.name != provider.name:
                logger.warning(
                    "asr_fallback",
                    from_provider=provider.name,
                    to_provider=fallback_provider.name,
                    从=provider.name,
                    切换到=fallback_provider.name,
                )

                try:
                    fallback_start_ts = time.time()
                    result = await fallback_provider.recognize(audio_data, config)
                    fallback_latency_ms = int((time.time() - fallback_start_ts) * 1000)

                    logger.info(
                        "asr_fallback_success",
                        provider=result.provider,
                        fallback_latency_ms=fallback_latency_ms,
                        total_latency_ms=int((time.time() - start_ts) * 1000),
                    )
                    return result

                except Exception as fallback_error:
                    logger.error(
                        "asr_fallback_failed",
                        fallback_provider=fallback_provider.name,
                        error=str(fallback_error),
                    )
                    raise RuntimeError(
                        f"All ASR providers failed: primary={provider.name}, fallback={fallback_provider.name}"
                    ) from fallback_error

            # 没有可用的备用Provider，或者备用Provider就是当前失败的Provider
            raise RuntimeError(f"ASR provider failed: {provider.name}") from e

    def _select_provider(self) -> ASRProvider:
        """选择最佳Provider。
        
        选择逻辑：
        1. 优先使用主Provider（如果健康）
        2. 主Provider不健康时使用备用Provider
        3. 如果都不健康，按优先级选择
        4. 如果没有可用Provider，抛出异常
        
        Returns:
            ASRProvider: 选中的Provider。
            
        Raises:
            RuntimeError: 没有可用Provider时抛出。
        """
        # 1. 尝试使用主Provider
        if self._ENV_PRIMARY in self._providers:
            primary = self._providers[self._ENV_PRIMARY]
            primary_status = self._provider_status.get(primary.name, ProviderStatus())

            if primary_status.available or not self._health_check_running:
                # 健康检查未启动时，默认信任主Provider
                logger.info(
                    "provider_selected",
                    provider=primary.name,
                    reason="primary_available" if primary_status.available else "health_check_not_started",
                    选中=f"{primary.name}（主服务）",
                )
                return primary
            else:
                logger.warning(
                    "primary_provider_unavailable",
                    provider=primary.name,
                    consecutive_failures=primary_status.consecutive_failures,
                )

        # 2. 使用备用Provider
        if self._ENV_FALLBACK in self._providers:
            fallback = self._providers[self._ENV_FALLBACK]
            logger.info(
                "provider_selected",
                provider=fallback.name,
                reason="fallback",
                选中=f"{fallback.name}（备用服务）",
            )
            return fallback

        # 3. 按优先级选择（降级方案）
        sorted_providers = sorted(
            self._providers.values(), key=lambda p: p.priority, reverse=True
        )
        if sorted_providers:
            selected = sorted_providers[0]
            logger.info(
                "provider_selected",
                provider=selected.name,
                reason="priority",
                priority=selected.priority,
            )
            return selected

        # 4. 没有可用Provider
        raise RuntimeError("No ASR providers available")

    def _get_fallback_provider(self) -> Optional[ASRProvider]:
        """获取备用Provider。
        
        Returns:
            Optional[ASRProvider]: 备用Provider，不存在时返回None。
        """
        # 1. 首先尝试配置的备用Provider
        if self._ENV_FALLBACK in self._providers:
            return self._providers[self._ENV_FALLBACK]
        
        # 2. 如果没有配置的备用Provider，选择优先级次高的Provider
        sorted_providers = sorted(
            self._providers.values(), key=lambda p: p.priority, reverse=True
        )
        # 返回第二优先级的Provider（如果存在且不止一个Provider）
        if len(sorted_providers) > 1:
            return sorted_providers[1]
        
        return None

    async def start_health_check(self) -> None:
        """启动后台健康检查任务。
        
        健康检查会定期检查所有Provider的健康状态，并更新状态信息。
        """
        if self._health_check_task is not None:
            logger.warning("health_check_already_running")
            return

        self._health_check_running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(
            "health_check_started",
            interval=self._ENV_HEALTH_CHECK_INTERVAL,
            providers=list(self._providers.keys()),
        )

    async def stop_health_check(self) -> None:
        """停止后台健康检查任务。"""
        if self._health_check_task is None:
            logger.warning("health_check_not_running")
            return

        self._health_check_running = False
        self._health_check_task.cancel()

        try:
            await self._health_check_task
        except asyncio.CancelledError:
            pass

        self._health_check_task = None
        logger.info("health_check_stopped")

    async def _health_check_loop(self) -> None:
        """健康检查循环任务。
        
        定期检查所有Provider的健康状态，记录连续成功/失败次数。
        """
        logger.info("health_check_loop_started")

        while self._health_check_running:
            try:
                await self._perform_health_checks()
            except Exception as e:
                logger.error("health_check_loop_error", error=str(e))

            # 等待下一次检查
            await asyncio.sleep(self._ENV_HEALTH_CHECK_INTERVAL)

        logger.info("health_check_loop_stopped")

    async def _perform_health_checks(self) -> None:
        """执行一次健康检查。
        
        检查所有Provider的健康状态，更新状态信息。
        """
        logger.info(
            "health_check_start",
            provider_count=len(self._providers),
        )

        for name, provider in self._providers.items():
            status = self._provider_status[name]
            check_start_ts = time.time()

            try:
                # 执行健康检查
                is_healthy = await provider.health_check()
                latency_ms = int((time.time() - check_start_ts) * 1000)

                # 更新状态
                status.last_check_time = time.time()
                status.last_check_latency_ms = latency_ms

                if is_healthy:
                    status.consecutive_successes += 1
                    status.consecutive_failures = 0

                    # 连续成功2次后标记为可用（防止抖动）
                    if status.consecutive_successes >= 2:
                        was_unavailable = not status.available
                        status.available = True

                        if was_unavailable:
                            logger.info(
                                "service_recovered",
                                service_name=name,
                                consecutive_successes=status.consecutive_successes,
                            )
                else:
                    status.consecutive_failures += 1
                    status.consecutive_successes = 0

                    # 连续失败3次后标记为不可用（防止误判）
                    if status.consecutive_failures >= 3:
                        was_available = status.available
                        status.available = False

                        if was_available:
                            logger.warning(
                                "service_marked_unavailable",
                                service_name=name,
                                consecutive_failures=status.consecutive_failures,
                            )

                logger.info(
                    "service_health_check",
                    service_name=name,
                    available=status.available,
                    is_healthy=is_healthy,
                    latency_ms=latency_ms,
                    consecutive_successes=status.consecutive_successes,
                    consecutive_failures=status.consecutive_failures,
                )

            except Exception as e:
                latency_ms = int((time.time() - check_start_ts) * 1000)
                logger.error(
                    "health_check_error",
                    service_name=name,
                    error=str(e),
                    latency_ms=latency_ms,
                )

                # 异常也算失败
                status.consecutive_failures += 1
                status.consecutive_successes = 0
                status.last_check_time = time.time()

                if status.consecutive_failures >= 3:
                    status.available = False

        # 输出汇总信息
        summary = {
            name: status.available for name, status in self._provider_status.items()
        }
        logger.info("health_check_complete", summary=summary)

    @property
    def provider_status(self) -> dict[str, bool]:
        """获取所有Provider的健康状态。
        
        Returns:
            dict[str, bool]: Provider名称到健康状态的映射。
        """
        return {name: status.available for name, status in self._provider_status.items()}

