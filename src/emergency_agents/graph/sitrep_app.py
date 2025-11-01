"""态势上报（SITREP Reporting）LangGraph子图

SITREP（Situation Report）是军事/应急领域的标准概念，用于定期汇总当前事件状态、
资源使用、风险评估和后续行动建议。

本子图特点：
- 100%独立，不依赖其他子图的执行结果
- 数据聚合 + LLM摘要的混合架构
- 强类型State（TypedDict + NotRequired）
- 所有副作用操作使用@task包装
- durability="sync"确保可靠持久化
- 完整的structlog日志链路

参考文档：
- openspec/changes/add-sitrep-graph/specs/sitrep-reporting/spec.md
- docs/新业务逻辑md/langgraph资料/references/concept-durable-execution.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, NotRequired, TypedDict

import structlog

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ModuleNotFoundError:
    AsyncPostgresSaver = None  # type: ignore[assignment, misc]

from langgraph.func import task
from langgraph.graph import END, START, StateGraph

from emergency_agents.db.dao import (
    IncidentDAO,
    IncidentRecord,
    IncidentSnapshotRepository,
    RescueDAO,
    TaskDAO,
)
from emergency_agents.db.models import IncidentSnapshotCreateInput, TaskSummary
from emergency_agents.risk.service import RiskCacheManager, RiskZoneRecord

logger = structlog.get_logger(__name__)


# ========== 数据模型定义 ==========


class SITREPMetrics(TypedDict):
    """态势报告核心指标数据模型

    所有字段可选（NotRequired），因为指标在aggregate_metrics节点中计算
    """

    active_incidents_count: NotRequired[int]
    completed_tasks_count: NotRequired[int]
    in_progress_tasks_count: NotRequired[int]
    pending_tasks_count: NotRequired[int]
    active_risk_zones_count: NotRequired[int]
    deployed_teams_count: NotRequired[int]
    total_rescuers_count: NotRequired[int]
    statistics_time_range_hours: NotRequired[int]


class SITREPReport(TypedDict):
    """最终生成的态势报告数据模型

    所有字段可选（NotRequired），因为报告在finalize节点中构建
    """

    report_id: NotRequired[str]
    generated_at: NotRequired[str]  # ISO8601时间戳
    summary: NotRequired[str]  # LLM生成的摘要
    metrics: NotRequired[SITREPMetrics]
    details: NotRequired[Dict[str, Any]]  # 详细数据（incidents/tasks/risks）
    snapshot_id: NotRequired[str]  # 持久化后的快照ID


class SITREPState(TypedDict):
    """态势上报子图状态定义

    核心标识字段（默认必填）：report_id, user_id, thread_id, triggered_at
    其他所有字段（NotRequired）：在图执行过程中逐步填充

    参考：
    - rescue_tactical_app.py:106-156 的State定义模式
    - concept-durable-execution.md:26 的TypedDict规范
    """

    # 核心标识字段（必填，TypedDict默认行为）
    report_id: str
    user_id: str
    thread_id: str
    triggered_at: datetime

    # 输入参数（可选）
    incident_id: NotRequired[str]  # 可选：指定事件ID生成专项报告
    time_range_hours: NotRequired[int]  # 统计时间范围（小时），默认24

    # 数据采集结果（可选）
    active_incidents: NotRequired[List[IncidentRecord]]
    task_progress: NotRequired[List[TaskSummary]]
    risk_zones: NotRequired[List[RiskZoneRecord]]
    resource_usage: NotRequired[Dict[str, Any]]

    # 分析结果（可选）
    metrics: NotRequired[SITREPMetrics]
    llm_summary: NotRequired[str]

    # 输出结果（可选）
    sitrep_report: NotRequired[SITREPReport]
    snapshot_id: NotRequired[str]

    # 状态标记（可选）
    status: NotRequired[str]
    error: NotRequired[str]


# ========== @task包装函数：确保副作用操作的幂等性 ==========
# 参考：concept-durable-execution.md:26
# "wrap any operations with side effects inside @tasks"


@task
async def fetch_active_incidents_task(
    incident_dao: IncidentDAO,
) -> List[IncidentRecord]:
    """
    数据库查询任务：获取所有活跃事件

    幂等性保证：相同时间点返回相同的活跃事件列表
    副作用：数据库查询
    """
    start_time = datetime.now(timezone.utc)
    logger.info("sitrep_fetch_incidents_start")

    incidents = await incident_dao.list_active_incidents()

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "sitrep_fetch_incidents_completed",
        incident_count=len(incidents),
        duration_ms=duration * 1000,
    )

    return incidents


@task
async def fetch_recent_tasks_task(
    task_dao: TaskDAO,
    hours: int,
) -> List[TaskSummary]:
    """
    数据库查询任务：获取最近N小时的任务

    幂等性保证：相同时间点+时间范围返回相同的任务列表
    副作用：数据库查询
    """
    start_time = datetime.now(timezone.utc)
    logger.info("sitrep_fetch_tasks_start", time_range_hours=hours)

    tasks = await task_dao.list_recent_tasks(hours=hours)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "sitrep_fetch_tasks_completed",
        task_count=len(tasks),
        duration_ms=duration * 1000,
    )

    return tasks


@task
async def fetch_risk_zones_task(
    risk_cache_manager: RiskCacheManager,
) -> List[RiskZoneRecord]:
    """
    缓存查询任务：获取活跃风险区域

    幂等性保证：强制刷新模式（force_refresh=True）确保获取最新数据
    副作用：缓存查询（可能触发数据库刷新）
    """
    start_time = datetime.now(timezone.utc)
    logger.info("sitrep_fetch_risks_start")

    # 强制刷新确保获取最新风险数据
    zones = await risk_cache_manager.get_active_zones(force_refresh=True)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "sitrep_fetch_risks_completed",
        zone_count=len(zones),
        duration_ms=duration * 1000,
    )

    return zones


@task
async def fetch_resource_usage_task(
    rescue_dao: RescueDAO,
) -> Dict[str, Any]:
    """
    数据库查询任务：获取资源使用情况统计

    幂等性保证：相同时间点返回相同的资源统计
    副作用：数据库查询
    """
    start_time = datetime.now(timezone.utc)
    logger.info("sitrep_fetch_resources_start")

    # 查询所有救援队员
    rescuers = await rescue_dao.list_rescuers()

    # 统计资源使用情况
    resource_usage = {
        "total_rescuers": len(rescuers),
        "deployed_teams": len(set(r.team_id for r in rescuers if r.team_id)),
        "available_rescuers": len([r for r in rescuers if r.status == "available"]),
        "busy_rescuers": len([r for r in rescuers if r.status == "busy"]),
        "offline_rescuers": len([r for r in rescuers if r.status == "offline"]),
    }

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "sitrep_fetch_resources_completed",
        total_rescuers=resource_usage["total_rescuers"],
        deployed_teams=resource_usage["deployed_teams"],
        duration_ms=duration * 1000,
    )

    return resource_usage


@task
async def call_llm_for_sitrep(
    llm_client: Any,
    llm_model: str,
    metrics: SITREPMetrics,
    incidents: List[IncidentRecord],
    tasks: List[TaskSummary],
    risks: List[RiskZoneRecord],
) -> str:
    """
    LLM调用任务：生成态势摘要

    幂等性保证：temperature=0确保相同输入返回稳定输出
    副作用：LLM API调用
    """
    start_time = datetime.now(timezone.utc)

    # 构建提示词（包含关键数据）
    prompt = _build_sitrep_prompt(metrics, incidents, tasks, risks)

    logger.info(
        "sitrep_llm_call_start",
        model=llm_model,
        prompt_length=len(prompt),
    )

    # 调用LLM（temperature=0确保稳定性）
    response = llm_client.chat.completions.create(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": "你是应急指挥系统的态势分析专家，负责生成简明、客观、专业的态势报告摘要。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,  # 确保输出稳定
    )

    summary = response.choices[0].message.content.strip()

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "sitrep_llm_call_completed",
        model=llm_model,
        summary_length=len(summary),
        duration_ms=duration * 1000,
    )

    return summary


@task
async def persist_snapshot_task(
    snapshot_repo: IncidentSnapshotRepository,
    snapshot_input: IncidentSnapshotCreateInput,
) -> str:
    """
    数据库写入任务：持久化态势报告快照

    幂等性保证：使用固定的report_id确保相同报告不会重复写入
    副作用：数据库写入
    """
    start_time = datetime.now(timezone.utc)
    logger.info("sitrep_persist_start")

    # 写入incident_snapshots表
    record = await snapshot_repo.create_snapshot(snapshot_input)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "sitrep_persist_completed",
        snapshot_id=record.snapshot_id,
        duration_ms=duration * 1000,
    )

    return record.snapshot_id


# ========== 节点函数：纯计算逻辑，无副作用，不需要@task ==========


def ingest(state: SITREPState) -> SITREPState:
    """
    入口节点：初始化和验证输入参数

    幂等性：纯计算节点，无副作用
    """
    logger.info(
        "sitrep_ingest_start",
        report_id=state["report_id"],
        incident_id=state.get("incident_id"),
        time_range_hours=state.get("time_range_hours"),
    )

    # 设置默认时间范围（24小时）
    time_range = state.get("time_range_hours", 24)

    return state | {
        "time_range_hours": time_range,
        "status": "ingested",
    }


def fetch_active_incidents(
    state: SITREPState,
    incident_dao: IncidentDAO,
) -> Dict[str, Any]:
    """
    数据采集节点：查询活跃事件

    幂等性：如果state中已有active_incidents，直接返回（避免重复查询）
    副作用：通过@task包装的函数执行数据库查询
    """
    # 幂等性检查
    if "active_incidents" in state and state["active_incidents"]:
        logger.info(
            "sitrep_fetch_incidents_skipped",
            report_id=state["report_id"],
            reason="already_fetched",
        )
        return {}

    # 调用@task包装的数据库查询
    incidents = fetch_active_incidents_task(incident_dao).result()

    # 如果指定了incident_id，过滤出特定事件
    if "incident_id" in state and state["incident_id"]:
        target_id = state["incident_id"]
        incidents = [i for i in incidents if i.id == target_id]
        logger.info(
            "sitrep_fetch_incidents_filtered",
            report_id=state["report_id"],
            target_incident_id=target_id,
            filtered_count=len(incidents),
        )

    return {"active_incidents": incidents}


def fetch_task_progress(
    state: SITREPState,
    task_dao: TaskDAO,
) -> Dict[str, Any]:
    """
    数据采集节点：查询任务进度

    幂等性：如果state中已有task_progress，直接返回
    副作用：通过@task包装的函数执行数据库查询
    """
    # 幂等性检查
    if "task_progress" in state and state["task_progress"]:
        logger.info(
            "sitrep_fetch_tasks_skipped",
            report_id=state["report_id"],
            reason="already_fetched",
        )
        return {}

    time_range = state.get("time_range_hours", 24)

    # 调用@task包装的数据库查询
    tasks = fetch_recent_tasks_task(task_dao, time_range).result()

    return {"task_progress": tasks}


def fetch_risk_zones(
    state: SITREPState,
    risk_cache_manager: RiskCacheManager,
) -> Dict[str, Any]:
    """
    数据采集节点：查询风险区域

    幂等性：如果state中已有risk_zones，直接返回
    副作用：通过@task包装的函数执行缓存查询
    """
    # 幂等性检查
    if "risk_zones" in state and state["risk_zones"]:
        logger.info(
            "sitrep_fetch_risks_skipped",
            report_id=state["report_id"],
            reason="already_fetched",
        )
        return {}

    # 调用@task包装的缓存查询
    zones = fetch_risk_zones_task(risk_cache_manager).result()

    return {"risk_zones": zones}


def fetch_resource_usage(
    state: SITREPState,
    rescue_dao: RescueDAO,
) -> Dict[str, Any]:
    """
    数据采集节点：查询资源使用情况

    幂等性：如果state中已有resource_usage，直接返回
    副作用：通过@task包装的函数执行数据库查询
    """
    # 幂等性检查
    if "resource_usage" in state and state["resource_usage"]:
        logger.info(
            "sitrep_fetch_resources_skipped",
            report_id=state["report_id"],
            reason="already_fetched",
        )
        return {}

    # 调用@task包装的数据库查询
    resource_usage = fetch_resource_usage_task(rescue_dao).result()

    return {"resource_usage": resource_usage}


def aggregate_metrics(state: SITREPState) -> Dict[str, Any]:
    """
    分析节点：聚合计算态势指标

    幂等性：纯计算节点，无副作用
    """
    logger.info("sitrep_aggregate_metrics_start", report_id=state["report_id"])

    incidents = state.get("active_incidents", [])
    tasks = state.get("task_progress", [])
    zones = state.get("risk_zones", [])
    resources = state.get("resource_usage", {})

    # 计算各项指标
    metrics: SITREPMetrics = {
        "active_incidents_count": len(incidents),
        "completed_tasks_count": len([t for t in tasks if t.status == "completed"]),
        "in_progress_tasks_count": len(
            [t for t in tasks if t.status == "in_progress"]
        ),
        "pending_tasks_count": len([t for t in tasks if t.status == "pending"]),
        "active_risk_zones_count": len(zones),
        "deployed_teams_count": resources.get("deployed_teams", 0),
        "total_rescuers_count": resources.get("total_rescuers", 0),
        "statistics_time_range_hours": state.get("time_range_hours", 24),
    }

    logger.info(
        "sitrep_aggregate_metrics_completed",
        report_id=state["report_id"],
        metrics=metrics,
    )

    return {"metrics": metrics}


def llm_generate_summary(
    state: SITREPState,
    llm_client: Any,
    llm_model: str,
) -> Dict[str, Any]:
    """
    LLM节点：生成态势摘要

    幂等性：如果state中已有llm_summary，直接返回
    副作用：通过@task包装的函数执行LLM调用
    """
    # 幂等性检查
    if "llm_summary" in state and state["llm_summary"]:
        logger.info(
            "sitrep_llm_summary_skipped",
            report_id=state["report_id"],
            reason="already_generated",
        )
        return {}

    metrics = state.get("metrics", {})
    incidents = state.get("active_incidents", [])
    tasks = state.get("task_progress", [])
    risks = state.get("risk_zones", [])

    # 调用@task包装的LLM函数
    summary = call_llm_for_sitrep(
        llm_client,
        llm_model,
        metrics,
        incidents,
        tasks,
        risks,
    ).result()

    return {"llm_summary": summary}


def persist_report(
    state: SITREPState,
    snapshot_repo: IncidentSnapshotRepository,
) -> Dict[str, Any]:
    """
    持久化节点：保存态势报告快照

    幂等性：如果state中已有snapshot_id，直接返回
    副作用：通过@task包装的函数执行数据库写入
    """
    # 幂等性检查
    if "snapshot_id" in state and state["snapshot_id"]:
        logger.info(
            "sitrep_persist_skipped",
            report_id=state["report_id"],
            reason="already_persisted",
        )
        return {}

    # 构建快照数据
    snapshot_input = IncidentSnapshotCreateInput(
        incident_id=state.get("incident_id") or "",  # 必填字段，如果没有就用空字符串
        snapshot_type="sitrep_report",  # 态势报告类型
        generated_at=datetime.now(timezone.utc),  # 必填字段
        created_by=state["user_id"],  # 必填字段
        payload={
            "report_id": state["report_id"],  # 将report_id放在payload中
            "metrics": state.get("metrics", {}),
            "summary": state.get("llm_summary", ""),
            "details": {
                "incidents": [
                    {
                        "id": i.id,
                        "title": i.title,
                        "type": i.type,
                        "priority": i.priority,
                        "status": i.status,
                    }
                    for i in state.get("active_incidents", [])
                ],
                "tasks": [
                    {
                        "id": t.id,
                        "code": t.code,
                        "status": t.status,
                        "progress": t.progress,
                    }
                    for t in state.get("task_progress", [])
                ],
                "risk_zones": [
                    {
                        "zone_id": z.zone_id,
                        "zone_name": z.zone_name,
                        "threat_type": z.threat_type,
                        "severity": z.severity,
                    }
                    for z in state.get("risk_zones", [])
                ],
                "resources": state.get("resource_usage", {}),
            },
            "time_range_hours": state.get("time_range_hours", 24),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 调用@task包装的持久化函数
    snapshot_id = persist_snapshot_task(snapshot_repo, snapshot_input).result()

    return {"snapshot_id": snapshot_id}


def finalize(state: SITREPState) -> Dict[str, Any]:
    """
    输出节点：构建最终SITREP报告

    幂等性：纯计算节点，无副作用
    """
    logger.info("sitrep_finalize_start", report_id=state["report_id"])

    # 构建最终报告
    report: SITREPReport = {
        "report_id": state["report_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": state.get("llm_summary", ""),
        "metrics": state.get("metrics", {}),
        "details": {
            "incidents": state.get("active_incidents", []),
            "tasks": state.get("task_progress", []),
            "risks": state.get("risk_zones", []),
            "resources": state.get("resource_usage", {}),
        },
        "snapshot_id": state.get("snapshot_id", ""),
    }

    logger.info(
        "sitrep_finalized",
        report_id=state["report_id"],
        snapshot_id=state.get("snapshot_id"),
        summary_length=len(state.get("llm_summary", "")),
    )

    return {
        "sitrep_report": report,
        "status": "completed",
    }


# ========== 辅助函数 ==========


def _build_sitrep_prompt(
    metrics: SITREPMetrics,
    incidents: List[IncidentRecord],
    tasks: List[TaskSummary],
    risks: List[RiskZoneRecord],
) -> str:
    """
    构建LLM提示词

    包含关键数据和生成要求
    """
    # 事件类型统计
    incident_types = {}
    for i in incidents:
        incident_types[i.type] = incident_types.get(i.type, 0) + 1

    # 任务状态统计
    task_statuses = {
        "completed": metrics.get("completed_tasks_count", 0),
        "in_progress": metrics.get("in_progress_tasks_count", 0),
        "pending": metrics.get("pending_tasks_count", 0),
    }

    # 风险类型统计
    risk_types = {}
    for r in risks:
        risk_types[r.threat_type] = risk_types.get(r.threat_type, 0) + 1

    prompt = f"""请根据以下态势数据生成一份简明、客观、专业的态势报告摘要（200-500字）。

