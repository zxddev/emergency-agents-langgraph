#!/usr/bin/env python3
# Copyright 2025 msq
"""
车载指挥API路由

提供三大核心服务：
1. /vehicle/vision/analyze - 无人机图像视觉分析
2. /vehicle/equipment/recommend - 装备智能推荐
3. /vehicle/task/allocate - 任务分配优化

技术特点：
- 异步非阻塞（FastAPI async）
- 请求trace_id追踪
- Prometheus性能监控
- 错误降级处理
"""
from __future__ import annotations

import uuid
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram

from emergency_agents.vehicle.vision import VisionAnalyzer, DangerLevel
from emergency_agents.vehicle.equipment import EquipmentRecommender, DisasterType
from emergency_agents.vehicle.task_optimizer import (
    TaskOptimizer,
    Task,
    RescueTeam,
    TaskPriority,
    TeamStatus,
)

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/vehicle", tags=["vehicle"])

# Prometheus监控指标
_vision_counter = Counter("vehicle_vision_analysis_total", "Total vision analysis requests")
_vision_latency = Histogram("vehicle_vision_analysis_seconds", "Vision analysis latency")

_equipment_counter = Counter("vehicle_equipment_recommend_total", "Total equipment recommendations")
_equipment_latency = Histogram("vehicle_equipment_recommend_seconds", "Equipment recommendation latency")

_task_counter = Counter("vehicle_task_allocate_total", "Total task allocation requests")
_task_latency = Histogram("vehicle_task_allocate_seconds", "Task allocation latency")


# ==================== Pydantic请求/响应模型 ====================


class VisionAnalysisRequest(BaseModel):
    """视觉分析请求"""
    image_base64: Optional[str] = Field(None, description="Base64编码的图像数据")
    image_url: Optional[str] = Field(None, description="图像URL（暂不支持）")


class VisionAnalysisResponse(BaseModel):
    """视觉分析响应"""
    trace_id: str
    danger_level: str
    persons: Dict[str, Any]
    vehicles: Dict[str, Any]
    buildings: Dict[str, Any]
    roads: Dict[str, Any]
    hazards: List[str]
    recommendations: List[str]
    latency_ms: float
    confidence_score: float


class EquipmentRecommendRequest(BaseModel):
    """装备推荐请求"""
    disaster_type: str = Field(..., description="灾害类型：earthquake/flood/fire/landslide/chemical_leak")
    magnitude: float = Field(..., description="震级或灾害强度")
    affected_area: str = Field(..., description="受灾区域名称")
    terrain: str = Field("平原", description="地形：山区/平原/城市")
    weather: str = Field("晴", description="天气：晴/雨/雪")
    casualties: Optional[int] = Field(None, description="预估伤亡人数")
    hazards: List[str] = Field(default_factory=list, description="次生灾害列表")


class ReasoningStepResponse(BaseModel):
    """推理步骤响应"""
    stage: str
    source: str
    duration_ms: float
    confidence: float


class EquipmentItemResponse(BaseModel):
    """装备项响应"""
    name: str
    category: str
    quantity: int
    priority: str
    reason: str
    source: str
    kg_verified: bool


class EquipmentRecommendResponse(BaseModel):
    """装备推荐响应"""
    trace_id: str
    equipment_list: List[EquipmentItemResponse]
    reasoning_chain: List[ReasoningStepResponse]
    total_items: int
    total_reasoning_time_ms: float
    confidence_score: float
    citations: List[Dict[str, str]]


class TaskAllocationRequest(BaseModel):
    """任务分配请求"""

    class TaskInput(BaseModel):
        id: str
        name: str
        priority: str  # critical/high/medium/low
        location: tuple[float, float]
        required_skills: List[str]
        required_personnel: int
        estimated_duration_hours: float

    class TeamInput(BaseModel):
        id: str
        name: str
        status: str  # available/busy/offline
        location: tuple[float, float]
        skills: List[str]
        personnel_count: int

    tasks: List[TaskInput]
    teams: List[TeamInput]


class AssignmentResponse(BaseModel):
    """任务分配项响应"""
    task_id: str
    team_id: str
    estimated_travel_time_hours: float
    estimated_start_time_hours: float
    confidence: float


class TaskAllocationResponse(BaseModel):
    """任务分配响应"""
    trace_id: str
    assignments: List[AssignmentResponse]
    unassigned_tasks: List[str]
    total_response_time_hours: float
    average_team_load: float
    solver_time_ms: float
    is_feasible: bool
    warnings: List[str]


# ==================== 全局服务实例 ====================

