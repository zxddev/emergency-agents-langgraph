from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Optional

import pytest
from psycopg_pool import AsyncConnectionPool, ConnectionPool

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.fspath(ROOT / "src"))


# 配置pytest-anyio只使用asyncio后端（避免trio依赖）
@pytest.fixture(scope="session")
def anyio_backend():
    """配置pytest-anyio只使用asyncio后端"""
    return "asyncio"


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> Optional[bool]:
    """异步测试执行钩子（避免与 pytest-anyio 冲突）。

    若用例标注了 anyio/asyncio 等异步标记，则交由对应插件管理事件循环；
    仅在无任何异步插件接管时，才启用手动事件循环以兼容旧测试。
    """

    function = pyfuncitem.obj
    if not asyncio.iscoroutinefunction(function):
        return None

    # 交给 pytest-anyio / pytest-asyncio 管理
    if "anyio" in pyfuncitem.keywords or "asyncio" in pyfuncitem.keywords:
        return None

    signature = inspect.signature(function)
    accepted = {
        name: value
        for name, value in pyfuncitem.funcargs.items()
        if name in signature.parameters
    }

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(function(**accepted))
    finally:
        loop.close()
    return True


# ============================================================================
# 集成测试 Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """提供 PostgreSQL 连接字符串，未配置则跳过测试"""
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN 未配置，跳过 PostgreSQL 集成测试")
    return dsn


@pytest.fixture(scope="session")
def postgres_pool(postgres_dsn: str) -> Iterable[ConnectionPool]:
    """提供 PostgreSQL 连接池（同步版本，用于 DeviceDirectory）"""
    pool = ConnectionPool(postgres_dsn, min_size=1, max_size=1, open=True)
    try:
        pool.wait(timeout=60)
        yield pool
    finally:
        pool.close()


@pytest.fixture
async def async_postgres_pool(postgres_dsn: str) -> AsyncIterator[AsyncConnectionPool[Any]]:
    """提供 PostgreSQL 异步连接池（用于 RescueTaskRepository）

    参考：psycopg文档要求open()后必须wait()等待连接建立
    https://www.psycopg.org/psycopg3/docs/advanced/pool.html
    """
    pool = AsyncConnectionPool(postgres_dsn, min_size=1, max_size=1, open=False)
    await pool.open()
    await pool.wait(timeout=60.0)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
def device_directory(postgres_pool: ConnectionPool):
    """提供真实的 PostgresDeviceDirectory 实例"""
    from emergency_agents.external.device_directory import PostgresDeviceDirectory

    return PostgresDeviceDirectory(pool=postgres_pool)


@pytest.fixture
def amap_client():
    """提供真实的高德地图客户端，未配置 API key 则跳过测试"""
    api_key = os.getenv("AMAP_API_KEY")
    if not api_key:
        pytest.skip("AMAP_API_KEY 未配置，跳过高德地图集成测试")

    from emergency_agents.external.amap_client import AmapClient

    backup_key = os.getenv("AMAP_API_BACKUP_KEY")
    base_url = os.getenv("AMAP_API_URL", "https://restapi.amap.com")

    return AmapClient(
        api_key=api_key,
        backup_key=backup_key,
        base_url=base_url,
        connect_timeout=10.0,
        read_timeout=10.0,
    )


@pytest.fixture
def empty_risk_repository():
    """提供空的 RiskRepository 实现，用于最小化测试依赖"""
    from dataclasses import dataclass
    from datetime import datetime, timezone
    from emergency_agents.risk.repository import RiskZoneRecord

    @dataclass
    class _EmptyRiskRepository:
        """空风险数据仓库，返回固定测试数据"""

        async def list_active_zones(self) -> list[RiskZoneRecord]:
            now = datetime.now(timezone.utc)
            return [
                RiskZoneRecord(
                    zone_id="test-zone-1",
                    zone_name="测试化工园区",
                    hazard_type="chemical_leak",
                    severity=4,
                    description="化工泄漏风险区域",
                    geometry_geojson={
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [120.1551, 30.2741],
                                [120.1551, 30.2796],
                                [120.1606, 30.2796],
                                [120.1606, 30.2741],
                                [120.1551, 30.2741],
                            ]
                        ],
                    },
                    properties={},
                    valid_from=now,
                    valid_until=None,
                    created_at=now,
                    updated_at=now,
                )
            ]

        async def find_zones_near(
            self, *, lng: float, lat: float, radius_meters: float
        ) -> list[RiskZoneRecord]:
            """查询指定坐标附近的风险区域（测试实现，返回所有活跃区域）"""
            return await self.list_active_zones()

    return _EmptyRiskRepository()


@pytest.fixture(autouse=True)
def cleanup_test_data(request: pytest.FixtureRequest):
    """自动清理测试数据（所有 device_id 以 TEST- 开头的记录）"""
    # 只在集成测试中执行清理
    if "integration" not in request.keywords:
        yield
        return

    # 测试前不清理，允许测试准备数据
    yield

    # 测试后清理（延迟获取postgres_pool）
    try:
        pool = request.getfixturevalue("postgres_pool")
        with pool.connection() as conn:
            conn.execute("DELETE FROM operational.device WHERE device_id LIKE 'TEST-%'")
            conn.commit()
    except Exception:
        # 清理失败不影响测试结果
        pass
