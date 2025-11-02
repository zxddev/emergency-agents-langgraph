from __future__ import annotations

import asyncio
import os
import time
from typing import Any, List, Tuple

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool


def _require_dsn() -> str:
    """读取 POSTGRES_DSN 环境变量，不存在则跳过诊断测试。"""
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN 未配置，跳过诊断测试")
    return dsn


async def _parallel_connect_attempts(dsn: str, attempts: int, timeout: float) -> Tuple[int, int]:
    """并发尝试建立若干直连连接，返回 (成功数, 失败数)。"""

    ok = 0
    fail = 0

    async def _one() -> bool:
        try:
            # psycopg3 同步 connect 在 asyncio 环境中可用；此处使用线程池规避阻塞
            def _connect() -> bool:
                with psycopg.connect(dsn, connect_timeout=timeout) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        _ = cur.fetchone()
                return True

            return await asyncio.to_thread(_connect)
        except Exception:
            return False

    tasks = [asyncio.create_task(_one()) for _ in range(max(1, attempts))]
    for fut in asyncio.as_completed(tasks, timeout=timeout + 5.0):
        try:
            if await fut:
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
    return ok, fail


@pytest.mark.diagnostic
@pytest.mark.anyio
async def test_diag_direct_connect_parallel() -> None:
    """并发直连诊断：快速评估同一路径可用连接位。

    - 不依赖连接池，直接使用 psycopg 连接。
    - 仅记录成功/失败，不做强断言，避免阻断其它测试。
    """

    dsn = _require_dsn()
    start = time.perf_counter()
    ok, fail = await _parallel_connect_attempts(dsn, attempts=10, timeout=5.0)
    duration = time.perf_counter() - start
    print({"diag": "direct_parallel", "ok": ok, "fail": fail, "duration_sec": round(duration, 3)})


@pytest.mark.diagnostic
@pytest.mark.anyio
async def test_diag_pool_sequential_acquire_release() -> None:
    """连接池诊断：单连接位反复借还，验证是否存在泄露或占位不归还。

    - 使用 AsyncConnectionPool(min_size=1, max_size=1)
    - 重复 10 次借还连接，每次执行 SELECT 1
    """

    dsn = _require_dsn()
    pool = AsyncConnectionPool(dsn, min_size=1, max_size=1, open=False)
    await pool.open()
    await pool.wait(timeout=60.0)
    rounds = 10
    start = time.perf_counter()
    try:
        for i in range(rounds):
            async with pool.connection(timeout=60.0) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    _ = await cur.fetchone()
        duration = time.perf_counter() - start
        print({"diag": "pool_seq", "rounds": rounds, "duration_sec": round(duration, 3)})
    finally:
        await pool.close()


@pytest.mark.diagnostic
@pytest.mark.anyio
async def test_diag_pool_under_small_concurrency() -> None:
    """连接池诊断：在 max_size=1 条件下以小并发压测排队行为。

    - 期望队列排队而非超时；若持续超时，说明路径拿不到首个连接位。
    """

    dsn = _require_dsn()
    pool = AsyncConnectionPool(dsn, min_size=1, max_size=1, open=False)
    await pool.open()
    await pool.wait(timeout=60.0)

    async def one_job(idx: int) -> bool:
        try:
            async with pool.connection(timeout=60.0) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    _ = await cur.fetchone()
            return True
        except Exception as exc:  # pragma: no cover - 仅诊断输出
            print({"diag": "pool_small_conc", "job": idx, "error": type(exc).__name__})
            return False

    jobs = [asyncio.create_task(one_job(i)) for i in range(5)]
    ok = 0
    for fut in asyncio.as_completed(jobs, timeout=65.0):
        try:
            if await fut:
                ok += 1
        except Exception:
            pass
    print({"diag": "pool_small_conc", "ok": ok, "total": 5})
    await pool.close()


@pytest.mark.diagnostic
@pytest.mark.anyio
async def test_diag_dao_risk_zones_single() -> None:
    """DAO 路径单次访问：复现当前卡死点的精简调用。"""

    from emergency_agents.db.dao import IncidentDAO

    dsn = _require_dsn()
    pool = AsyncConnectionPool(dsn, min_size=1, max_size=1, open=False)
    await pool.open()
    await pool.wait(timeout=60.0)
    dao = IncidentDAO.create(pool)
    try:
        rows = await dao.list_active_risk_zones()
        print({"diag": "dao_risk", "rows": len(rows)})
    finally:
        await pool.close()

