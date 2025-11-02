from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest
import importlib

try:
    importlib.import_module("langgraph.checkpoint.postgres.aio")
except ModuleNotFoundError:
    pytest.skip("langgraph checkpoint module unavailable", allow_module_level=True)

from emergency_agents.db.models import RiskZoneRecord
from emergency_agents.external.device_directory import DeviceDirectory
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.intent.handlers.scout_task_generation import ScoutTaskGenerationHandler
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from psycopg_pool import AsyncConnectionPool


class _StubRiskRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.zones = [
            RiskZoneRecord(
                zone_id="zone-1",
                zone_name="化工园东侧",
                hazard_type="chemical_leak",
                severity=4,
                description="疑似有毒气体泄漏",
                geometry_geojson={"type": "Point", "coordinates": [120.0, 30.0]},
                properties={},
                valid_from=now - timedelta(hours=1),
                valid_until=now + timedelta(hours=2),
                created_at=now - timedelta(hours=1),
                updated_at=now,
            )
        ]

    async def list_active_zones(self) -> list[RiskZoneRecord]:
        return list(self.zones)

    async def find_zones_near(self, *, lng: float, lat: float, radius_meters: float) -> list[RiskZoneRecord]:
        """查询指定坐标附近的风险区域（测试实现，返回所有活跃区域）"""
        return await self.list_active_zones()


@pytest.mark.integration
@pytest.mark.anyio
async def test_scout_handler_generates_plan(
    async_postgres_pool: AsyncConnectionPool,
    postgres_dsn: str,
    device_directory: DeviceDirectory,
) -> None:
    """测试 ScoutTaskGenerationHandler 使用懒加载模式生成侦察计划

    注意：此测试需要真实PostgreSQL连接和DeviceDirectory（用于LangGraph graph构建）
    """
    # 创建 Stub 风险数据仓库（包含1个化工泄漏风险区域）
    risk_repository = _StubRiskRepository()

    # 创建 Mock 依赖（Handler 会懒加载 Graph）
    # 注意：DeviceDirectory使用真实fixture（集成测试）
    # AmapClient是异步客户端，使用AsyncMock并配置返回值
    mock_amap_client = AsyncMock()
    mock_amap_client.direction.return_value = {
        "distance_meters": 1500,
        "duration_seconds": 180,
        "steps": [],
        "cache_hit": False,
    }
    # OrchestratorClient是同步客户端，使用Mock
    mock_orchestrator = Mock()
    mock_orchestrator.publish_scout_scenario.return_value = {"success": True}

    # 创建 Handler（使用新的懒加载模式）
    # 注意：postgres_dsn, pool, device_directory需要真实值以支持LangGraph graph构建
    handler = ScoutTaskGenerationHandler(
        risk_repository=risk_repository,  # type: ignore[arg-type]
        device_directory=device_directory,  # 真实DeviceDirectory（来自fixture）
        amap_client=mock_amap_client,
        orchestrator_client=mock_orchestrator,
        postgres_dsn=postgres_dsn,  # 真实DSN（来自fixture）
        pool=async_postgres_pool,  # 真实连接池（来自fixture）
    )

    # 准备意图槽位
    slots = ScoutTaskGenerationSlots(
        target_type="hazard",
        objective_summary="确认化工园泄漏范围",
    )

    # 准备状态字典
    # 注意：incident_id必须是有效UUID（和integration测试一致）
    state: Dict[str, Any] = {
        "user_id": "u1",
        "thread_id": "thread-scout-handler-1",
        "conversation_context": {"incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630"},
    }

    # 执行 Handler（内部会懒加载 ScoutTacticalGraph）
    result = await handler.handle(slots, state)

    # 验证生成的侦察计划
    plan = result["scout_plan"]
    assert plan["targets"], "需要侦察目标"
    assert plan["overview"]["riskSummary"]["total"] == 1

    # 验证 UI 动作（应包含风险警告）
    ui_actions = result["ui_actions"]
    assert any(action["action"] == "show_risk_warning" for action in ui_actions)
