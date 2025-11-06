"""系统数据统一查询Handler测试

测试基于ToolNode模式的统一数据查询功能。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from emergency_agents.db.models import (
    CarriedDevice,
    DeviceSummary,
    TaskSummary,
    EventLocation,
    EntityLocation,
    PoiLocation,
)
from emergency_agents.intent.handlers.system_data_query import SystemDataQueryHandler
from emergency_agents.intent.schemas import SystemDataQuerySlots
from emergency_agents.graph.system_data_query_node import SystemDataQueryNode


@pytest.mark.unit
class TestSystemDataQueryHandler:
    """SystemDataQueryHandler单元测试"""

    @pytest.fixture
    def mock_daos(self):
        """创建mock DAO对象"""
        device_dao = MagicMock()
        task_dao = MagicMock()
        event_dao = MagicMock()
        poi_dao = MagicMock()
        rescuer_dao = MagicMock()

        return {
            "device_dao": device_dao,
            "task_dao": task_dao,
            "event_dao": event_dao,
            "poi_dao": poi_dao,
            "rescuer_dao": rescuer_dao,
        }

    @pytest.fixture
    def handler(self, mock_daos):
        """创建handler实例"""
        return SystemDataQueryHandler(
            device_dao=mock_daos["device_dao"],
            task_dao=mock_daos["task_dao"],
            event_dao=mock_daos["event_dao"],
            poi_dao=mock_daos["poi_dao"],
            rescuer_dao=mock_daos["rescuer_dao"],
        )

    @pytest.mark.asyncio
    async def test_query_carried_devices_success(self, handler, mock_daos):
        """测试查询携带设备 - 成功"""
        # 准备mock数据
        mock_devices = [
            CarriedDevice(name="无人机A", weather_capability="全天候飞行，抗7级风"),
            CarriedDevice(name="机器狗01", weather_capability="防水防尘，适合复杂地形"),
            CarriedDevice(name="热成像仪", weather_capability="夜间和烟雾环境可用"),
        ]
        mock_daos["device_dao"].fetch_carried_devices = AsyncMock(return_value=mock_devices)

        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="carried_devices"
        )

        # 执行查询
        state = {"thread_id": "test-001", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert result["query_type"] == "carried_devices"
        assert "车载携带设备清单（共3台）" in result["response_text"]
        assert "无人机A：全天候飞行" in result["response_text"]
        assert "机器狗01：防水防尘" in result["response_text"]
        assert len(result["query_result"]) == 3
        assert result["query_result"][0]["name"] == "无人机A"

        # 验证mock调用
        mock_daos["device_dao"].fetch_carried_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_carried_devices_empty(self, handler, mock_daos):
        """测试查询携带设备 - 无设备"""
        # 准备空数据
        mock_daos["device_dao"].fetch_carried_devices = AsyncMock(return_value=[])

        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="carried_devices"
        )

        # 执行查询
        state = {"thread_id": "test-002", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert result["response_text"] == "当前没有车载携带的设备"
        assert result["query_result"] == []

    @pytest.mark.asyncio
    async def test_query_device_by_name_success(self, handler, mock_daos):
        """测试按名称查询设备 - 成功"""
        # 准备mock数据
        mock_device = DeviceSummary(
            id="UAV-001",
            device_type="uav",
            name="无人机A"
        )
        mock_daos["device_dao"].fetch_device_by_name = AsyncMock(return_value=mock_device)

        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="device_by_name",
            query_params={"device_name": "无人机A"}
        )

        # 执行查询
        state = {"thread_id": "test-003", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert result["query_type"] == "device_by_name"
        assert "设备 无人机A（编号 UAV-001）记录在案" in result["response_text"]
        assert result["query_result"]["id"] == "UAV-001"
        assert result["query_result"]["name"] == "无人机A"

        # 验证mock调用
        mock_daos["device_dao"].fetch_device_by_name.assert_called_once_with("无人机A")

    @pytest.mark.asyncio
    async def test_query_device_by_name_not_found(self, handler, mock_daos):
        """测试按名称查询设备 - 未找到"""
        # 准备空数据
        mock_daos["device_dao"].fetch_device_by_name = AsyncMock(return_value=None)

        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="device_by_name",
            query_params={"device_name": "不存在的设备"}
        )

        # 执行查询
        state = {"thread_id": "test-004", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert "未找到名称为 不存在的设备 的设备" in result["response_text"]
        assert result["query_result"] is None

    @pytest.mark.asyncio
    async def test_query_task_progress_success(self, handler, mock_daos):
        """测试查询任务进度 - 成功"""
        # 准备mock数据
        from datetime import datetime
        mock_task = TaskSummary(
            id="TASK-001",
            code="RESCUE-20250106-001",
            description="搜救被困人员",
            status="executing",
            progress=75,
            updated_at=datetime(2025, 1, 6, 15, 30, 0)
        )
        mock_daos["task_dao"].fetch_task_summary = AsyncMock(return_value=mock_task)

        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="task_progress",
            query_params={"task_id": "TASK-001"}
        )

        # 执行查询
        state = {"thread_id": "test-005", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert "任务 RESCUE-20250106-001 进度: 75%" in result["response_text"]
        assert result["query_result"]["progress"] == 75
        assert result["query_result"]["status"] == "executing"

        # 验证mock调用
        mock_daos["task_dao"].fetch_task_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_event_location_success(self, handler, mock_daos):
        """测试查询事件位置 - 成功"""
        # 准备mock数据
        mock_location = EventLocation(
            name="火灾现场",
            lng=121.5,
            lat=31.2
        )
        mock_daos["event_dao"].fetch_event_location = AsyncMock(return_value=mock_location)

        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="event_location",
            query_params={"event_id": "EVT-001"}
        )

        # 执行查询
        state = {"thread_id": "test-006", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert "事件 火灾现场 位置: (31.2, 121.5)" in result["response_text"]
        assert result["query_result"]["lat"] == 31.2
        assert result["query_result"]["lng"] == 121.5

    @pytest.mark.asyncio
    async def test_unsupported_query_type(self, handler):
        """测试不支持的查询类型"""
        # 准备槽位
        slots = SystemDataQuerySlots(
            query_type="unknown_query"
        )

        # 执行查询
        state = {"thread_id": "test-007", "user_id": "user-123"}
        result = await handler.handle(slots, state)

        # 验证结果
        assert "不支持的查询类型: unknown_query" in result["response_text"]
        assert result["error"] is True
        assert result["query_result"] is None


@pytest.mark.unit
class TestSystemDataQueryNode:
    """SystemDataQueryNode单元测试"""

    @pytest.fixture
    def mock_daos(self):
        """创建mock DAO对象"""
        device_dao = MagicMock()
        task_dao = MagicMock()
        event_dao = MagicMock()
        poi_dao = MagicMock()
        rescuer_dao = MagicMock()

        # 设置默认的异步mock
        device_dao.fetch_carried_devices = AsyncMock(return_value=[])
        device_dao.fetch_device_by_name = AsyncMock(return_value=None)
        device_dao.fetch_device_by_id = AsyncMock(return_value=None)
        task_dao.fetch_task_summary = AsyncMock(return_value=None)
        task_dao.fetch_task_latest_log = AsyncMock(return_value=None)
        task_dao.fetch_task_route_plan = AsyncMock(return_value=None)
        event_dao.fetch_event_location = AsyncMock(return_value=None)
        poi_dao.fetch_poi_location = AsyncMock(return_value=None)
        rescuer_dao.fetch_team_location = AsyncMock(return_value=None)

        return {
            "device_dao": device_dao,
            "task_dao": task_dao,
            "event_dao": event_dao,
            "poi_dao": poi_dao,
            "rescuer_dao": rescuer_dao,
        }

    @pytest.fixture
    def query_node(self, mock_daos):
        """创建查询节点实例"""
        return SystemDataQueryNode(
            device_dao=mock_daos["device_dao"],
            task_dao=mock_daos["task_dao"],
            event_dao=mock_daos["event_dao"],
            poi_dao=mock_daos["poi_dao"],
            rescuer_dao=mock_daos["rescuer_dao"],
        )

    @pytest.mark.asyncio
    async def test_execute_with_empty_query_type(self, query_node):
        """测试空查询类型"""
        result = await query_node.execute("", {})

        assert result["success"] is False
        assert result["message"] == "查询类型不能为空"
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_execute_with_invalid_query_type(self, query_node):
        """测试无效查询类型"""
        result = await query_node.execute("invalid_type", {})

        assert result["success"] is False
        assert "不支持的查询类型: invalid_type" in result["message"]
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_execute_carried_devices(self, query_node, mock_daos):
        """测试执行携带设备查询"""
        # 准备mock数据
        mock_devices = [
            CarriedDevice(name="设备1", weather_capability="能力1"),
            CarriedDevice(name="设备2", weather_capability="能力2"),
        ]
        mock_daos["device_dao"].fetch_carried_devices = AsyncMock(return_value=mock_devices)

        # 执行查询
        result = await query_node.execute("carried_devices", None)

        # 验证结果
        assert result["success"] is True
        assert "车载携带设备清单（共2台）" in result["message"]
        assert len(result["data"]) == 2
        assert result["query_type"] == "carried_devices"
        assert result["elapsed_ms"] >= 0

    @pytest.mark.asyncio
    async def test_execute_with_exception(self, query_node, mock_daos):
        """测试执行过程中的异常处理"""
        # 模拟异常
        mock_daos["device_dao"].fetch_carried_devices = AsyncMock(
            side_effect=Exception("数据库连接失败")
        )

        # 执行查询
        result = await query_node.execute("carried_devices", None)

        # 验证结果
        assert result["success"] is False
        assert "查询失败: 数据库连接失败" in result["message"]
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_query_poi_location(self, query_node, mock_daos):
        """测试POI位置查询"""
        # 准备mock数据
        mock_location = PoiLocation(
            name="避难所A",
            lng=121.45,
            lat=31.23
        )
        mock_daos["poi_dao"].fetch_poi_location = AsyncMock(return_value=mock_location)

        # 执行查询
        result = await query_node.execute(
            "poi_location",
            {"poi_name": "避难所A"}
        )

        # 验证结果
        assert result["success"] is True
        assert "POI 避难所A 位置: (31.23, 121.45)" in result["message"]
        assert result["data"]["name"] == "避难所A"
        assert result["data"]["lat"] == 31.23
        assert result["data"]["lng"] == 121.45


@pytest.mark.unit
class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_query_performance(self):
        """测试查询性能 - 确保响应时间小于100ms"""
        import time

        # 创建mock DAO（快速返回）
        device_dao = MagicMock()
        device_dao.fetch_carried_devices = AsyncMock(return_value=[
            CarriedDevice(name=f"设备{i}", weather_capability=f"能力{i}")
            for i in range(10)
        ])

        # 创建节点
        query_node = SystemDataQueryNode(
            device_dao=device_dao,
            task_dao=MagicMock(),
            event_dao=MagicMock(),
            poi_dao=MagicMock(),
            rescuer_dao=MagicMock(),
        )

        # 执行查询并计时
        start = time.perf_counter()
        result = await query_node.execute("carried_devices", None)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 验证性能
        assert result["success"] is True
        assert elapsed_ms < 100  # 应该在100ms内完成
        assert result["elapsed_ms"] < 100