# 这些实例会在应用启动时由main.py初始化
vision_analyzer: Optional[VisionAnalyzer] = None
equipment_recommender: Optional[EquipmentRecommender] = None
task_optimizer: Optional[TaskOptimizer] = None


def init_vehicle_services(
    vllm_vision_url: str,
    vllm_text_url: str,
    rag_url: str,
    kg_url: str,
):
    """初始化车载指挥服务（由main.py调用）

    Args:
        vllm_vision_url: GLM-4V-Plus地址 (H100 #1)
        vllm_text_url: GLM-4-Plus地址 (H100 #2)
        rag_url: RAG服务地址
        kg_url: KG服务地址
    """
    global vision_analyzer, equipment_recommender, task_optimizer

    vision_analyzer = VisionAnalyzer(vllm_url=vllm_vision_url)

    equipment_recommender = EquipmentRecommender(
        rag_url=rag_url,
        kg_url=kg_url,
        llm_url=vllm_text_url,
    )

    task_optimizer = TaskOptimizer(use_ortools=True, max_solver_time_seconds=10)

    logger.info(
        f"Vehicle services initialized: "
        f"vision={vllm_vision_url}, text={vllm_text_url}, rag={rag_url}, kg={kg_url}"
    )


# ==================== API端点 ====================


@router.post("/vision/analyze", response_model=VisionAnalysisResponse)
async def analyze_vision(req: VisionAnalysisRequest):
    """无人机图像视觉分析

    调用GLM-4V-Plus（H100 GPU#1）进行：
    - 人员/车辆检测与计数
    - 建筑物损毁评估
    - 道路通行状态分析
    - 危险等级评定（L0-L3）

    **性能指标**: 平均2.5秒/张图（1920×1080）
    """
    _vision_counter.inc()
    trace_id = str(uuid.uuid4())

    if vision_analyzer is None:
        raise HTTPException(status_code=503, detail="Vision analyzer not initialized")

    if not req.image_base64:
        raise HTTPException(status_code=400, detail="Missing image_base64")

    try:
        with _vision_latency.time():
            result = await vision_analyzer.analyze_drone_image(
                image_base64=req.image_base64
            )

        return VisionAnalysisResponse(
            trace_id=trace_id,
            danger_level=result.danger_level.value,
            persons={
                "count": result.persons.count,
                "positions": result.persons.positions,
                "activities": result.persons.activities,
            },
            vehicles={
                "total_count": result.vehicles.total_count,
                "by_type": result.vehicles.by_type,
                "positions": result.vehicles.positions,
            },
            buildings={
                "total_buildings": result.buildings.total_buildings,
                "damaged_count": result.buildings.damaged_count,
                "damage_levels": result.buildings.damage_levels,
                "collapse_risk": result.buildings.collapse_risk,
            },
            roads={
                "passable": result.roads.passable,
                "blocked_sections": result.roads.blocked_sections,
                "obstacles": result.roads.obstacles,
            },
            hazards=result.hazards,
            recommendations=result.recommendations,
            latency_ms=result.latency_ms,
            confidence_score=result.confidence_score,
        )

    except Exception as e:
        logger.error(f"Vision analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/vision/analyze/file", response_model=VisionAnalysisResponse)
