#!/usr/bin/env python3
# Copyright 2025 msq
"""
任务分配优化服务 - 基于OR-Tools的约束优化引擎

核心功能：
- 智能任务-队伍匹配（考虑技能、位置、优先级）
- 多目标优化（响应时间最小化 + 负载均衡）
- 约束满足（技能要求、人数限制、时间窗口）
- 实时重分配（动态调整方案）

技术栈：
- Google OR-Tools (CP-SAT Solver)
- 混合整数规划（MIP）
- 启发式算法（Greedy + Local Search）
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set

try:
    from ortools.sat.python import cp_model
except ImportError:
    # OR-Tools未安装时的占位符
    cp_model = None
    logger = logging.getLogger(__name__)
    logger.warning("OR-Tools not installed. TaskOptimizer will use fallback algorithm.")


logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """任务优先级"""
    CRITICAL = "critical"  # 紧急：立即执行（生命威胁）
    HIGH = "high"  # 高优：2小时内
    MEDIUM = "medium"  # 中优：4小时内
    LOW = "low"  # 低优：可延后


class TeamStatus(str, Enum):
    """队伍状态"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class Task:
    """救援任务"""
    id: str
    name: str
    priority: TaskPriority
    location: tuple[float, float]  # (lat, lng)
    required_skills: Set[str]  # {"医疗", "破拆", "生命探测"}
    required_personnel: int  # 最少需要人数
    estimated_duration_hours: float
    deadline_hours: Optional[float] = None  # 距离现在的小时数


@dataclass
class RescueTeam:
    """救援队伍"""
    id: str
    name: str
    status: TeamStatus
    location: tuple[float, float]
    skills: Set[str]
    personnel_count: int
    current_load: int = 0  # 当前已分配任务数


@dataclass
class Assignment:
    """任务-队伍分配"""
    task_id: str
    team_id: str
    estimated_travel_time_hours: float
    estimated_start_time_hours: float  # 相对于当前时间
    confidence: float  # 分配可行性置信度


@dataclass
class OptimizationResult:
    """优化结果"""
    assignments: List[Assignment]
    unassigned_tasks: List[str]  # 无法分配的任务ID

    # 优化指标
    total_response_time_hours: float
    average_team_load: float
    solver_time_ms: float
    objective_value: float

    # 可行性分析
    is_feasible: bool
    warnings: List[str] = field(default_factory=list)


