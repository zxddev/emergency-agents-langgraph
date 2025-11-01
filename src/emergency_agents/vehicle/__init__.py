#!/usr/bin/env python3
# Copyright 2025 msq
"""
车载指挥模块

三大核心功能：
1. 视觉分析 (vision.py) - GLM-4V无人机图像分析
2. 装备推荐 (equipment.py) - RAG+KG混合推理
3. 任务优化 (task_optimizer.py) - OR-Tools智能分配
"""
from __future__ import annotations

from emergency_agents.vehicle.vision import VisionAnalyzer, DangerLevel, VisionAnalysisResult
from emergency_agents.vehicle.equipment import EquipmentRecommender, EquipmentRecommendation
from emergency_agents.vehicle.task_optimizer import (
    TaskOptimizer,
    Task,
    RescueTeam,
    OptimizationResult,
    TaskPriority,
    TeamStatus,
)

__all__ = [
    "VisionAnalyzer",
    "VisionAnalysisResult",
    "DangerLevel",
    "EquipmentRecommender",
    "EquipmentRecommendation",
    "TaskOptimizer",
    "Task",
    "RescueTeam",
    "OptimizationResult",
    "TaskPriority",
    "TeamStatus",
]
