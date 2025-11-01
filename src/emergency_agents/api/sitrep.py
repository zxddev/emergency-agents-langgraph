"""态势上报（SITREP）API端点

提供生成和查询态势报告的REST API接口。
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from emergency_agents.graph.sitrep_app import build_sitrep_graph

logger = structlog.get_logger(__name__)

router = APIRouter()


# ========== 请求/响应模型 ==========


class SITREPGenerateRequest(BaseModel):
    """生成态势报告请求"""

    incident_id: Optional[str] = Field(
        None,
        description="可选：指定事件ID生成专项报告",
    )
    time_range_hours: int = Field(
        24,
        ge=1,
        le=168,  # 最多7天
        description="统计时间范围（小时），默认24小时",
    )
    user_id: Optional[str] = Field(
        None,
        description="用户ID，可选（默认使用'system'）",
    )


class SITREPMetricsResponse(BaseModel):
    """态势指标响应"""

    active_incidents_count: int
    completed_tasks_count: int
    in_progress_tasks_count: int
    pending_tasks_count: int
    active_risk_zones_count: int
    deployed_teams_count: int
    total_rescuers_count: int
    statistics_time_range_hours: int


class SITREPGenerateResponse(BaseModel):
    """生成态势报告响应"""

    report_id: str = Field(..., description="报告ID")
    generated_at: str = Field(..., description="生成时间（ISO8601）")
    summary: str = Field(..., description="LLM生成的态势摘要")
    metrics: SITREPMetricsResponse = Field(..., description="态势指标")
    details: Dict[str, Any] = Field(..., description="详细数据")
    snapshot_id: str = Field(..., description="快照ID")


class SITREPHistoryItem(BaseModel):
    """历史态势报告条目"""

    report_id: str
    generated_at: str
    summary: str
    metrics: Dict[str, Any]
    incident_id: Optional[str] = None


class SITREPHistoryResponse(BaseModel):
    """历史态势报告响应"""

    total: int = Field(..., description="总数")
    items: List[SITREPHistoryItem] = Field(..., description="报告列表")
    limit: int
    offset: int


# ========== 依赖注入 ==========
# 这些全局变量将在main.py的startup_event中初始化

_sitrep_graph = None
_incident_dao = None
_snapshot_repo = None


def get_sitrep_graph():
    """获取SITREP graph实例（依赖注入）"""
    if _sitrep_graph is None:
        raise HTTPException(
            status_code=500,
            detail="SITREP graph未初始化，请检查服务启动流程",
        )
    return _sitrep_graph


def get_incident_dao():
    """获取IncidentDAO实例（依赖注入）"""
    if _incident_dao is None:
        raise HTTPException(
            status_code=500,
            detail="IncidentDAO未初始化，请检查服务启动流程",
        )
    return _incident_dao


def get_snapshot_repo():
    """获取IncidentSnapshotRepository实例（依赖注入）"""
    if _snapshot_repo is None:
        raise HTTPException(
            status_code=500,
            detail="IncidentSnapshotRepository未初始化，请检查服务启动流程",
        )
    return _snapshot_repo


# ========== API端点 ==========


@router.post("/generate", response_model=SITREPGenerateResponse)
async def generate_sitrep(
    request: SITREPGenerateRequest,
    sitrep_graph=Depends(get_sitrep_graph),
) -> SITREPGenerateResponse:
    """
    生成态势报告

    流程：
    1. 初始化State（report_id, user_id, thread_id, triggered_at）
    2. 调用graph.invoke()执行完整流程（durability="sync"）
    3. 返回最终报告

    性能要求：
    - 正常情况下30秒内返回
    - 数据采集: <5秒
    - LLM生成: <15秒
    - 持久化: <2秒
    """
    start_time = datetime.now(timezone.utc)
    report_id = str(uuid.uuid4())
    user_id = request.user_id or "system"
    thread_id = f"sitrep-{report_id}"

    logger.info(
        "sitrep_generate_start",
        report_id=report_id,
        incident_id=request.incident_id,
        time_range_hours=request.time_range_hours,
        user_id=user_id,
    )

    try:
        # 构建初始State
        initial_state = {
            "report_id": report_id,
            "user_id": user_id,
            "thread_id": thread_id,
            "triggered_at": datetime.now(timezone.utc),
            "time_range_hours": request.time_range_hours,
        }

        # 如果指定了incident_id，添加到State
        if request.incident_id:
            initial_state["incident_id"] = request.incident_id

        # 配置
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": f"user-{user_id}",  # 租户隔离
            }
        }

        # 执行graph（durability="sync"确保可靠持久化）
        result = await sitrep_graph.ainvoke(
            initial_state,
            config=config,
            durability="sync",  # 同步持久化模式
        )

        # 提取最终报告
        if "sitrep_report" not in result or not result["sitrep_report"]:
            raise HTTPException(
                status_code=500,
                detail="SITREP生成失败：未返回报告数据",
            )

        report = result["sitrep_report"]

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            "sitrep_generate_completed",
            report_id=report_id,
            snapshot_id=report.get("snapshot_id"),
            duration_ms=duration * 1000,
        )

        # 构建响应
        return SITREPGenerateResponse(
            report_id=report["report_id"],
            generated_at=report["generated_at"],
            summary=report["summary"],
            metrics=SITREPMetricsResponse(**report["metrics"]),
            details=report["details"],
            snapshot_id=report["snapshot_id"],
        )

    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.error(
            "sitrep_generate_failed",
            report_id=report_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration * 1000,
        )
        raise HTTPException(
            status_code=500,
            detail=f"SITREP生成失败: {str(e)}",
        )


@router.get("/history", response_model=SITREPHistoryResponse)
async def get_sitrep_history(
    incident_id: Optional[str] = Query(None, description="可选：按事件ID过滤"),
    limit: int = Query(10, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    snapshot_repo=Depends(get_snapshot_repo),
) -> SITREPHistoryResponse:
    """
    查询历史态势报告

    支持：
    - 按incident_id过滤
    - 分页查询（limit/offset）
    - 按时间倒序排列
    """
    start_time = datetime.now(timezone.utc)

    logger.info(
        "sitrep_history_query_start",
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )

    try:
        # 查询快照（snapshot_type='sitrep_report'）
        snapshots = await snapshot_repo.list_snapshots(
            incident_id=incident_id,
            snapshot_type="sitrep_report",
            limit=limit,
            offset=offset,
        )

        # 统计总数（如果repository支持）
        # 注意：这里假设repository返回结果包含total_count字段
        # 如果不支持，可以设置为len(snapshots)（不精确但可用）
        total = getattr(snapshots, "total_count", len(snapshots))

        # 转换为响应格式
        items = []
        for snapshot in snapshots:
            payload = snapshot.payload or {}
            items.append(
                SITREPHistoryItem(
                    report_id=snapshot.snapshot_id,
                    generated_at=payload.get("generated_at", ""),
                    summary=payload.get("summary", ""),
                    metrics=payload.get("metrics", {}),
                    incident_id=snapshot.incident_id,
                )
            )

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            "sitrep_history_query_completed",
            result_count=len(items),
            duration_ms=duration * 1000,
        )

        return SITREPHistoryResponse(
            total=total,
            items=items,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.error(
            "sitrep_history_query_failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration * 1000,
        )
        raise HTTPException(
            status_code=500,
            detail=f"查询历史报告失败: {str(e)}",
        )
