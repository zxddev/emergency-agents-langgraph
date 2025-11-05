"""
统一日志模块

提供全局structlog配置，包括：
- 统一processor链（时间戳、堆栈、trace-id注入）
- JSON/控制台双渲染模式
- Prometheus指标集中注册
- 自动trace-id上下文管理

参考：docs/新业务逻辑md/new_0.1/子图体系开发规划.md 第2章
      docs/新业务逻辑md/new_0.1/Phase0-问题分析报告-修正版.md P0-4
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
import os
from typing import Any

import structlog
from prometheus_client import Counter, Histogram

# 是否抑制定时/健康检查类日志的运行时开关（可热切换）
_SUPPRESS_PERIODIC_LOGS_FLAG: bool = (
    os.getenv("SUPPRESS_PERIODIC_LOGS", "false").lower() in {"1", "true", "yes", "y", "on"}
)

# ========== ContextVar：跨异步边界的trace-id传递 ==========
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


# ========== Prometheus指标集中注册 ==========
# 日志计数器：按级别和模块统计日志数量
log_count_metric = Counter(
    "emergency_log_total",
    "日志总数（按级别和模块分类）",
    ["level", "module"],
)

# 日志延迟直方图：记录日志处理延迟
log_latency_metric = Histogram(
    "emergency_log_latency_seconds",
    "日志处理延迟（秒）",
    ["module"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)


# ========== 自定义Processor：trace-id注入 ==========
def add_trace_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    从ContextVar中提取trace-id并注入到日志上下文

    用法：
        from emergency_agents.logging import set_trace_id
        set_trace_id("req-12345")
        logger.info("processing_request")  # 自动包含trace_id字段
    """
    trace_id = trace_id_var.get()
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def add_prometheus_metrics(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    日志事件计数到Prometheus

    记录每个级别的日志数量，用于监控异常日志激增
    """
    level = event_dict.get("level", "info")
    module = event_dict.get("logger", "unknown")
    log_count_metric.labels(level=level, module=module).inc()
    return event_dict


# ========== 全局配置函数 ==========
def configure_logging(
    *,
    json_logs: bool = False,
    log_level: str = "INFO",
) -> None:
    """
    配置全局structlog

    Args:
        json_logs: 是否输出JSON格式（生产环境推荐True）
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）

    使用方式：
        # 在应用启动时调用一次
        from emergency_agents.logging import configure_logging
        configure_logging(json_logs=True, log_level="INFO")

        # 之后所有模块直接使用
        import structlog
        logger = structlog.get_logger(__name__)
        logger.info("hello", user_id="123")  # 自动包含trace_id、timestamp等
    """
    # 配置标准库logging（作为structlog的后端）
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    def drop_periodic_logs(
        logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """在开启 SUPPRESS_PERIODIC_LOGS 时丢弃噪声型的定时日志。

        说明：
        - 仅针对周期性任务产生日志（健康检查、缓存刷新、概要统计）。
        - 不影响正常的错误/业务日志；只根据事件名过滤。
        - 通过返回 structlog.DropEvent 让该日志完全不输出，也不计入 Prometheus 指标。
        """
        # 读取模块级开关，支持运行时热切换
        if not _SUPPRESS_PERIODIC_LOGS_FLAG:
            return event_dict

        event = str(event_dict.get("event", ""))
        if not event:
            return event_dict

        # 前缀匹配：大多数定时健康检查日志
        PERIODIC_PREFIXES = (
            "health_check_",          # health_check_start/complete/loop_*/error 等
            "service_health_check",   # service_health_check 与其 *_timeout/_error
            "aliyun_asr_",            # aliyun_asr_start / aliyun_asr_done
        )

        # 精确匹配：其它周期性刷新/统计
        PERIODIC_EXACT = {
            "risk_cache_refreshed",
            "risk_prediction_summary",
            "dao_incident_list_active_risk_zones",
            "service_recovered",
            "local_asr_unhealthy",
        }

        if event in PERIODIC_EXACT or any(event.startswith(p) for p in PERIODIC_PREFIXES):
            raise structlog.DropEvent

        return event_dict

    processors: list[Any] = [
        # 1. 添加logger名称
        structlog.stdlib.add_logger_name,
        # 2. 添加日志级别
        structlog.stdlib.add_log_level,
        # 2.5 在Prometheus计数前过滤周期性日志（按事件名）
        drop_periodic_logs,
        # 3. 添加时间戳
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # 4. 自定义：trace-id注入
        add_trace_id,
        # 5. 自定义：Prometheus指标
        add_prometheus_metrics,
        # 6. 堆栈信息提取（异常时）
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # 7. 最终渲染器（JSON或控制台）
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(),
    ]

    # 应用配置
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ========== 便捷函数：trace-id管理 ==========
def set_trace_id(trace_id: str) -> None:
    """
    设置当前协程的trace-id

    示例：
        from emergency_agents.logging import set_trace_id
        from emergency_agents.api.main import app

        @app.middleware("http")
        async def trace_id_middleware(request: Request, call_next):
            trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
            set_trace_id(trace_id)
            response = await call_next(request)
            return response
    """
    trace_id_var.set(trace_id)


def clear_trace_id() -> None:
    """清除当前协程的trace-id（防止上下文泄漏）"""
    trace_id_var.set(None)


def get_trace_id() -> str | None:
    """获取当前协程的trace-id（用于手动传递）"""
    return trace_id_var.get()


# ========== 运行时控制：定时日志抑制 ==========
def set_periodic_logs_suppressed(enabled: bool) -> None:
    """运行时打开/关闭定时日志抑制（无需重启）。

    示例：
        from emergency_agents.logging import set_periodic_logs_suppressed
        set_periodic_logs_suppressed(True)
    """
    global _SUPPRESS_PERIODIC_LOGS_FLAG
    _SUPPRESS_PERIODIC_LOGS_FLAG = bool(enabled)


# ========== 默认初始化 ==========
# 在模块导入时自动配置（开发环境使用控制台渲染）
# 生产环境应在应用启动时显式调用 configure_logging(json_logs=True)
configure_logging(json_logs=False, log_level="INFO")
