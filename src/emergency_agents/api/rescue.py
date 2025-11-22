from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from emergency_agents.services import RescueDraftService
from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
import structlog
import time

router = APIRouter(prefix="/rescue", tags=["rescue"])
logger = structlog.get_logger(__name__)

# 由 main.py 注入
_pg_pool_async: Optional[AsyncConnectionPool] = None


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


class ActionPlanRequest(BaseModel):
    """基于描述+实有装备生成前线救援行动方案（前端调用Java，Java可透传此结构）。"""

    description: str = Field(..., description="现场救援描述或指令")
    location_name: Optional[str] = Field(None, description="地点名称")
    latitude: Optional[float] = Field(None, description="纬度")
    longitude: Optional[float] = Field(None, description="经度")
    disaster_type: Optional[str] = Field(None, description="灾种描述，用于提示模型")
    event_id: Optional[str] = Field(None, description="事件ID，用于链路追踪")


class ActionPlanItem(BaseModel):
    level: str
    title: str
    origin: str
    time: str
    locationName: str
    location: Dict[str, Any]
    image: Optional[str] = None
    schema: str
    description: str


class CommonEnvelope(BaseModel):
    code: int = 200
    data: Any
    message: str = "ok"


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


async def _fetch_available_devices(pool: AsyncConnectionPool, limit: int = 5) -> List[Dict[str, Any]]:
    """查询实有装备，优先在 action 方案中使用。"""
    sql = """
        SELECT id, name, device_type, env_type, weather_capability
        FROM operational.device
        WHERE deleted_at IS NULL
        ORDER BY is_recon DESC NULLS LAST, id ASC
        LIMIT %s
    """
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (limit,))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


def _fmt_coord(lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
    return {
        "latitude": lat if lat is not None else 0.0,
        "longitude": lon if lon is not None else 0.0,
    }


@router.post("/action-plan-from-description", response_model=CommonEnvelope)
async def generate_action_plan_from_description(payload: ActionPlanRequest) -> CommonEnvelope:
    """
    基于描述+实有装备生成“一线救援行动方案”前置数据。

    - 返回格式兼容前端现有一线救援方案弹窗（与 Java 接口结构一致）：code/data/message
    - data 为 pointList（Steps 用的数据），字段：level/title/origin/time/locationName/location/schema/description/image
    - 设备来源：PostgreSQL operational.device（实有装备），若查询失败则降级为空列表。
    """
    start_ts = time.perf_counter()
    cfg = AppConfig.load_from_env()

    devices: List[Dict[str, Any]] = []
    if _pg_pool_async:
        try:
            devices = await _fetch_available_devices(_pg_pool_async, limit=6)
        except Exception as e:  # pragma: no cover - 容错降级
            logger.warning("fetch_devices_failed", error=str(e))
    else:
        logger.warning("pg_pool_not_initialized_action_plan")

    device_lines = [
        f"- {d.get('name','未知装备')} | 类型:{d.get('device_type') or '未知'} | 环境:{d.get('env_type') or '未知'} | 能力:{d.get('weather_capability') or '未标注'}"
        for d in devices
    ]
    device_block = "\n".join(device_lines) if device_lines else "（未查询到实有装备，需人工补充装备列表）"

    location_name = payload.location_name or "救援现场"
    coord = _fmt_coord(payload.latitude, payload.longitude)
    disaster = payload.disaster_type or "综合灾害"

    llm_client = get_openai_client(cfg)
    prompt = (
        "你是一名应急救援前线指挥员，请基于现场描述和可用装备，生成一段简明可执行的救援行动方案。"
        "要求：\n"
        "1) 3-5 条要点，每条 1 句话，包含任务目标和使用的关键装备。\n"
        "2) 覆盖侦察/救援/医疗/通信保障等核心环节。\n"
        "3) 语气正式、可直接下达。\n\n"
        f"灾种: {disaster}\n"
        f"位置: {location_name} ({coord['latitude']},{coord['longitude']})\n"
        f"现场描述: {payload.description}\n"
        f"可用装备:\n{device_block}\n"
    )

    try:
        completion = llm_client.chat.completions.create(
            model=cfg.llm_model or "glm-4-flash",
            temperature=0.2,
            max_tokens=800,
            messages=[
                {"role": "system", "content": "生成中文救援行动要点，条理清晰，面向指挥员。"},
                {"role": "user", "content": prompt},
            ],
        )
        plan_text = completion.choices[0].message.content if completion.choices else ""
    except Exception as e:
        logger.warning("action_plan_llm_failed", error=str(e))
        plan_text = "未能生成AI方案，请人工补充。"

    point = ActionPlanItem(
        level="紧急",
        title=f"{location_name} 一线救援行动方案",
        origin="AI生成方案",
        time=datetime.utcnow().isoformat(),
        locationName=location_name,
        location=coord,
        image=None,
        schema=plan_text,
        description=payload.description,
    )

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    logger.info(
        "action_plan_generated",
        latency_ms=elapsed_ms,
        device_count=len(devices),
        has_llm=bool(plan_text),
        disaster=disaster,
    )

    return CommonEnvelope(code=200, data=[point.model_dump()], message="ok")
