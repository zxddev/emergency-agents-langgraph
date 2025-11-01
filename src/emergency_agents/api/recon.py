"""侦察方案 REST 接口。"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from anyio import to_thread
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from emergency_agents.external.recon_gateway import ReconPlanDraft
from emergency_agents.planner.recon_models import ReconPlan, TaskPlanPayload


router = APIRouter(prefix="/recon", tags=["recon"])


class ReconPlanRequest(BaseModel):
    """侦察方案生成请求体。"""

    event_id: UUID = Field(..., description="关联事件 ID")
    command_text: str = Field(..., min_length=1, description="侦察自然语言指令")


class ReconPlanResponse(BaseModel):
    """侦察方案应答结构。"""

    plan: ReconPlan
    plan_summary: str
    plan_payload: Dict[str, Any]
    tasks: List[TaskPlanPayload]


def _require_graph(request: Request) -> Any:
    """从应用状态获取侦察 LangGraph。"""

    graph = getattr(request.app.state, "recon_graph", None)
    if graph is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "recon graph unavailable")
    return graph


@router.post("/plans", response_model=ReconPlanResponse)
async def create_recon_plan(payload: ReconPlanRequest, request: Request) -> ReconPlanResponse:
    """生成并持久化侦察方案。"""

    graph = _require_graph(request)

    def _invoke() -> Dict[str, Any]:
        """同步执行 LangGraph 侦察流程。"""

        init_state = {
            "event_id": str(payload.event_id),
            "command_text": payload.command_text,
        }
        return graph.invoke(
            init_state,
            config={"durability": "sync"},  # 长流程（侦察规划），同步保存checkpoint确保高可靠性
        )

    state = await to_thread.run_sync(_invoke)
    plan = state.get("plan")
    draft: ReconPlanDraft | None = state.get("draft")
    if plan is None or draft is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "recon plan generation failed")
    return ReconPlanResponse(
        plan=plan,
        plan_summary=draft.summary,
        plan_payload=draft.plan_payload,
        tasks=draft.tasks_payload,
    )
