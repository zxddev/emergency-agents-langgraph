"""LangGraph 侦察流程编排。

本文件负责构建侦察规划子图,将用户给定的 `event_id` 与 `command_text`
转换为结构化的侦察方案(`ReconPlan`)以及对应的草稿(`ReconPlanDraft`)。

为满足可恢复/幂等/专业性的工程基线:
- 对外部副作用(LLM 调用/数据库草稿组装)使用 `@task` 包装,通过 `.result()` 获取结果,
  避免在 checkpoint 恢复时重复执行副作用。
- 提供异步构建函数以绑定 PostgreSQL checkpointer,并在 API 启动阶段注入 `app.state.recon_graph`。
"""

from __future__ import annotations

from typing import Any, Dict, Literal, TypedDict

from langgraph.graph import StateGraph
from langgraph.func import task

import structlog

from emergency_agents.external.recon_gateway import PostgresReconGateway, ReconPlanDraft
from emergency_agents.planner.recon_models import ReconPlan
from emergency_agents.planner.recon_pipeline import ReconPipeline
from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer

logger = structlog.get_logger(__name__)


class ReconState(TypedDict, total=False):
    """侦察流程状态容器。

    说明:
    - `event_id` 与 `command_text` 是输入关键字段,应由调用方提供。
    - `plan` 与 `draft` 为中间/最终产物,由图内节点生成。
    - `status` 为流程进度标签,便于日志追踪。
    - 使用 TypedDict(强类型)约束字段形态,配合下游模型(pydantic)保证结构完整性。
    """

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
    """构建侦察任务 LangGraph(不绑定持久化)。

    参数:
        pipeline: 负责生成侦察方案的流水线。
        gateway: 连接 Postgres 数据源的访问网关。
    返回:
        已编译的 LangGraph,可通过 `invoke` 执行。

    注意:
    - 此函数不绑定 checkpointer,适合本地/单元测试。
    - 生产/演示环境请使用 `build_recon_graph_async(...)` 以启用持久化与恢复。
    """

    graph = StateGraph(ReconState)

    @task
    def generate_plan_task(event_id: str, command_text: str, _pipeline: ReconPipeline) -> ReconPlan:
        """生成侦察方案(幂等包装)。

        - 输入: 事件编号/指令文本/侦察流水线
        - 输出: ReconPlan(强类型)
        - 失败: 抛出异常,由 LangGraph 负责错误传播与可观测性
        """
        # 使用侦察流水线解析指令并生成完整方案(含规则校验与LLM蓝图转换)
        return _pipeline.build_plan(command_text=command_text, event_id=event_id)

    @task
    def prepare_draft_task(
        event_id: str,
        command_text: str,
        plan: ReconPlan,
        _pipeline: ReconPipeline,
        _gateway: PostgresReconGateway,
    ) -> ReconPlanDraft:
        """根据方案生成草稿(幂等包装)。

        - 输入: 事件编号/指令/方案/流水线/网关
        - 输出: ReconPlanDraft(草稿摘要与写库载荷)
        - 失败: 抛出异常
        """
        return _gateway.prepare_plan_draft(
            event_id=event_id,
            command_text=command_text,
            plan=plan,
            pipeline=_pipeline,
        )

    def _generate_plan(state: ReconState) -> Dict[str, Any]:
        """生成侦察方案(节点)。"""

        event_id = state.get("event_id")
        command_text = state.get("command_text")
        if not event_id or not command_text:
            raise ValueError("缺少 event_id 或 command_text，无法生成侦察方案")
        logger.info("recon_generate_plan_start", event_id=event_id)
        plan = generate_plan_task(event_id, command_text, pipeline).result()  # 使用@task包装,支持恢复
        logger.info(
            "recon_generate_plan_done",
            event_id=event_id,
            objectives=len(plan.objectives),
            task_count=len(plan.tasks),
        )
        return {"plan": plan, "status": "plan_ready"}

    def _prepare_draft(state: ReconState) -> Dict[str, Any]:
        """构造侦察方案草稿(节点)。"""

        plan = state.get("plan")
        event_id = state.get("event_id")
        command_text = state.get("command_text")
        if plan is None or event_id is None or command_text is None:
            raise ValueError("方案或上下文缺失，无法生成草稿")
        logger.info("recon_prepare_draft_start", event_id=event_id)
        draft = prepare_draft_task(event_id, command_text, plan, pipeline, gateway).result()
        logger.info("recon_prepare_draft_done", event_id=event_id, tasks=len(draft.tasks_payload))
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


