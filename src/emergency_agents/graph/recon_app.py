"""LangGraph 侦察流程编排。"""

from __future__ import annotations

from typing import Any, Dict, Literal, TypedDict

from langgraph.graph import StateGraph

from emergency_agents.external.recon_gateway import PostgresReconGateway, ReconPlanDraft
from emergency_agents.planner.recon_models import ReconPlan
from emergency_agents.planner.recon_pipeline import ReconPipeline


class ReconState(TypedDict, total=False):
    """侦察流程状态容器。"""

    event_id: str
    command_text: str
    plan: ReconPlan
    draft: ReconPlanDraft
    status: Literal["init", "plan_ready", "draft_ready", "error"]
    error_message: str


def build_recon_graph(
    pipeline: ReconPipeline,
    gateway: PostgresReconGateway,
) -> Any:
    """构建侦察任务 LangGraph。

    参数:
        pipeline: 负责生成侦察方案的流水线。
        gateway: 连接 Postgres 数据源的访问网关。
    返回:
        已编译的 LangGraph，可通过 invoke 执行。
    """

    graph = StateGraph(ReconState)

    def _generate_plan(state: ReconState) -> Dict[str, Any]:
        """生成侦察方案。"""

        event_id = state.get("event_id")
        command_text = state.get("command_text")
        if not event_id or not command_text:
            raise ValueError("缺少 event_id 或 command_text，无法生成侦察方案")
        # 使用侦察流水线解析指令并生成完整方案
        plan = pipeline.build_plan(command_text=command_text, event_id=event_id)
        return {"plan": plan, "status": "plan_ready"}

    def _prepare_draft(state: ReconState) -> Dict[str, Any]:
        """构造侦察方案草稿。"""

        plan = state.get("plan")
        event_id = state.get("event_id")
        command_text = state.get("command_text")
        if plan is None or event_id is None or command_text is None:
            raise ValueError("方案或上下文缺失，无法生成草稿")
        draft = gateway.prepare_plan_draft(
            event_id=event_id,
            command_text=command_text,
            plan=plan,
            pipeline=pipeline,
        )
        return {"draft": draft, "status": "draft_ready"}

    def _finalize(state: ReconState) -> Dict[str, Any]:
        """返回最终状态。"""

        if state.get("status") != "draft_ready":
            raise ValueError("侦察草稿未准备完成，无法结束流程")
        return {}

    graph.add_node("generate_plan", _generate_plan)
    graph.add_node("prepare_draft", _prepare_draft)
    graph.add_node("finish", _finalize)

    graph.set_entry_point("generate_plan")
    graph.add_edge("generate_plan", "prepare_draft")
    graph.add_edge("prepare_draft", "finish")

    return graph.compile()
