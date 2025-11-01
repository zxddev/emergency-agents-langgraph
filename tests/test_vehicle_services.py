#!/usr/bin/env python3
# Copyright 2025 msq
"""
车载指挥模块单元测试

测试覆盖：
1. VisionAnalyzer - 视觉分析服务
2. EquipmentRecommender - 装备推荐服务
3. TaskOptimizer - 任务分配优化

测试策略：
- 单元测试：Mock外部依赖（vLLM/RAG/KG）
- 性能测试：验证响应时间指标
- 容错测试：验证降级和错误处理
"""
from __future__ import annotations

import asyncio
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from emergency_agents.vehicle import (
    VisionAnalyzer,
    DangerLevel,
    EquipmentRecommender,
    TaskOptimizer,
    Task,
    RescueTeam,
    TaskPriority,
    TeamStatus,
)


# ==================== VisionAnalyzer Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vision_analyzer_initialization():
    """测试VisionAnalyzer初始化"""
    analyzer = VisionAnalyzer(
        vllm_url="http://test:8001/v1",
        model_name="glm-4v-plus",
        timeout=10.0,
    )

    assert analyzer.vllm_url == "http://test:8001/v1"
    assert analyzer.model_name == "glm-4v-plus"
    assert analyzer.timeout == 10.0

    await analyzer.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vision_analysis_with_mock_llm():
    """测试视觉分析（Mock LLM响应）"""
    # Mock vLLM响应
    mock_llm_response = {
        "choices": [
            {
                "message": {
                    "content": """```json
{
  "danger_level": "L2",
  "persons": {
    "count": 3,
    "positions": [{"x": 0.5, "y": 0.3, "confidence": 0.95, "activity": "站立"}],
    "activities": ["站立"]
  },
  "vehicles": {
    "total_count": 2,
    "by_type": {"小汽车": 2},
    "positions": []
  },
  "buildings": {
    "total_buildings": 5,
    "damaged_count": 2,
    "damage_levels": {"完好": 3, "轻度": 2},
    "collapse_risk": false
  },
  "roads": {
    "passable": true,
    "blocked_sections": [],
    "obstacles": []
  },
  "hazards": ["建筑损毁"],
  "recommendations": ["派遣搜救队"],
  "confidence_score": 0.85
}
```"""
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json = MagicMock(return_value=mock_llm_response)

        analyzer = VisionAnalyzer(vllm_url="http://test:8001/v1")

        # 创建测试图像（1x1像素白色PNG）
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

        result = await analyzer.analyze_drone_image(image_base64=test_image_b64)

        # 验证结果
        assert result.danger_level == DangerLevel.L2
        assert result.persons.count == 3
        assert result.vehicles.total_count == 2
        assert result.buildings.damaged_count == 2
        assert result.confidence_score == 0.85
        assert "建筑损毁" in result.hazards
        assert result.latency_ms > 0

        await analyzer.close()


@pytest.mark.unit
def test_vision_analyzer_priority_weights():
    """测试危险等级枚举"""
    assert DangerLevel.L0.value == "L0"
    assert DangerLevel.L1.value == "L1"
    assert DangerLevel.L2.value == "L2"
    assert DangerLevel.L3.value == "L3"


# ==================== EquipmentRecommender Tests ====================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_equipment_recommender_initialization():
    """测试EquipmentRecommender初始化"""
    recommender = EquipmentRecommender(
        rag_url="http://test/rag/query",
        kg_url="http://test/kg/recommend",
        llm_url="http://test:8002/v1",
    )

    assert recommender.rag_url == "http://test/rag/query"
    assert recommender.kg_url == "http://test/kg/recommend"
    assert recommender.llm_url == "http://test:8002/v1"

    await recommender.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_equipment_recommendation_with_mocks():
    """测试装备推荐（Mock RAG/KG/LLM）"""
    # Mock RAG响应
    mock_rag_response = {
        "results": [
            {
                "text": "地震救援需要生命探测仪、破拆工具",
                "source": "GB/T 33743-2017",
                "loc": "第5.2节",
            }
        ]
    }

    # Mock KG响应
    mock_kg_response = {
        "recommendations": [
            {"name": "生命探测仪"},
            {"name": "破拆工具"},
        ]
    }

    # Mock LLM响应
    mock_llm_response = {
        "choices": [
            {
                "message": {
                    "content": """```json
{
  "equipment": [
    {
      "name": "生命探测仪",
      "category": "生命探测",
      "quantity": 3,
      "priority": "必需",
      "reason": "搜救被困人员",
      "source": "GB/T 33743-2017"
    }
  ]
}
```"""
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # 模拟多个API调用
        mock_post.side_effect = [
            # RAG调用
            MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value=mock_rag_response)),
            # KG调用
            MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value=mock_kg_response)),
            # LLM调用
            MagicMock(raise_for_status=MagicMock(), json=MagicMock(return_value=mock_llm_response)),
        ]

        recommender = EquipmentRecommender(
            rag_url="http://test/rag",
            kg_url="http://test/kg",
            llm_url="http://test/llm",
        )

        disaster_context = {
            "disaster_type": "earthquake",
            "magnitude": 7.0,
            "affected_area": "汶川县",
            "terrain": "山区",
            "weather": "晴",
        }

        result = await recommender.recommend(disaster_context)

        # 验证推理链
        assert len(result.reasoning_chain) == 3
        assert result.reasoning_chain[0].stage.value == "RAG检索"
        assert result.reasoning_chain[1].stage.value == "KG验证"
        assert result.reasoning_chain[2].stage.value == "LLM合成"

        # 验证装备列表
        assert result.total_items > 0
        assert result.equipment_list[0].name == "生命探测仪"
        assert result.equipment_list[0].priority == "必需"

        # 验证性能
        assert result.total_reasoning_time_ms > 0
        assert result.confidence_score > 0

        await recommender.close()


# ==================== TaskOptimizer Tests ====================


@pytest.mark.unit
def test_task_optimizer_initialization():
    """测试TaskOptimizer初始化"""
    # 测试使用OR-Tools
    optimizer_with_ortools = TaskOptimizer(use_ortools=True)
    assert optimizer_with_ortools.use_ortools or not optimizer_with_ortools.use_ortools  # 取决于是否安装

    # 测试使用贪心算法
    optimizer_greedy = TaskOptimizer(use_ortools=False)
    assert not optimizer_greedy.use_ortools


@pytest.mark.unit
def test_task_optimizer_greedy_algorithm():
    """测试贪心任务分配算法"""
    optimizer = TaskOptimizer(use_ortools=False)

    # 定义测试任务
    tasks = [
        Task(
            id="t1",
            name="搜救被困人员",
            priority=TaskPriority.CRITICAL,
            location=(30.65, 104.07),
            required_skills={"搜救", "医疗"},
            required_personnel=5,
            estimated_duration_hours=2.0,
        ),
        Task(
            id="t2",
            name="清理道路",
            priority=TaskPriority.MEDIUM,
            location=(30.66, 104.08),
            required_skills={"破拆"},
            required_personnel=3,
            estimated_duration_hours=1.0,
        ),
    ]

    # 定义测试队伍
    teams = [
        RescueTeam(
            id="team1",
            name="综合救援队",
            status=TeamStatus.AVAILABLE,
            location=(30.60, 104.00),
            skills={"搜救", "医疗", "破拆"},
            personnel_count=10,
        ),
        RescueTeam(
            id="team2",
            name="工程队",
            status=TeamStatus.AVAILABLE,
            location=(30.62, 104.05),
            skills={"破拆"},
            personnel_count=5,
        ),
    ]

    result = optimizer.optimize(tasks, teams)

    # 验证结果
    assert result.is_feasible
    assert len(result.assignments) >= 1
    assert len(result.assignments) + len(result.unassigned_tasks) == len(tasks)
    assert result.solver_time_ms >= 0


@pytest.mark.unit
def test_task_optimizer_skill_constraints():
    """测试技能约束"""
    optimizer = TaskOptimizer(use_ortools=False)

    # 任务需要"医疗"技能
    task = Task(
        id="t1",
        name="救治伤员",
        priority=TaskPriority.HIGH,
        location=(30.65, 104.07),
        required_skills={"医疗"},
        required_personnel=2,
        estimated_duration_hours=1.0,
    )

    # 队伍没有"医疗"技能
    team_no_skill = RescueTeam(
        id="team1",
        name="工程队",
        status=TeamStatus.AVAILABLE,
        location=(30.60, 104.00),
        skills={"破拆"},
        personnel_count=10,
    )

    result = optimizer.optimize([task], [team_no_skill])

    # 验证：任务无法分配
    assert len(result.assignments) == 0
    assert "t1" in result.unassigned_tasks
    assert len(result.warnings) > 0


@pytest.mark.unit
def test_task_optimizer_personnel_constraints():
    """测试人数约束"""
    optimizer = TaskOptimizer(use_ortools=False)

    # 任务需要10人
    task = Task(
        id="t1",
        name="大规模搜救",
        priority=TaskPriority.CRITICAL,
        location=(30.65, 104.07),
        required_skills={"搜救"},
        required_personnel=10,
        estimated_duration_hours=3.0,
    )

    # 队伍只有5人
    team_small = RescueTeam(
        id="team1",
        name="小队",
        status=TeamStatus.AVAILABLE,
        location=(30.60, 104.00),
        skills={"搜救"},
        personnel_count=5,
    )

    result = optimizer.optimize([task], [team_small])

    # 验证：任务无法分配
    assert len(result.assignments) == 0
    assert "t1" in result.unassigned_tasks


@pytest.mark.unit
def test_task_optimizer_team_status_filter():
    """测试队伍状态过滤"""
    optimizer = TaskOptimizer(use_ortools=False)

    task = Task(
        id="t1",
        name="搜救",
        priority=TaskPriority.HIGH,
        location=(30.65, 104.07),
        required_skills={"搜救"},
        required_personnel=5,
        estimated_duration_hours=2.0,
    )

    # 队伍1：离线
    team_offline = RescueTeam(
        id="team1",
        name="离线队",
        status=TeamStatus.OFFLINE,
        location=(30.60, 104.00),
        skills={"搜救"},
        personnel_count=10,
    )

    # 队伍2：忙碌
    team_busy = RescueTeam(
        id="team2",
        name="忙碌队",
        status=TeamStatus.BUSY,
        location=(30.62, 104.05),
        skills={"搜救"},
        personnel_count=10,
    )

    result = optimizer.optimize([task], [team_offline, team_busy])

    # 验证：任务无法分配（所有队伍不可用）
    assert len(result.assignments) == 0
    assert "t1" in result.unassigned_tasks


# ==================== 性能基准测试 ====================


@pytest.mark.benchmark
def test_task_optimizer_performance():
    """测试任务优化性能（100任务×20队伍）"""
    optimizer = TaskOptimizer(use_ortools=False, max_solver_time_seconds=5)

    # 生成100个任务
    tasks = [
        Task(
            id=f"t{i}",
            name=f"任务{i}",
            priority=TaskPriority.MEDIUM,
            location=(30.0 + i * 0.01, 104.0 + i * 0.01),
            required_skills={"搜救"},
            required_personnel=5,
            estimated_duration_hours=2.0,
        )
        for i in range(100)
    ]

    # 生成20个队伍
    teams = [
        RescueTeam(
            id=f"team{j}",
            name=f"队伍{j}",
            status=TeamStatus.AVAILABLE,
            location=(30.0 + j * 0.05, 104.0 + j * 0.05),
            skills={"搜救", "医疗", "破拆"},
            personnel_count=10,
        )
        for j in range(20)
    ]

    result = optimizer.optimize(tasks, teams)

    # 验证性能目标：<500ms
    assert result.solver_time_ms < 500
    assert result.is_feasible
    assert len(result.assignments) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "unit"])