# 当前态势数据

## 事件情况
- 活跃事件总数：{metrics.get("active_incidents_count", 0)}个
- 事件类型分布：{incident_types}

## 任务进度
- 已完成任务：{task_statuses['completed']}个
- 进行中任务：{task_statuses['in_progress']}个
- 待办任务：{task_statuses['pending']}个

## 风险区域
- 活跃风险区域：{metrics.get("active_risk_zones_count", 0)}个
- 风险类型分布：{risk_types}

## 资源部署
- 部署队伍数：{metrics.get("deployed_teams_count", 0)}支
- 救援人员数：{metrics.get("total_rescuers_count", 0)}人

# 生成要求

摘要应包含以下内容：
1. **总体态势概述**（1-2句）：简要描述当前救援态势
2. **关键进展和成果**（2-3点）：突出已完成的重要任务和成果
3. **当前风险和挑战**（2-3点）：指出当前面临的主要风险和问题
4. **后续行动建议**（2-3点）：提出下一步的关键行动建议

要求：
- 语气专业、简洁、客观
- 使用中文
- 总长度200-500字
- 突出重点，避免堆砌数字
"""

    return prompt


# ========== Graph构建函数 ==========


async def build_sitrep_graph(
    incident_dao: IncidentDAO,
    task_dao: TaskDAO,
    risk_cache_manager: RiskCacheManager,
    rescue_dao: RescueDAO,
    snapshot_repo: IncidentSnapshotRepository,
    llm_client: Any,
    llm_model: str,
    checkpointer: AsyncPostgresSaver,
) -> Any:
    """
    构建态势上报LangGraph子图

    参考：
    - rescue_tactical_app.py:build_rescue_tactical_graph
    - concept-durable-execution.md:26

    Args:
        incident_dao: 事件DAO
        task_dao: 任务DAO
        risk_cache_manager: 风险缓存管理器
        rescue_dao: 救援DAO
        snapshot_repo: 快照仓库
        llm_client: LLM客户端
        llm_model: LLM模型名称
        checkpointer: 异步PostgreSQL检查点管理器

    Returns:
        编译后的LangGraph应用
    """
    logger.info("sitrep_graph_build_start")

    # 创建StateGraph
    graph = StateGraph(SITREPState)

    # 添加节点（使用闭包捕获依赖）
    graph.add_node("ingest", ingest)
    graph.add_node(
        "fetch_active_incidents",
        lambda state: fetch_active_incidents(state, incident_dao),
    )
    graph.add_node(
        "fetch_task_progress",
        lambda state: fetch_task_progress(state, task_dao),
    )
    graph.add_node(
        "fetch_risk_zones",
        lambda state: fetch_risk_zones(state, risk_cache_manager),
    )
    graph.add_node(
        "fetch_resource_usage",
        lambda state: fetch_resource_usage(state, rescue_dao),
    )
    graph.add_node("aggregate_metrics", aggregate_metrics)
    graph.add_node(
        "llm_generate_summary",
        lambda state: llm_generate_summary(state, llm_client, llm_model),
    )
    graph.add_node(
        "persist_report",
        lambda state: persist_report(state, snapshot_repo),
    )
    graph.add_node("finalize", finalize)

    # 配置线性流程边
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "fetch_active_incidents")
    graph.add_edge("fetch_active_incidents", "fetch_task_progress")
    graph.add_edge("fetch_task_progress", "fetch_risk_zones")
    graph.add_edge("fetch_risk_zones", "fetch_resource_usage")
    graph.add_edge("fetch_resource_usage", "aggregate_metrics")
    graph.add_edge("aggregate_metrics", "llm_generate_summary")
    graph.add_edge("llm_generate_summary", "persist_report")
    graph.add_edge("persist_report", "finalize")
    graph.add_edge("finalize", END)

    # 编译graph（使用checkpointer支持持久化和中断恢复）
    # 注意：SITREP不需要interrupt_before，因为是自动化流程无需人工审批
    app = graph.compile(checkpointer=checkpointer)

    logger.info("sitrep_graph_build_completed")

    return app
