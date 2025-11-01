from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from emergency_agents.services import RescueDraftService

router = APIRouter(prefix="/rescue", tags=["rescue"])


class RescueDraftResponse(BaseModel):
    draft_id: str = Field(..., description="草稿ID")
    incident_id: str = Field(..., description="事件ID")
    entity_id: Optional[str] = Field(None, description="关联实体ID")
    plan: Dict[str, Any] = Field(..., description="方案主体")
    risk_summary: Dict[str, Any] = Field(default_factory=dict, description="风险摘要")
    ui_actions: List[Dict[str, Any]] = Field(default_factory=list, description="前端UI动作")
    created_at: datetime = Field(..., description="创建时间")
    created_by: Optional[str] = Field(None, description="创建人")


class ConfirmDraftRequest(BaseModel):
    commander_id: str = Field(..., min_length=1, description="确认人")
    priority: int = Field(70, ge=0, le=100, description="任务优先级")
    description: Optional[str] = Field(None, description="任务描述")
    deadline: Optional[datetime] = Field(None, description="任务截止时间")
    task_code: Optional[str] = Field(None, description="任务编码")


class ConfirmDraftResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    incident_id: Optional[str] = Field(None, description="事件ID")
    status: str = Field(..., description="任务状态")
    priority: int = Field(..., description="优先级")
    description: Optional[str] = Field(None, description="任务描述")


def _require_draft_service(request: Request) -> RescueDraftService:
    service = getattr(request.app.state, "rescue_draft_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="救援草稿服务未初始化")
    return service


@router.get("/drafts/{draft_id}", response_model=RescueDraftResponse)
async def get_rescue_draft(
    draft_id: str,
    service: RescueDraftService = Depends(_require_draft_service),
) -> RescueDraftResponse:
    try:
        record = await service.load_draft(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RescueDraftResponse(
        draft_id=record.draft_id,
        incident_id=record.incident_id,
        entity_id=record.entity_id,
        plan=dict(record.plan),
        risk_summary=dict(record.risk_summary),
        ui_actions=[dict(action) for action in record.ui_actions],
        created_at=record.created_at,
        created_by=record.created_by,
    )


@router.post("/drafts/{draft_id}/confirm", response_model=ConfirmDraftResponse)
async def confirm_rescue_draft(
    draft_id: str,
    payload: ConfirmDraftRequest,
    service: RescueDraftService = Depends(_require_draft_service),
) -> ConfirmDraftResponse:
    try:
        task = await service.confirm_draft(
            draft_id,
            commander_id=payload.commander_id,
            priority=payload.priority,
            description=payload.description,
            deadline=payload.deadline,
            task_code=payload.task_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ConfirmDraftResponse(
        task_id=task.id,
        incident_id=task.event_id,
        status=task.status,
        priority=task.priority,
        description=task.description,
    )
