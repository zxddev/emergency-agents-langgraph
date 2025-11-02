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

    # 第二步：创建 autocommit 连接池用于执行 setup()（避免并发索引创建失败）
    # LangGraph 的迁移6/7/8使用 CREATE INDEX CONCURRENTLY，必须在 autocommit 模式下执行
    setup_pool = AsyncConnectionPool(
        conninfo=normalized_dsn,
        min_size=1,
        max_size=1,
        kwargs={
            "options": f"-c search_path={schema}",
            "autocommit": True,  # 关键：启用 autocommit 避免事务冲突
        },
        open=False,
    )
    await setup_pool.open()

    try:
        setup_saver = AsyncPostgresSaver(setup_pool)
        await setup_saver.setup()
        logger.info("async_postgres_checkpointer_schema_initialized", schema=schema)
    finally:
        await setup_pool.close()

    # 第三步：创建正常的连接池（用于运行时 checkpoint 操作）
    pool = AsyncConnectionPool(
        conninfo=normalized_dsn,
        min_size=min_size,
        max_size=max_size,
        kwargs={"options": f"-c search_path={schema}"},
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
    saver = AsyncPostgresSaver(pool)
    logger.info("async_postgres_checkpointer_ready", schema=schema)

    async def _close() -> None:
        await pool.close()
        logger.info("async_postgres_checkpointer_closed", schema=schema)

    return saver, _close