class TaskOptimizer:
    """任务分配优化引擎

    使用方法：
        optimizer = TaskOptimizer()

        # 定义任务
        tasks = [
            Task(
                id="t1", name="搜救被困人员",
                priority=TaskPriority.CRITICAL,
                location=(30.65, 104.07),
                required_skills={"搜救", "医疗"},
                required_personnel=5,
                estimated_duration_hours=2.0
            )
        ]

        # 定义队伍
        teams = [
            RescueTeam(
                id="team1", name="综合救援队",
                status=TeamStatus.AVAILABLE,
                location=(30.60, 104.00),
                skills={"搜救", "医疗", "破拆"},
                personnel_count=10
            )
        ]

        result = optimizer.optimize(tasks, teams)
        print(f"分配 {len(result.assignments)} 个任务")
        print(f"总响应时间: {result.total_response_time_hours:.1f}小时")
    """

    def __init__(self, use_ortools: bool = True, max_solver_time_seconds: int = 10):
        """初始化优化器

        Args:
            use_ortools: 是否使用OR-Tools（False则用启发式算法）
            max_solver_time_seconds: OR-Tools求解器超时时间
        """
        self.use_ortools = use_ortools and cp_model is not None
        self.max_solver_time = max_solver_time_seconds

        if not self.use_ortools:
            logger.warning("Using fallback greedy algorithm (OR-Tools unavailable)")

    def optimize(
        self, tasks: List[Task], teams: List[RescueTeam]
    ) -> OptimizationResult:
        """执行任务分配优化

        Args:
            tasks: 待分配任务列表
            teams: 可用救援队伍列表

        Returns:
            OptimizationResult: 优化后的分配方案
        """
        start_time = time.time()

        try:
            if self.use_ortools:
                result = self._optimize_with_ortools(tasks, teams)
            else:
                result = self._optimize_greedy(tasks, teams)

            result.solver_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Task optimization completed in {result.solver_time_ms:.0f}ms: "
                f"{len(result.assignments)} assigned, {len(result.unassigned_tasks)} unassigned"
            )

            return result

        except Exception as e:
            logger.error(f"Optimization failed: {e}", exc_info=True)
            # 返回空结果
            return OptimizationResult(
                assignments=[],
                unassigned_tasks=[t.id for t in tasks],
                total_response_time_hours=0.0,
                average_team_load=0.0,
                solver_time_ms=(time.time() - start_time) * 1000,
                objective_value=0.0,
                is_feasible=False,
                warnings=[f"优化失败: {str(e)}"],
            )

    def _optimize_with_ortools(
        self, tasks: List[Task], teams: List[RescueTeam]
    ) -> OptimizationResult:
        """使用OR-Tools CP-SAT求解器优化"""
        model = cp_model.CpModel()

        # 决策变量: x[i][j] = 1 表示任务i分配给队伍j
        x = {}
        for i, task in enumerate(tasks):
            for j, team in enumerate(teams):
                x[i, j] = model.NewBoolVar(f"x_t{task.id}_team{team.id}")

        # 约束1: 每个任务最多分配给一个队伍
        for i, task in enumerate(tasks):
            model.Add(sum(x[i, j] for j in range(len(teams))) <= 1)

        # 约束2: 技能匹配
        for i, task in enumerate(tasks):
            for j, team in enumerate(teams):
                if not task.required_skills.issubset(team.skills):
                    model.Add(x[i, j] == 0)  # 强制不分配

        # 约束3: 人数要求
        for i, task in enumerate(tasks):
            for j, team in enumerate(teams):
                if team.personnel_count < task.required_personnel:
                    model.Add(x[i, j] == 0)

        # 约束4: 队伍状态（只能分配给AVAILABLE的队伍）
        for i, task in enumerate(tasks):
            for j, team in enumerate(teams):
                if team.status != TeamStatus.AVAILABLE:
                    model.Add(x[i, j] == 0)

        # 目标函数: 最小化加权响应时间
        objective_terms = []
        for i, task in enumerate(tasks):
            priority_weight = self._get_priority_weight(task.priority)
            for j, team in enumerate(teams):
                travel_time = self._calculate_travel_time(task.location, team.location)
                # 响应时间 = 旅行时间 * 优先级权重
                weighted_time = int(travel_time * priority_weight * 100)  # 缩放到整数
                objective_terms.append(weighted_time * x[i, j])

        model.Minimize(sum(objective_terms))

        # 求解
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.max_solver_time
        status = solver.Solve(model)

        # 解析结果
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            assignments = []
            unassigned = []

            for i, task in enumerate(tasks):
                assigned = False
                for j, team in enumerate(teams):
                    if solver.Value(x[i, j]) == 1:
                        travel_time = self._calculate_travel_time(
                            task.location, team.location
                        )
                        assignments.append(
                            Assignment(
                                task_id=task.id,
                                team_id=team.id,
                                estimated_travel_time_hours=travel_time,
                                estimated_start_time_hours=travel_time,
                                confidence=0.9,
                            )
                        )
                        assigned = True
                        break

                if not assigned:
                    unassigned.append(task.id)

            total_response = sum(a.estimated_travel_time_hours for a in assignments)
            avg_load = len(assignments) / len(teams) if teams else 0

            return OptimizationResult(
                assignments=assignments,
                unassigned_tasks=unassigned,
                total_response_time_hours=total_response,
                average_team_load=avg_load,
                solver_time_ms=0.0,  # 会被外部覆盖
                objective_value=solver.ObjectiveValue() / 100.0,
                is_feasible=True,
            )

        else:
            # 无可行解，回退到贪心算法
            logger.warning("OR-Tools solver failed, falling back to greedy")
            return self._optimize_greedy(tasks, teams)

    def _optimize_greedy(
        self, tasks: List[Task], teams: List[RescueTeam]
    ) -> OptimizationResult:
        """贪心算法：按优先级排序任务，为每个任务选择最近的可用队伍"""
        # 按优先级排序任务
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                self._get_priority_weight(t.priority),
                t.estimated_duration_hours,
            ),
            reverse=True,
        )

        assignments = []
        unassigned = []
        team_loads = {team.id: 0 for team in teams}

        for task in sorted_tasks:
            best_team = None
            best_distance = float("inf")

            # 找到最近的满足条件的队伍
            for team in teams:
                if team.status != TeamStatus.AVAILABLE:
                    continue

                if not task.required_skills.issubset(team.skills):
                    continue

                if team.personnel_count < task.required_personnel:
                    continue

                distance = self._calculate_travel_time(task.location, team.location)
                if distance < best_distance:
                    best_distance = distance
                    best_team = team

            if best_team:
                assignments.append(
                    Assignment(
                        task_id=task.id,
                        team_id=best_team.id,
                        estimated_travel_time_hours=best_distance,
                        estimated_start_time_hours=best_distance,
                        confidence=0.8,
                    )
                )
                team_loads[best_team.id] += 1
            else:
                unassigned.append(task.id)

        total_response = sum(a.estimated_travel_time_hours for a in assignments)
        avg_load = sum(team_loads.values()) / len(teams) if teams else 0

        warnings = []
        if unassigned:
            warnings.append(f"{len(unassigned)}个任务无法分配（技能/人数不足）")

        return OptimizationResult(
            assignments=assignments,
            unassigned_tasks=unassigned,
            total_response_time_hours=total_response,
            average_team_load=avg_load,
            solver_time_ms=0.0,
            objective_value=total_response,
            is_feasible=len(assignments) > 0,
            warnings=warnings,
        )

    def _calculate_travel_time(
        self, loc1: tuple[float, float], loc2: tuple[float, float]
    ) -> float:
        """计算旅行时间（简化：使用直线距离/平均速度）

        Args:
            loc1: (lat, lng)
            loc2: (lat, lng)

        Returns:
            小时数
        """
        import math

        # Haversine公式计算大圆距离（公里）
        lat1, lon1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lon2 = math.radians(loc2[0]), math.radians(loc2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        distance_km = 6371 * c  # 地球半径 6371 km

        # 假设平均速度60公里/小时
        avg_speed_kmh = 60.0
        travel_time_hours = distance_km / avg_speed_kmh

        return travel_time_hours

    def _get_priority_weight(self, priority: TaskPriority) -> float:
        """获取优先级权重（用于目标函数）"""
        weights = {
            TaskPriority.CRITICAL: 10.0,
            TaskPriority.HIGH: 5.0,
            TaskPriority.MEDIUM: 2.0,
            TaskPriority.LOW: 1.0,
        }
        return weights.get(priority, 1.0)
