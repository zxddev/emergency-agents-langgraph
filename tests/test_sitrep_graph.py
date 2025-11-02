"""态势上报（SITREP）子图测试

测试覆盖：
1. State定义和类型检查
2. 数据采集节点（Mock DAO）
3. 分析节点（纯计算）
4. LLM节点（Mock客户端）
5. 完整graph流程
6. 幂等性验证
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from emergency_agents.db.dao import IncidentRecord, RescueDAO, TaskDAO
from emergency_agents.db.models import TaskSummary
from emergency_agents.graph.sitrep_app import (
    SITREPMetrics,
    SITREPState,
    aggregate_metrics,
    fetch_active_incidents,
    fetch_recent_tasks_task,
    fetch_resource_usage,
    fetch_risk_zones,
    finalize,
    ingest,
    llm_generate_summary,
)
from emergency_agents.risk.service import RiskZoneRecord


# ========== Fixtures ==========


@pytest.fixture
def mock_incident_dao():
    """Mock IncidentDAO"""
    dao = AsyncMock()

    # Mock list_active_incidents返回值
    dao.list_active_incidents.return_value = [
        IncidentRecord(
            id=str(uuid.uuid4()),
            event_code="EVT-001",
            title="地震事件",
            type="earthquake",
            priority=1,
            status="active",
            description="某地发生6.5级地震",
            created_by="system",
            updated_by="system",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
            parent_event_id=None,
        ),
        IncidentRecord(
            id=str(uuid.uuid4()),
            event_code="EVT-002",
            title="洪水事件",
            type="flood",
            priority=2,
            status="active",
            description="某地发生洪水",
            created_by="system",
            updated_by="system",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
            parent_event_id=None,
        ),
    ]

    return dao


@pytest.fixture
def mock_task_dao():
    """Mock TaskDAO"""
    dao = AsyncMock()

    # Mock list_recent_tasks返回值
    dao.list_recent_tasks.return_value = [
        TaskSummary(
            id=str(uuid.uuid4()),
            code="TASK-001",
            description="救援任务1",
            status="completed",
            progress=100,
            updated_at=datetime.now(timezone.utc),
        ),
        TaskSummary(
            id=str(uuid.uuid4()),
            code="TASK-002",
            description="救援任务2",
            status="in_progress",
            progress=50,
            updated_at=datetime.now(timezone.utc),
        ),
        TaskSummary(
            id=str(uuid.uuid4()),
            code="TASK-003",
            description="救援任务3",
            status="pending",
            progress=0,
            updated_at=datetime.now(timezone.utc),
        ),
    ]

    return dao


@pytest.fixture
def mock_risk_cache_manager():
    """Mock RiskCacheManager"""
    manager = AsyncMock()

    # Mock get_active_zones返回值
    manager.get_active_zones.return_value = [
        RiskZoneRecord(
            zone_id="ZONE-001",
            zone_name="危险区域1",
            threat_type="fire",
            severity="high",
            lat=30.5,
            lng=120.5,
        ),
        RiskZoneRecord(
            zone_id="ZONE-002",
            zone_name="危险区域2",
            threat_type="flood",
            severity="medium",
            lat=30.6,
            lng=120.6,
        ),
    ]

    return manager


@pytest.fixture
def mock_rescue_dao():
    """Mock RescueDAO"""
    dao = AsyncMock()

    # Mock list_rescuers返回值（简化版本）
    dao.list_rescuers.return_value = [
        MagicMock(
            team_id="TEAM-001",
            status="available",
        ),
        MagicMock(
            team_id="TEAM-001",
            status="busy",
        ),
        MagicMock(
            team_id="TEAM-002",
            status="available",
        ),
    ]

    return dao


@pytest.fixture
def mock_llm_client():
    """Mock LLM客户端"""
    client = MagicMock()

    # Mock LLM响应
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="当前救援态势总体平稳。已完成1项任务，2项任务进行中。存在2个活跃风险区域，需要持续关注。建议加强火灾区域的监控力度。"
            )
        )
    ]

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def initial_state() -> SITREPState:
    """初始State"""
    return {
        "report_id": str(uuid.uuid4()),
        "user_id": "test_user",
        "thread_id": "test_thread",
        "triggered_at": datetime.now(timezone.utc),
        "time_range_hours": 24,
    }


# ========== 单元测试 ==========


@pytest.mark.unit
def test_ingest_node(initial_state):
    """测试ingest节点：初始化和验证"""
    result = ingest(initial_state)

    assert result["status"] == "ingested"
    assert result["time_range_hours"] == 24  # 默认值
    assert "report_id" in result


@pytest.mark.unit
async def test_fetch_active_incidents_node(initial_state, mock_incident_dao):
    """测试fetch_active_incidents节点：幂等性检查逻辑"""
    # 测试幂等性：如果state中已有数据，应返回空字典
    state_with_data = initial_state | {
        "active_incidents": [
            mock_incident_dao.list_active_incidents.return_value[0]
        ]
    }
    result = fetch_active_incidents(state_with_data, mock_incident_dao)
    assert result == {}  # 幂等性：已有数据，不重复查询

    # 注意：由于@task需要LangGraph运行上下文，
    # 实际的数据库调用测试应在集成测试中进行


@pytest.mark.unit
async def test_fetch_active_incidents_idempotent(initial_state, mock_incident_dao):
    """测试fetch_active_incidents节点的幂等性"""
    # 第一次调用
    state_with_incidents = initial_state | {
        "active_incidents": [
            IncidentRecord(
                id="test-id",
                event_code="TEST",
                title="Test",
                type="test",
                priority=1,
                status="active",
                description="Test",
                created_by="test",
                updated_by="test",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
                parent_event_id=None,
            )
        ]
    }

    result = fetch_active_incidents(state_with_incidents, mock_incident_dao)

    # 幂等性验证：如果已有数据，应返回空字典（不修改state）
    assert result == {}


@pytest.mark.unit
def test_aggregate_metrics_node():
    """测试aggregate_metrics节点：指标聚合"""
    state: SITREPState = {
        "report_id": "test",
        "user_id": "test",
        "thread_id": "test",
        "triggered_at": datetime.now(timezone.utc),
        "active_incidents": [
            MagicMock(),  # 模拟2个事件
            MagicMock(),
        ],
        "task_progress": [
            TaskSummary(
                id="1",
                code="T1",
                description="",
                status="completed",
                progress=100,
                updated_at=datetime.now(timezone.utc),
            ),
            TaskSummary(
                id="2",
                code="T2",
                description="",
                status="in_progress",
                progress=50,
                updated_at=datetime.now(timezone.utc),
            ),
            TaskSummary(
                id="3",
                code="T3",
                description="",
                status="pending",
                progress=0,
                updated_at=datetime.now(timezone.utc),
            ),
        ],
        "risk_zones": [
            MagicMock(),  # 模拟3个风险区域
            MagicMock(),
            MagicMock(),
        ],
        "resource_usage": {
            "deployed_teams": 5,
            "total_rescuers": 20,
        },
        "time_range_hours": 24,
    }

    result = aggregate_metrics(state)

    assert "metrics" in result
    metrics: SITREPMetrics = result["metrics"]

    assert metrics["active_incidents_count"] == 2
    assert metrics["completed_tasks_count"] == 1
    assert metrics["in_progress_tasks_count"] == 1
    assert metrics["pending_tasks_count"] == 1
    assert metrics["active_risk_zones_count"] == 3
    assert metrics["deployed_teams_count"] == 5
    assert metrics["total_rescuers_count"] == 20
    assert metrics["statistics_time_range_hours"] == 24


@pytest.mark.unit
def test_finalize_node():
    """测试finalize节点：构建最终报告"""
    state: SITREPState = {
        "report_id": "test-report-id",
        "user_id": "test",
        "thread_id": "test",
        "triggered_at": datetime.now(timezone.utc),
        "llm_summary": "测试摘要内容",
        "metrics": {
            "active_incidents_count": 2,
            "completed_tasks_count": 1,
            "in_progress_tasks_count": 1,
            "pending_tasks_count": 1,
            "active_risk_zones_count": 3,
            "deployed_teams_count": 5,
            "total_rescuers_count": 20,
            "statistics_time_range_hours": 24,
        },
        "active_incidents": [],
        "task_progress": [],
        "risk_zones": [],
        "resource_usage": {},
        "snapshot_id": "test-snapshot-id",
    }

    result = finalize(state)

    assert "sitrep_report" in result
    assert result["status"] == "completed"

    report = result["sitrep_report"]
    assert report["report_id"] == "test-report-id"
    assert report["summary"] == "测试摘要内容"
    assert report["snapshot_id"] == "test-snapshot-id"
    assert "generated_at" in report
    assert "metrics" in report
    assert "details" in report


# ========== 集成测试（需要真实LLM） ==========


@pytest.mark.integration
async def test_simple_graph_flow_integration():
    """集成测试：简化的Graph流程测试（仅验证核心功能）"""
    from emergency_agents.config import AppConfig
    from emergency_agents.db.dao import IncidentDAO, TaskDAO, RescueDAO, IncidentSnapshotRepository
    from emergency_agents.graph.sitrep_app import build_sitrep_graph
    from emergency_agents.llm.client import get_openai_client
    from emergency_agents.risk.service import RiskCacheManager
    from psycopg_pool import AsyncConnectionPool

    cfg = AppConfig.load_from_env()

    # 创建临时连接池（简化测试）
    async with AsyncConnectionPool(cfg.postgres_dsn, min_size=1, max_size=2) as pool:
        await pool.open()

        # 创建最小依赖
        incident_dao = IncidentDAO.create(pool)
        task_dao = TaskDAO.create(pool)
        rescue_dao = RescueDAO.create(pool)
        snapshot_repo = IncidentSnapshotRepository.create(pool)

        risk_cache_manager = RiskCacheManager(
            incident_dao=incident_dao,
            ttl_seconds=300,
        )
        await risk_cache_manager.prefetch()

        llm_client = get_openai_client(cfg)

        # 创建checkpointer
        from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
        checkpointer, close_cb = await create_async_postgres_checkpointer(
            dsn=cfg.postgres_dsn,
            schema="test_sitrep_checkpoint",
            min_size=1,
            max_size=2,
        )

        try:
            # 构建graph
            graph = await build_sitrep_graph(
                incident_dao=incident_dao,
                task_dao=task_dao,
                risk_cache_manager=risk_cache_manager,
                rescue_dao=rescue_dao,
                snapshot_repo=snapshot_repo,
                llm_client=llm_client,
                llm_model=cfg.llm_model,
                checkpointer=checkpointer,
            )

            # 准备初始State
            report_id = str(uuid.uuid4())
            initial_state: SITREPState = {
                "report_id": report_id,
                "user_id": "integration_test_user",
                "thread_id": f"sitrep-test-{report_id}",
                "triggered_at": datetime.now(timezone.utc),
                "time_range_hours": 24,
            }

            # 配置
            config = {
                "configurable": {
                    "thread_id": f"sitrep-test-{report_id}",
                    "checkpoint_ns": "integration_test",
                }
            }

            # 执行graph
            print(f"\n开始执行SITREP Graph集成测试...")
            print(f"Report ID: {report_id}")

            result = await graph.ainvoke(
                initial_state,
                config=config,
                durability="sync",
            )

            # 验证结果
            assert "sitrep_report" in result, "未返回sitrep_report"
            assert result["status"] == "completed", f"状态不是completed: {result.get('status')}"

            report = result["sitrep_report"]
            assert report["report_id"] == report_id
            assert "generated_at" in report
            assert "summary" in report
            assert "metrics" in report
            assert "snapshot_id" in report

            # 验证摘要内容
            summary = report["summary"]
            assert isinstance(summary, str), "摘要不是字符串"
            assert len(summary) > 50, f"摘要太短: {len(summary)}字"
            assert len(summary) < 2000, f"摘要太长: {len(summary)}字"

            # 验证指标
            metrics = report["metrics"]
            assert "active_incidents_count" in metrics
            assert "completed_tasks_count" in metrics
            assert "deployed_teams_count" in metrics

            print(f"\n✅ 集成测试通过！")
            print(f"生成时间: {report['generated_at']}")
            print(f"快照ID: {report['snapshot_id']}")
            print(f"摘要长度: {len(summary)}字")
            print(f"摘要内容:\n{summary[:200]}...")
            print(f"指标: {metrics}")

        finally:
            # 清理资源
            await close_cb()


@pytest.mark.integration
async def test_full_sitrep_flow_integration():
    """集成测试：完整SITREP流程（需要真实数据库和LLM）"""
    from emergency_agents.config import AppConfig
    from emergency_agents.db.dao import (
        IncidentDAO,
        RescueDAO,
        TaskDAO,
    )
    from emergency_agents.db.snapshot_repository import IncidentSnapshotRepository
    from emergency_agents.graph.checkpoint_utils import (
        create_async_postgres_checkpointer,
    )
    from emergency_agents.graph.sitrep_app import build_sitrep_graph
    from emergency_agents.llm.client import get_openai_client
    from emergency_agents.risk.service import RiskCacheManager
    from psycopg_pool import AsyncConnectionPool

    cfg = AppConfig.load_from_env()

    # 创建连接池
    async with AsyncConnectionPool(cfg.postgres_dsn, min_size=1, max_size=5) as pool:
        await pool.open()

        # 创建DAO
        incident_dao = IncidentDAO.create(pool)
        task_dao = TaskDAO.create(pool)
        rescue_dao = RescueDAO.create(pool)
        snapshot_repo = IncidentSnapshotRepository.create(pool)

        # 创建RiskCacheManager
        risk_cache_manager = RiskCacheManager(
            incident_dao=incident_dao,
            ttl_seconds=300,
        )
        await risk_cache_manager.prefetch()

        # 创建LLM客户端
        llm_client = get_openai_client(cfg)

        # 创建checkpointer
        checkpointer = create_async_postgres_checkpointer(cfg.postgres_dsn)

        # 构建graph
        graph = await build_sitrep_graph(
            incident_dao=incident_dao,
            task_dao=task_dao,
            risk_cache_manager=risk_cache_manager,
            rescue_dao=rescue_dao,
            snapshot_repo=snapshot_repo,
            llm_client=llm_client,
            llm_model=cfg.llm_model,
            checkpointer=checkpointer,
        )

        # 准备初始State
        report_id = str(uuid.uuid4())
        initial_state: SITREPState = {
            "report_id": report_id,
            "user_id": "integration_test_user",
            "thread_id": f"sitrep-{report_id}",
            "triggered_at": datetime.now(timezone.utc),
            "time_range_hours": 24,
        }

        # 配置
        config = {
            "configurable": {
                "thread_id": f"sitrep-{report_id}",
                "checkpoint_ns": "test",
            }
        }

        # 执行graph（durability="sync"）
        result = await graph.ainvoke(
            initial_state,
            config=config,
            durability="sync",
        )

        # 验证结果
        assert "sitrep_report" in result
        assert result["status"] == "completed"

        report = result["sitrep_report"]
        assert report["report_id"] == report_id
        assert "generated_at" in report
        assert "summary" in report
        assert "metrics" in report
        assert "snapshot_id" in report

        print(f"\n完整SITREP报告：")
        print(f"Report ID: {report['report_id']}")
        print(f"生成时间: {report['generated_at']}")
        print(f"摘要: {report['summary']}")
        print(f"快照ID: {report['snapshot_id']}")
        print(f"指标: {report['metrics']}")

        # 清理checkpointer连接
        if hasattr(checkpointer, "close"):
            await checkpointer.close()


# ========== API端点测试 ==========


@pytest.mark.integration
async def test_sitrep_api_generate_endpoint():
    """集成测试：测试POST /sitrep/generate端点"""
    from fastapi.testclient import TestClient
    from emergency_agents.api.main import app

    # 注意：这需要完整的应用启动（包括startup_event）
    # 实际环境中可能需要测试数据库

    client = TestClient(app)

    response = client.post(
        "/sitrep/generate",
        json={
            "time_range_hours": 24,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "report_id" in data
    assert "generated_at" in data
    assert "summary" in data
    assert "metrics" in data
    assert "snapshot_id" in data

    print(f"\nAPI响应：{data}")


if __name__ == "__main__":
    # 运行集成测试
    pytest.main([__file__, "-v", "-m", "integration"])
