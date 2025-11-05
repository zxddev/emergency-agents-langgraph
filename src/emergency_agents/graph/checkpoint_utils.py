from __future__ import annotations

from typing import Awaitable, Callable, Tuple

import structlog
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ModuleNotFoundError as exc:  # pragma: no cover - 开发环境缺少可选依赖时触发
    AsyncPostgresSaver = None  # type: ignore[assignment]
    _missing_langgraph_error = exc
else:
    _missing_langgraph_error = None

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool


logger = structlog.get_logger(__name__)


async def create_async_postgres_checkpointer(
    *,
    dsn: str,
    schema: str,
    min_size: int = 1,
    max_size: int = 5,
) -> Tuple[AsyncPostgresSaver, Callable[[], Awaitable[None]]]:
    """创建异步 Postgres checkpointer。

    - 要求在事件循环内执行，确保与LangGraph AsyncPregelLoop同一调度器。
    - 建立专属schema并初始化连接池。
    - 返回AsyncPostgresSaver及关闭回调，由调用方纳入生命周期管理。
    """
    if AsyncPostgresSaver is None:
        raise RuntimeError(
            "langgraph.checkpoint.postgres 未安装，无法创建 checkpointer，请安装 `langgraph` 依赖。"
        ) from _missing_langgraph_error

    normalized_dsn = dsn.strip() if dsn else ""
    if not normalized_dsn:
        raise ValueError("POSTGRES_DSN 缺失，无法创建 LangGraph checkpointer")

    # 第一步：使用 autocommit 连接创建 schema（避免事务冲突）
    admin_conn = await AsyncConnection.connect(normalized_dsn, autocommit=True)
    try:
        await admin_conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    finally:
        await admin_conn.close()

    # 第二步：创建 autocommit 连接用于执行 setup()
    # LangGraph 的迁移6/7/8使用 CREATE INDEX CONCURRENTLY，必须在 autocommit 模式下执行
    # 注意：使用 AsyncConnection 而不是 Pool，以便设置 search_path
    setup_conn = await AsyncConnection.connect(
        normalized_dsn,
        autocommit=True,  # 关键：启用 autocommit 避免事务冲突
    )

    try:
        # 设置 search_path 到自定义 schema + public（必须包含public以访问PostGIS函数）
        await setup_conn.execute(f"SET search_path TO {schema}, public")

        # AsyncPostgresSaver 会在当前 search_path 的 schema 中创建表
        setup_saver = AsyncPostgresSaver(setup_conn)
        await setup_saver.setup()
        logger.info("async_postgres_checkpointer_schema_initialized", schema=schema)
    finally:
        await setup_conn.close()

    # 第三步：创建正常的连接池（用于运行时 checkpoint 操作）
    # 注意：PostgreSQL 17 不支持在 kwargs.options 中设置 search_path
    # 改用数据库级别配置：ALTER DATABASE ... SET search_path TO operational, public;
    pool = AsyncConnectionPool(
        conninfo=normalized_dsn,
        min_size=min_size,
        max_size=max_size,
        open=False,
    )
    logger.info(
        "async_postgres_checkpointer_opening",
        schema=schema,
        min_size=min_size,
        max_size=max_size,
    )
    await pool.open()

    # 第四步：创建运行时 checkpointer（schema 已初始化，无需再次 setup）
    # 注意：新版本不再支持 schema_name 参数，改用 search_path
    saver = AsyncPostgresSaver(pool)
    logger.info("async_postgres_checkpointer_ready", schema=schema)

    async def _close() -> None:
        await pool.close()
        logger.info("async_postgres_checkpointer_closed", schema=schema)

    return saver, _close