async def build_recon_graph_async(
    *,
    pipeline: ReconPipeline,
    gateway: PostgresReconGateway,
    dsn: str,
    schema: str = "recon_checkpoint",
) -> Any:
    """异步构建侦察任务 LangGraph(绑定PostgreSQL checkpointer)。

    参数:
        pipeline: 侦察方案流水线
        gateway: Postgres 侦察数据网关
        dsn: Postgres 连接串
        schema: Checkpoint schema 名称(默认: recon_checkpoint)

    返回:
        编译后的 LangGraph 应用,支持持久化与恢复。
    """
    if not dsn or not dsn.strip():  # 卫语句: 必填校验
        raise ValueError("POSTGRES_DSN 缺失,无法构建 recon 子图")

    # 构建 StateGraph
    graph = build_recon_graph(pipeline=pipeline, gateway=gateway)

    # 绑定 PostgreSQL checkpointer
    checkpointer, close_cb = await create_async_postgres_checkpointer(
        dsn=dsn,
        schema=schema,
        min_size=1,
        max_size=1,
    )
    logger.info("recon_graph_checkpointer_ready", schema=schema)

    # 重新编译并附加关闭钩子
    # 说明: build_recon_graph 返回的已编译对象无法直接重绑,此处重新生成 StateGraph 再编译
    # 为避免重复构建,这里直接使用同一实现流程重新构建
    graph2 = StateGraph(ReconState)

    # 复用相同节点构造逻辑
    @task
    def _gen(event_id: str, command_text: str, _pipeline: ReconPipeline) -> ReconPlan:
        return _pipeline.build_plan(command_text=command_text, event_id=event_id)

    @task
    def _draft(
        event_id: str,
        command_text: str,
        plan: ReconPlan,
        _pipeline: ReconPipeline,
        _gateway: PostgresReconGateway,
    ) -> ReconPlanDraft:
        return _gateway.prepare_plan_draft(
            event_id=event_id, command_text=command_text, plan=plan, pipeline=_pipeline
        )

    def __gen(state: ReconState) -> Dict[str, Any]:
        eid = state.get("event_id")
        cmd = state.get("command_text")
        if not eid or not cmd:
            raise ValueError("缺少 event_id 或 command_text,无法生成侦察方案")
        logger.info("recon_generate_plan_start", event_id=eid)
        plan = _gen(eid, cmd, pipeline).result()
        logger.info("recon_generate_plan_done", event_id=eid, task_count=len(plan.tasks))
        return {"plan": plan, "status": "plan_ready"}

    def __draft(state: ReconState) -> Dict[str, Any]:
        plan = state.get("plan")
        eid = state.get("event_id")
        cmd = state.get("command_text")
        if plan is None or eid is None or cmd is None:
            raise ValueError("方案或上下文缺失,无法生成草稿")
        logger.info("recon_prepare_draft_start", event_id=eid)
        dr = _draft(eid, cmd, plan, pipeline, gateway).result()
        logger.info("recon_prepare_draft_done", event_id=eid, tasks=len(dr.tasks_payload))
        return {"draft": dr, "status": "draft_ready"}

    def __finish(state: ReconState) -> Dict[str, Any]:
        if state.get("status") != "draft_ready":
            raise ValueError("侦察草稿未准备完成,无法结束流程")
        return {}

    graph2.add_node("generate_plan", __gen)
    graph2.add_node("prepare_draft", __draft)
    graph2.add_node("finish", __finish)
    graph2.set_entry_point("generate_plan")
    graph2.add_edge("generate_plan", "prepare_draft")
    graph2.add_edge("prepare_draft", "finish")

    app = graph2.compile(checkpointer=checkpointer)
    setattr(app, "_checkpoint_close", close_cb)
    return app