async def analyze_vision_file(file: UploadFile = File(...)):
    """无人机图像视觉分析（文件上传版）

    支持格式：JPEG, PNG
    最大文件大小：10MB
    """
    _vision_counter.inc()
    trace_id = str(uuid.uuid4())

    if vision_analyzer is None:
        raise HTTPException(status_code=503, detail="Vision analyzer not initialized")

    try:
        # 读取文件并编码为base64
        import base64
        file_data = await file.read()
        if len(file_data) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")

        image_b64 = base64.b64encode(file_data).decode("utf-8")

        with _vision_latency.time():
            result = await vision_analyzer.analyze_drone_image(image_base64=image_b64)

        return VisionAnalysisResponse(
            trace_id=trace_id,
            danger_level=result.danger_level.value,
            persons={
                "count": result.persons.count,
                "positions": result.persons.positions,
                "activities": result.persons.activities,
            },
            vehicles={
                "total_count": result.vehicles.total_count,
                "by_type": result.vehicles.by_type,
                "positions": result.vehicles.positions,
            },
            buildings={
                "total_buildings": result.buildings.total_buildings,
                "damaged_count": result.buildings.damaged_count,
                "damage_levels": result.buildings.damage_levels,
                "collapse_risk": result.buildings.collapse_risk,
            },
            roads={
                "passable": result.roads.passable,
                "blocked_sections": result.roads.blocked_sections,
                "obstacles": result.roads.obstacles,
            },
            hazards=result.hazards,
            recommendations=result.recommendations,
            latency_ms=result.latency_ms,
            confidence_score=result.confidence_score,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/equipment/recommend", response_model=EquipmentRecommendResponse)
async def recommend_equipment(req: EquipmentRecommendRequest):
    """装备智能推荐

    三阶段混合推理：
    1. RAG检索应急救援规范（GB/T标准）
    2. KG验证装备真实性（Neo4j知识图谱）
    3. LLM综合生成方案（GLM-4-Plus on H100 #2）

    **透明化推理链**: 每个步骤的数据源、耗时、置信度全部返回

    **性能指标**: 平均1.5秒（并行执行RAG+KG）
    """
    _equipment_counter.inc()
    trace_id = str(uuid.uuid4())

    if equipment_recommender is None:
        raise HTTPException(status_code=503, detail="Equipment recommender not initialized")

    try:
        disaster_context = {
            "disaster_type": req.disaster_type,
            "magnitude": req.magnitude,
            "affected_area": req.affected_area,
            "terrain": req.terrain,
            "weather": req.weather,
            "casualties": req.casualties,
            "hazards": req.hazards,
        }

        with _equipment_latency.time():
            result = await equipment_recommender.recommend(disaster_context)

        return EquipmentRecommendResponse(
            trace_id=trace_id,
            equipment_list=[
                EquipmentItemResponse(
                    name=item.name,
                    category=item.category,
                    quantity=item.quantity,
                    priority=item.priority,
                    reason=item.reason,
                    source=item.source,
                    kg_verified=item.kg_verified,
                )
                for item in result.equipment_list
            ],
            reasoning_chain=[
                ReasoningStepResponse(
                    stage=step.stage.value,
                    source=step.source,
                    duration_ms=step.duration_ms,
                    confidence=step.confidence,
                )
                for step in result.reasoning_chain
            ],
            total_items=result.total_items,
            total_reasoning_time_ms=result.total_reasoning_time_ms,
            confidence_score=result.confidence_score,
            citations=result.citations,
        )

    except Exception as e:
        logger.error(f"Equipment recommendation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


@router.post("/task/allocate", response_model=TaskAllocationResponse)
async def allocate_tasks(req: TaskAllocationRequest):
    """任务分配优化

    使用OR-Tools约束优化引擎：
    - 多目标优化（响应时间最小化 + 负载均衡）
    - 约束满足（技能匹配、人数要求、队伍状态）
    - 智能降级（OR-Tools不可用时使用贪心算法）

    **性能指标**: 平均500ms（100任务×20队伍）
    """
    _task_counter.inc()
    trace_id = str(uuid.uuid4())

    if task_optimizer is None:
        raise HTTPException(status_code=503, detail="Task optimizer not initialized")

    try:
        # 转换输入数据
        tasks = [
            Task(
                id=t.id,
                name=t.name,
                priority=TaskPriority(t.priority),
                location=t.location,
                required_skills=set(t.required_skills),
                required_personnel=t.required_personnel,
                estimated_duration_hours=t.estimated_duration_hours,
            )
            for t in req.tasks
        ]

        teams = [
            RescueTeam(
                id=tm.id,
                name=tm.name,
                status=TeamStatus(tm.status),
                location=tm.location,
                skills=set(tm.skills),
                personnel_count=tm.personnel_count,
            )
            for tm in req.teams
        ]

        with _task_latency.time():
            result = task_optimizer.optimize(tasks, teams)

        return TaskAllocationResponse(
            trace_id=trace_id,
            assignments=[
                AssignmentResponse(
                    task_id=a.task_id,
                    team_id=a.team_id,
                    estimated_travel_time_hours=a.estimated_travel_time_hours,
                    estimated_start_time_hours=a.estimated_start_time_hours,
                    confidence=a.confidence,
                )
                for a in result.assignments
            ],
            unassigned_tasks=result.unassigned_tasks,
            total_response_time_hours=result.total_response_time_hours,
            average_team_load=result.average_team_load,
            solver_time_ms=result.solver_time_ms,
            is_feasible=result.is_feasible,
            warnings=result.warnings,
        )

    except Exception as e:
        logger.error(f"Task allocation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Allocation failed: {str(e)}")


@router.get("/health")
async def vehicle_health():
    """车载指挥服务健康检查"""
    status = {
        "vision_analyzer": vision_analyzer is not None,
        "equipment_recommender": equipment_recommender is not None,
        "task_optimizer": task_optimizer is not None,
    }

    all_healthy = all(status.values())

    return {
        "status": "ok" if all_healthy else "degraded",
        "services": status,
    }
