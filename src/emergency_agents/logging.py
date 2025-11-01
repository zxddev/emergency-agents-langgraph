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
from typing import Any

import structlog
from prometheus_client import Counter, Histogram

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

    # 配置structlog processor链
    processors: list[Any] = [
        # 1. 添加logger名称
        structlog.stdlib.add_logger_name,
        # 2. 添加日志级别
        structlog.stdlib.add_log_level,
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


# ========== 默认初始化 ==========
# 在模块导入时自动配置（开发环境使用控制台渲染）
# 生产环境应在应用启动时显式调用 configure_logging(json_logs=True)
configure_logging(json_logs=False, log_level="INFO")
