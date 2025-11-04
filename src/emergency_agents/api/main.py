#!/usr/bin/env python3
# Copyright 2025 msq
from __future__ import annotations

import inspect
import uuid
import asyncio
from contextlib import suppress
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Literal

import structlog
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from emergency_agents.config import AppConfig
from emergency_agents.logging import configure_logging, set_trace_id, clear_trace_id  # 统一日志配置
from emergency_agents.api.voice_chat import handle_voice_chat, voice_chat_handler
from emergency_agents.api import rescue as rescue_api
from emergency_agents.api import plan as plan_api
from emergency_agents.api import overall_rescue as overall_rescue_api
from emergency_agents.api import recon_priority as recon_priority_api
from emergency_agents.api import recon_batch_weather as recon_batch_weather_api
from emergency_agents.api import sitrep as sitrep_api
from emergency_agents.api import reports as reports_api
from emergency_agents.api import recon as recon_api
from emergency_agents.external.adapter_client import AdapterHubClient
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.app import build_app
from emergency_agents.graph.intent_orchestrator_app import build_intent_orchestrator_graph
from emergency_agents.graph.voice_control_app import build_voice_control_graph
from emergency_agents.graph.sitrep_app import build_sitrep_graph
from emergency_agents.graph.recon_app import build_recon_graph_async
from emergency_agents.external.recon_gateway import PostgresReconGateway
from emergency_agents.planner.recon_llm import OpenAIReconLLMEngine, ReconLLMConfig
from emergency_agents.planner.recon_pipeline import ReconPipeline
from emergency_agents.memory.conversation_manager import (
    ConversationManager,
    ConversationNotFoundError,
    MessageRecord,
)
from emergency_agents.memory.mem0_facade import Mem0Config, MemoryFacade
from emergency_agents.llm.client import get_openai_client
from emergency_agents.llm.factory import LLMClientFactory
from emergency_agents.rag.pipe import RagPipeline, RagChunk
from emergency_agents.graph.kg_service import KGService, KGConfig
from emergency_agents.db.dao import (
    IncidentDAO,
    IncidentRepository,
    IncidentSnapshotRepository,
    RescueTaskRepository,
    TaskDAO,
    RescueDAO,
)
from emergency_agents.audit.logger import get_audit_logger, log_human_approval
from langgraph.types import Command
from emergency_agents.voice.asr.service import ASRService
from emergency_agents.voice.asr.base import ASRConfig as ASRConfigModel
from emergency_agents.intent.classifier import intent_classifier_node
from emergency_agents.intent.prompt_missing import prompt_missing_slots_node
from emergency_agents.intent.registry import IntentHandlerRegistry
from emergency_agents.context.service import ContextService
from emergency_agents.intent.validator import validate_and_prompt_node
from emergency_agents.api.intent_processor import (
    IntentProcessResult,
    Mem0Metrics,
    process_intent_core,
)
from emergency_agents.control import VoiceControlPipeline
from emergency_agents.external.device_directory import PostgresDeviceDirectory
from emergency_agents.risk import RiskCacheManager, RiskDataRepository, RiskPredictor
from emergency_agents.services import RescueDraftService


class Domain(str, Enum):
    """受支持的知识域。"""
    SPEC = "规范"
    CASE = "案例"
    GEO = "地理"
    EQUIP = "装备"


app = FastAPI(title="AI Emergency Brain API")
_cfg = AppConfig.load_from_env()
if not _cfg.postgres_dsn:
    raise RuntimeError("POSTGRES_DSN 未配置，无法启动服务。")
_graph_app: Any | None = None
_intent_graph: Any | None = None
_voice_control_graph: Any | None = None
_sitrep_graph: Any | None = None
_recon_graph: Any | None = None
_graph_closers: list[Callable[[], Awaitable[None]]] = []
_context_service: ContextService | None = None


# ========== Trace-ID中间件：自动注入请求追踪ID ==========
class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    为每个HTTP请求注入trace-id到日志上下文

    支持：
    1. 客户端传入 X-Trace-Id 请求头（复用trace-id）
    2. 自动生成 UUID trace-id（新请求）
    3. 响应头返回 X-Trace-Id（便于客户端日志关联）

    参考：emergency_agents.logging 模块文档
    """

    async def dispatch(self, request: Request, call_next):
        # 提取或生成trace-id
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        set_trace_id(trace_id)

        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            # 清理上下文，防止泄漏
            clear_trace_id()


app.add_middleware(TraceIDMiddleware)


# metrics
Instrumentator().instrument(app).expose(app)

# custom metrics
_assist_counter = Counter('assist_answer_total', 'Total /assist/answer requests')
_assist_failures = Counter('assist_answer_failures_total', 'Total /assist/answer failures')
_assist_latency = Histogram('assist_answer_seconds', 'Latency of /assist/answer')

_mem0_search_success = Counter("mem0_search_success_total", "mem0检索成功次数")
_mem0_search_failure = Counter(
    "mem0_search_failure_total",
    "mem0检索失败次数",
    ["reason"],
)
_mem0_search_duration = Histogram(
    "mem0_search_duration_seconds",
    "mem0检索耗时（秒）",
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
)
_mem0_add_success = Counter("mem0_add_success_total", "mem0写入成功次数")
_mem0_add_failure = Counter(
    "mem0_add_failure_total",
    "mem0写入失败次数",
    ["reason"],
)

# memory facade singleton
_mem = MemoryFacade(
    Mem0Config(
        qdrant_url=_cfg.qdrant_url or "http://192.168.1.40:6333",
        qdrant_api_key=_cfg.qdrant_api_key,
        qdrant_collection="mem0_collection",
        embedding_model=_cfg.embedding_model,
        embedding_dim=_cfg.embedding_dim,
        neo4j_uri=_cfg.neo4j_uri or "bolt://192.168.1.40:7687",
        neo4j_user=_cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        neo4j_password=_cfg.neo4j_password or "example-neo4j",
        openai_base_url=_cfg.openai_base_url,
        # pragma: allowlist secret - placeholder credential for development
        openai_api_key=_cfg.openai_api_key,
        graph_llm_model=_cfg.llm_model,
    )
)

# rag pipeline singleton
_rag = RagPipeline(
    qdrant_url=_cfg.qdrant_url or "http://192.168.1.40:6333",
    qdrant_api_key=_cfg.qdrant_api_key,
    embedding_model=_cfg.embedding_model,
    embedding_dim=_cfg.embedding_dim,
    openai_base_url=_cfg.openai_base_url,
    openai_api_key=_cfg.openai_api_key,
    llm_model=_cfg.llm_model,
)

# kg service singleton
_kg = KGService(
    KGConfig(
        uri=_cfg.neo4j_uri or "bolt://192.168.1.40:7687",
        user=_cfg.neo4j_user or "neo4j",
        # pragma: allowlist secret - placeholder credential for development
        password=_cfg.neo4j_password or "example-neo4j",
    )
)

if not _cfg.postgres_dsn:
    raise RuntimeError("必须配置POSTGRES_DSN以启用会话服务")

_pg_pool: AsyncConnectionPool[DictRow] = AsyncConnectionPool(
    conninfo=_cfg.postgres_dsn,
    min_size=1,
    max_size=4,
    open=False,
)
_conversation_manager = ConversationManager(_pg_pool)

_incident_repository = IncidentRepository.create(_pg_pool)
_incident_snapshot_repository = IncidentSnapshotRepository.create(_pg_pool)
_rescue_task_repository = RescueTaskRepository.create(_pg_pool)
_rescue_draft_service = RescueDraftService(
    incident_repository=_incident_repository,
    snapshot_repository=_incident_snapshot_repository,
    task_repository=_rescue_task_repository,
)

_llm_factory = LLMClientFactory(_cfg)
_llm_clients = {
    "default": _llm_factory.get_sync("default"),
    "rescue": _llm_factory.get_sync("rescue"),
    "intent": _llm_factory.get_sync("intent"),
    "strategic": _llm_factory.get_sync("strategic"),
}
app.state.llm_clients = _llm_clients
app.state.rescue_draft_service = _rescue_draft_service
_llm_client_default = _llm_clients["default"]
_llm_client_rescue = _llm_clients["rescue"]
_intent_llm_client = _llm_clients["intent"]
_llm_client_strategic = _llm_clients["strategic"]

_adapter_client = AdapterHubClient(
    base_url=_cfg.adapter_base_url,
    timeout=_cfg.adapter_timeout,
)

_device_directory_pool: ConnectionPool | None = None
_device_directory: PostgresDeviceDirectory | None = None
_voice_control_pipeline: VoiceControlPipeline | None = None
_recon_sync_pool: ConnectionPool | None = None

_amap_client = AmapClient(
    api_key=_cfg.amap_api_key or "",
    backup_key=_cfg.amap_backup_key,
    base_url=_cfg.amap_base_url or "https://restapi.amap.com",
    connect_timeout=_cfg.amap_connect_timeout,
    read_timeout=_cfg.amap_read_timeout,
)

_orchestrator_client = OrchestratorClient()

# IntentHandlerRegistry需要异步初始化，在startup_event中完成
_intent_registry: IntentHandlerRegistry | None = None

_risk_cache_manager: RiskCacheManager | None = None
_risk_refresh_task: asyncio.Task[None] | None = None
_risk_predictor: RiskPredictor | None = None
_risk_predict_task: asyncio.Task[None] | None = None

app.include_router(rescue_api.router)
app.include_router(sitrep_api.router, prefix="/sitrep", tags=["sitrep"])
app.include_router(reports_api.router)
app.include_router(recon_api.router)
app.include_router(overall_rescue_api.router)
app.include_router(recon_priority_api.router)
app.include_router(recon_batch_weather_api.router)


def _classifier_wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
    """意图分类器包装器"""
    return intent_classifier_node(
        state,
        llm_client=_intent_llm_client,
        llm_model=_cfg.intent_llm_model or _cfg.llm_model,
    )


def _validator_wrapper(state: Dict[str, Any], llm_client: Any, llm_model: str) -> Dict[str, Any]:
    # 预归一化：将别名/下划线形式统一成短横线，避免schema查找遗漏
    intent = state.get("intent") or {}
    itype_raw = str((intent.get("intent_type") or "").strip())
    norm = itype_raw.replace(" ", "").replace("_", "-").lower()
    if norm in ("video-analysis", "video-analyze"):
        state = state | {"intent": intent | {"intent_type": "video-analysis"}}
    if norm in ("task-progress-query", "taskprogressquery"):
        state = state | {"intent": intent | {"intent_type": "task-progress-query"}}
    return validate_and_prompt_node(state, llm_client, llm_model)


def _prompt_wrapper(state: Dict[str, Any], llm_client: Any, llm_model: str) -> Dict[str, Any]:
    # 增强：当视频分析缺少设备名时，提供结构化候选（DAO+Mem0）
    # 为视频分析构造结构化候选（同步查询 device_video_link）
    try:
        intent = state.get("intent") or {}
        itype = str((intent.get("intent_type") or "").strip()).lower()
        itype_norm = itype.replace(" ", "").replace("_", "-")
        if itype_norm in ("video-analysis", "video-analyze"):
            import psycopg
            from emergency_agents.intent.prompt_missing import prompt_missing_slots_enhanced
            from emergency_agents.intent.schemas import ClarifyOption

            options: list[ClarifyOption] = []
            # 同步查询：优先 device_video_link，其次 device_detail.stream_url
            sql = (
                "WITH candidates AS (\n"
                "  SELECT d.id::text AS id, d.name AS name\n"
                "    FROM operational.device d\n"
                "    JOIN operational.device_video_link dvl ON dvl.id = d.id\n"
                "   WHERE COALESCE(NULLIF(dvl.video_link, ''), '') <> ''\n"
                "  UNION ALL\n"
                "  SELECT d.id::text AS id, d.name AS name\n"
                "    FROM operational.device d\n"
                "    JOIN operational.device_detail dd ON dd.device_id = d.id\n"
                "   WHERE COALESCE(NULLIF(dd.device_detail->>'stream_url', ''), '') <> ''\n"
                ") SELECT id, name FROM candidates GROUP BY id, name ORDER BY name ASC LIMIT 10"
            )
            with psycopg.connect(_cfg.postgres_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for dev_id, name in cur.fetchall():
                        options.append({"label": name or dev_id, "device_id": dev_id})
            return prompt_missing_slots_enhanced(state, llm_client, llm_model, options=options)
    except Exception:
        pass
    # 其它意图退回通用文本澄清
    return prompt_missing_slots_node(state, llm_client, llm_model)


_asr = ASRService()
logger = structlog.get_logger(__name__)


def _require_conversation_manager() -> ConversationManager:
    if _conversation_manager is None:
        raise RuntimeError("ConversationManager 未初始化")
    return _conversation_manager


def _require_intent_registry() -> IntentHandlerRegistry:
    if _intent_registry is None:
        raise RuntimeError("IntentHandlerRegistry 未初始化")
    return _intent_registry

def _require_rescue_graph() -> Any:
    if _graph_app is None:
        raise RuntimeError("救援编排子图未初始化")
    return _graph_app


def _require_intent_graph() -> Any:
    if _intent_graph is None:
        raise RuntimeError("意图编排子图未构建")
    return _intent_graph


def _require_voice_control_graph() -> Any:
    graph = getattr(app.state, "voice_control_graph", None)
    if graph is None:
        if _voice_control_graph is None:
            raise RuntimeError("语音控制子图未初始化")
        app.state.voice_control_graph = _voice_control_graph
        return _voice_control_graph
    return graph


def _build_history(records: List[MessageRecord]) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for record in records:
        history.append(
            {
                "id": record.id,
                "role": record.role,
                "content": record.content,
                "intent_type": record.intent_type,
                "event_time": record.event_time.isoformat(),
            }
        )
    return history


def _mem0_metrics_factory() -> Mem0Metrics:
    return Mem0Metrics(
        inc_search_success=_mem0_search_success.inc,
        inc_search_failure=lambda reason: _mem0_search_failure.labels(reason=reason).inc(),
        observe_search_duration=_mem0_search_duration.observe,
        inc_add_success=_mem0_add_success.inc,
        inc_add_failure=lambda reason: _mem0_add_failure.labels(reason=reason).inc(),
    )


def _register_graph_close(resource: Any) -> None:
    """记录需要在shutdown阶段关闭的图资源。"""
    close_cb = getattr(resource, "_checkpoint_close", None)
    if callable(close_cb):
        _graph_closers.append(close_cb)


@app.on_event("startup")
async def startup_event():
    # 🔧 统一日志配置（生产环境使用JSON格式，开发环境使用控制台）
    import os
    json_logs = os.getenv("LOG_JSON", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(json_logs=json_logs, log_level=log_level)

    global _graph_app
    global _intent_graph
    global _voice_control_graph
    global _sitrep_graph
    global _graph_closers
    global _risk_cache_manager
    global _risk_refresh_task
    global _risk_predictor
    global _risk_predict_task
    global _intent_registry  # 新增
    global _context_service
    global _recon_sync_pool

    await _pg_pool.open()
    logger.info("api_startup_pg_pool_opened")
    await _asr.start_health_check()
    await voice_chat_handler.start_background_tasks()
    _graph_closers = []

    # 延迟初始化设备目录连接池，避免模块导入阶段占用数据库连接
    global _device_directory_pool
    global _device_directory
    global _voice_control_pipeline
    if _device_directory_pool is None:
        _device_directory_pool = ConnectionPool(
            conninfo=_cfg.postgres_dsn,
            min_size=1,
            max_size=3,
            open=True,
        )
        _device_directory_pool.wait(timeout=60.0)
        _device_directory = PostgresDeviceDirectory(_device_directory_pool)
        _voice_control_pipeline = VoiceControlPipeline(
            default_robotdog_id=_cfg.default_robotdog_id,
            device_directory=_device_directory,
        )

    # 初始化IntentHandlerRegistry（异步初始化，包含ScoutTaskGenerationHandler懒加载）
    _intent_registry = await IntentHandlerRegistry.build(
        pool=_pg_pool,
        amap_client=_amap_client,
        device_directory=_device_directory,
        video_stream_map=_cfg.video_stream_map,
        kg_service=_kg,
        rag_pipeline=_rag,
        llm_client=_llm_client_rescue,
        llm_model=_cfg.llm_model,
        adapter_client=_adapter_client,
        default_robotdog_id=_cfg.default_robotdog_id,
        orchestrator_client=_orchestrator_client,
        rag_timeout=_cfg.rag_analysis_timeout,
        postgres_dsn=_cfg.postgres_dsn,
        vllm_url=_cfg.openai_base_url,  # GLM-4V 使用相同的 OpenAI 兼容端点
    )
    _intent_registry.attach_rescue_draft_service(_rescue_draft_service)
    logger.info("api_intent_registry_initialized")

    _graph_app = await build_app(_cfg.checkpoint_sqlite_path, _cfg.postgres_dsn)
    _register_graph_close(_graph_app)
    logger.info("api_graph_ready", graph="rescue_app")

    _intent_graph = await build_intent_orchestrator_graph(
        cfg=_cfg,
        llm_client=_intent_llm_client,
        llm_model=_cfg.intent_llm_model or _cfg.llm_model,
        classifier_node=_classifier_wrapper,
        validator_node=_validator_wrapper,
        prompt_node=_prompt_wrapper,
    )
    _register_graph_close(_intent_graph)
    logger.info("api_graph_ready", graph="intent_orchestrator")

    # 会话上下文服务（基于全局 AsyncConnectionPool）
    _context_service = ContextService(pool=_pg_pool)

    if _voice_control_pipeline is None:
        raise RuntimeError("VoiceControlPipeline 未初始化")

    _voice_control_graph = await build_voice_control_graph(
        pipeline=_voice_control_pipeline,
        adapter_client=_adapter_client,
        postgres_dsn=_cfg.postgres_dsn,
    )
    _register_graph_close(_voice_control_graph)
    app.state.voice_control_graph = _voice_control_graph
    logger.info("api_graph_ready", graph="voice_control")

    # 初始化RiskCacheManager（SITREP依赖它）
    incident_dao = IncidentDAO.create(_pg_pool)
    _risk_cache_manager = RiskCacheManager(
        incident_dao=incident_dao,
        ttl_seconds=_cfg.risk_cache_ttl_seconds,
    )
    await _risk_cache_manager.prefetch()
    app.state.risk_cache = _risk_cache_manager
    refresh_interval = _cfg.risk_refresh_interval_seconds
    _risk_refresh_task = asyncio.create_task(
        _risk_cache_manager.periodic_refresh(refresh_interval)
    )
    repository = RiskDataRepository(incident_dao)
    _risk_predictor = RiskPredictor(repository, _risk_cache_manager)
    await _risk_predictor.analyze()
    app.state.risk_predictor = _risk_predictor
    _risk_predict_task = asyncio.create_task(
        _risk_predictor.run_periodic(refresh_interval)
    )

    # 绑定 /ai/plan 路由（战略/救援方案）
    # 依赖注入: 供 /ai/plan/from-progress 使用
    plan_api._pg_pool_async = _pg_pool  # type: ignore[assignment]
    app.include_router(plan_api.router)
    # 绑定 /ai/rescue 路由（整体救援方案）
    overall_rescue_api._pg_pool_async = _pg_pool  # type: ignore[assignment]
    recon_priority_api._pg_pool_async = _pg_pool  # type: ignore[assignment]
    recon_batch_weather_api._pg_pool_async = _pg_pool  # type: ignore[assignment]

    # ========== 初始化SITREP子图 ==========
    task_dao = TaskDAO.create(_pg_pool)
    rescue_dao = RescueDAO.create(_pg_pool)
    snapshot_repo = IncidentSnapshotRepository.create(_pg_pool)

    # 创建checkpointer（复用PostgreSQL连接池）
    from emergency_agents.graph.checkpoint_utils import create_async_postgres_checkpointer
    sitrep_checkpointer, sitrep_close_cb = await create_async_postgres_checkpointer(
        dsn=_cfg.postgres_dsn,
        schema="sitrep_checkpoint",
        min_size=1,
        max_size=1,
    )

    _sitrep_graph = await build_sitrep_graph(
        incident_dao=incident_dao,
        task_dao=task_dao,
        risk_cache_manager=_risk_cache_manager,  # 复用已初始化的risk_cache_manager
        rescue_dao=rescue_dao,
        snapshot_repo=snapshot_repo,
        llm_client=_llm_client_rescue,
        llm_model=_cfg.llm_model,
        checkpointer=sitrep_checkpointer,
    )
    _sitrep_graph._checkpoint_close = sitrep_close_cb  # 注册关闭回调
    _register_graph_close(_sitrep_graph)
    logger.info("api_graph_ready", graph="sitrep")

    # 将依赖注入到sitrep_api模块
    sitrep_api._sitrep_graph = _sitrep_graph
    sitrep_api._incident_dao = incident_dao
    sitrep_api._snapshot_repo = snapshot_repo
    # ========== SITREP子图初始化完成 ==========

    # ========== 注入Reports API依赖 ==========
    reports_api._kg_service = _kg
    reports_api._rag_pipeline = _rag
    logger.info("api_reports_dependencies_injected")
    # ========== Reports API依赖注入完成 ==========

    if _intent_registry is not None:
        _intent_registry.attach_risk_cache(_risk_cache_manager)
    logger.info(
        "risk_cache_startup_initialized",
        ttl_seconds=_cfg.risk_cache_ttl_seconds,
        refresh_interval_seconds=refresh_interval,
    )

    # ========== 初始化RECON子图(侦察方案) ==========
    # 使用与全局一致的数据库,但在checkpoint层使用独立schema(recon_checkpoint)
    if not _cfg.recon_llm_model or not _cfg.recon_llm_base_url or not _cfg.recon_llm_api_key:
        # 遵循“不兜底/不降级”: 明确要求配置RECON LLM参数
        raise RuntimeError("RECON_LLM_* 未配置,无法初始化侦察子图")

    # 构造同步ConnectionPool用于网关(与Async连接池并存,职责分离)
    _recon_sync_pool = ConnectionPool(
        conninfo=_cfg.postgres_dsn,
        min_size=1,
        max_size=1,
        open=True,
    )
    recon_gateway = PostgresReconGateway(_recon_sync_pool)

    # 按需固定侦察LLM模型（接口明确要求固定使用 glm4.6）
    recon_llm = OpenAIReconLLMEngine(
        config=ReconLLMConfig(
            model="glm-4.6",
            base_url=_cfg.recon_llm_base_url,
            api_key=_cfg.recon_llm_api_key,
            temperature=0.2,
            timeout_seconds=_cfg.llm_request_timeout_seconds,
        )
    )
    recon_pipeline = ReconPipeline(gateway=recon_gateway, llm_engine=recon_llm)

    _recon_graph = await build_recon_graph_async(
        pipeline=recon_pipeline,
        gateway=recon_gateway,
        dsn=_cfg.postgres_dsn,
        schema="recon_checkpoint",
    )
    _register_graph_close(_recon_graph)
    app.state.recon_graph = _recon_graph
    app.state.recon_gateway = recon_gateway
    plan_api._recon_gateway = recon_gateway  # type: ignore[assignment]
    logger.info("api_graph_ready", graph="recon")


@app.on_event("shutdown")
async def shutdown_event():
    global _graph_app
    global _intent_graph
    global _voice_control_graph
    global _sitrep_graph
    global _recon_graph
    global _graph_closers
    global _risk_cache_manager
    global _risk_refresh_task
    global _risk_predictor
    global _risk_predict_task
    global _recon_sync_pool
    await voice_chat_handler.stop_background_tasks()
    await _asr.stop_health_check()
    await _adapter_client.aclose()
    await _amap_client.close()
    _orchestrator_client.close()
    logger.info("api_shutdown_services_stopped")
    for close_cb in _graph_closers:
        await close_cb()
    _graph_closers.clear()
    _graph_app_attr = _graph_app if _graph_app is not None else None
    for resource in (_graph_app_attr, _intent_graph, _voice_control_graph, _sitrep_graph):
        if resource is not None and hasattr(resource, "_checkpoint_close"):
            setattr(resource, "_checkpoint_close", None)
    logger.info("api_shutdown_graphs_closed")
    _graph_app = None
    _intent_graph = None
    _voice_control_graph = None
    _sitrep_graph = None
    _recon_graph = None

    if hasattr(_intent_registry, "close"):
        close_result = _intent_registry.close()
        if inspect.isawaitable(close_result):
            await close_result
    await _pg_pool.close()
    if _device_directory_pool is not None:
        _device_directory_pool.close()
    if _recon_sync_pool is not None:
        try:
            _recon_sync_pool.close()
        except Exception:
            pass
        _recon_sync_pool = None
    for task in (_risk_refresh_task, _risk_predict_task):
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    _risk_refresh_task = None
    _risk_predict_task = None
    if _intent_registry is not None:
        _intent_registry.attach_risk_cache(None)
    _risk_cache_manager = None
    if hasattr(app.state, "risk_cache"):
        delattr(app.state, "risk_cache")
    if hasattr(app.state, "risk_predictor"):
        delattr(app.state, "risk_predictor")
    _risk_predictor = None


class RagDoc(BaseModel):
    """RAG 文档输入。"""
    id: str
    text: str
    meta: Optional[Dict[str, Any]] = None


class RagIndexRequest(BaseModel):
    """批量索引请求。"""
    domain: Domain
    docs: List[RagDoc]


class RagQueryRequest(BaseModel):
    """RAG 检索请求。"""
    domain: Domain
    question: str
    top_k: int = Field(3, ge=1, le=10, description="返回片段数量上限")


class KGRecommendRequest(BaseModel):
    """装备推荐请求。"""
    hazard: str
    environment: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20)


class KGCaseSearchRequest(BaseModel):
    """案例检索请求。"""
    keywords: str
    top_k: int = Field(5, ge=1, le=20)


class IntentProcessRequest(BaseModel):
    """意图处理请求体。"""

    user_id: str
    thread_id: str
    message: str
    metadata: Dict[str, Any] | None = None
    incident_id: Optional[str] = None
    channel: Literal["voice", "text", "system"] = "text"


class ConversationHistoryRequest(BaseModel):
    """会话历史查询请求。"""

    user_id: str
    thread_id: str
    limit: int = Field(20, ge=1, le=100)


class AssistAnswerRequest(BaseModel):
    """智能回答请求。"""
    user_id: str
    run_id: str
    domain: Domain
    question: str
    top_k: int = Field(3, ge=1, le=10)


class StartThreadRequest(BaseModel):
    """启动救援线程请求"""
    raw_report: str = Field(..., description="非结构化灾情报告")
    user_id: Optional[str] = Field(None, description="用户ID")


@app.post("/threads/start")
async def start_thread(rescue_id: str, req: StartThreadRequest):
    """创建救援线程并进入人工审批中断点。"""
    init_state = {
        "rescue_id": rescue_id,
        "user_id": req.user_id or "unknown",
        "raw_report": req.raw_report
    }
    result = _require_rescue_graph().invoke(
        init_state,
        config={
            "configurable": {
                "thread_id": f"rescue-{rescue_id}",
                "checkpoint_ns": f"tenant-{init_state['user_id']}",
            },
            "durability": "sync",  # 长流程（救援线程），同步保存checkpoint确保高可靠性
        },
    )
    return {"rescue_id": rescue_id, "state": result}


class ApproveRequest(BaseModel):
    """审批请求"""
    approved_ids: List[str] = Field(..., description="批准的提案ID列表")
    comment: Optional[str] = Field(None, description="审批意见")


@app.post("/threads/approve")
async def approve_thread(rescue_id: str, user_id: str, req: ApproveRequest):
    """审批救援方案。"""
    log_human_approval(
        rescue_id=rescue_id,
        user_id=user_id,
        approved_ids=req.approved_ids,
        comment=req.comment,
        thread_id=f"rescue-{rescue_id}"
    )
    
    # 动态中断恢复：使用 Command(resume=[...]) 将批准的ID注入 await 节点
    result = _require_rescue_graph().invoke(
        Command(resume=req.approved_ids),
        config={
            "configurable": {"thread_id": f"rescue-{rescue_id}"},
            "durability": "sync",  # 长流程（救援线程），同步保存checkpoint确保高可靠性
        },
    )
    return {"rescue_id": rescue_id, "approved": True, "state": result}


@app.post("/threads/resume")
async def resume_thread(rescue_id: str):
    """继续执行指定救援线程。"""
    result = _require_rescue_graph().invoke(
        None,
        config={
            "configurable": {"thread_id": f"rescue-{rescue_id}"},
            "durability": "sync",  # 长流程（救援线程），同步保存checkpoint确保高可靠性
        },
    )
    return {"rescue_id": rescue_id, "state": result}


@app.get("/audit/trail/{rescue_id}")
async def get_audit_trail(rescue_id: str):
    """获取审计轨迹。"""
    audit_logger = get_audit_logger()
    trail = audit_logger.get_trail(rescue_id)
    return {"rescue_id": rescue_id, "trail": trail, "count": len(trail)}


@app.get("/healthz")
async def healthz():
    """健康探针。"""
    return {"status": "ok"}


@app.post("/memory/add")
async def memory_add(content: str, user_id: str, run_id: Optional[str] = None, agent_id: Optional[str] = None):
    """新增记忆记录。"""
    _mem.add(content=content, user_id=user_id, run_id=run_id, agent_id=agent_id)
    return {"ok": True}


@app.get("/memory/search")
async def memory_search(query: str, user_id: str, run_id: Optional[str] = None, agent_id: Optional[str] = None, top_k: int = 5):
    """检索记忆记录。"""
    res = _mem.search(query=query, user_id=user_id, run_id=run_id, agent_id=agent_id, top_k=top_k)
    return {"results": res}


@app.post("/rag/index")
async def rag_index(req: RagIndexRequest):
    """批量索引文档到 RAG 存储。"""
    _rag.index_documents(req.domain.value, [d.model_dump() for d in req.docs])
    return {"ok": True, "count": len(req.docs), "trace_id": str(uuid.uuid4())}


@app.post("/rag/query")
async def rag_query(req: RagQueryRequest):
    """执行 RAG 相似度检索。"""
    chunks: List[RagChunk] = _rag.query(req.question, req.domain.value, req.top_k)
    return {"trace_id": str(uuid.uuid4()), "results": [
        {"text": c.text, "source": c.source, "loc": c.loc} for c in chunks
    ]}


@app.post("/asr/recognize")
async def asr_recognize(file: UploadFile = File(...), sample_rate: int = 16000, fmt: str = "pcm"):
    """上传单段音频并返回识别文本。

    ASR 使用自动故障转移机制:Aliyun(主)→ Local FunASR(备),后台健康检查每 30 秒执行一次。
    支持 PCM/WAV（若为 WAV，应由调用方传入裸音频数据或确保服务端获取到 PCM 数据）。
    """

    try:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="empty file")
        cfg = ASRConfigModel(format=fmt, sample_rate=sample_rate)
        result = await _asr.recognize(data, cfg)
        return {
            "provider": _asr.provider_name,
            "text": result.text,
            "latency_ms": result.latency_ms,
            "confidence": result.confidence,
            "metadata": result.metadata or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kg/recommend")
async def kg_recommend(req: KGRecommendRequest):
    """根据危害/环境推荐装备。"""
    items = _kg.recommend_equipment(hazard=req.hazard, environment=req.environment, top_k=req.top_k)
    return {"trace_id": str(uuid.uuid4()), "recommendations": items}


@app.post("/kg/cases/search")
async def kg_search(req: KGCaseSearchRequest):
    """按关键词检索案例。"""
    items = _kg.search_cases(keywords=req.keywords, top_k=req.top_k)
    return {"trace_id": str(uuid.uuid4()), "results": items}


@app.post("/assist/answer")
async def assist_answer(req: AssistAnswerRequest):
    """结合 RAG 与记忆生成带引用的回答。"""
    _assist_counter.inc()
    trace_id = str(uuid.uuid4())
    with _assist_latency.time():
        try:
            # 1) 检索 RAG 片段
            rag_chunks: List[RagChunk] = _rag.query(req.question, req.domain.value, req.top_k)
            # 2) 检索 Mem0 记忆
            mem_results = _mem.search(query=req.question, user_id=req.user_id, run_id=req.run_id, top_k=req.top_k)
            # 3) 汇总证据并生成回答
            client = get_openai_client(_cfg)
            context_parts: List[str] = []
            for c in rag_chunks:
                context_parts.append(f"[RAG] {c.source}@{c.loc}: {c.text}")
            for m in mem_results or []:
                if isinstance(m, dict):
                    meta = m.get('metadata', {})
                    content = m.get('content', '')
                    context_parts.append(f"[MEM] {meta.get('run_id','')}: {content}")
                else:
                    context_parts.append(f"[MEM] {str(m)}")
            context = "\n".join(context_parts)
            messages = [
                {"role": "system", "content": "你是救援应急大脑，请基于给定证据回答，并在末尾列出引用。"},
                {"role": "user", "content": f"问题: {req.question}\n\n证据:\n{context}"},
            ]
            resp = client.chat.completions.create(model=_cfg.llm_model, messages=messages, temperature=0)
            answer = resp.choices[0].message.content if getattr(resp, 'choices', None) else ""
            return {
                "trace_id": trace_id,
                "answer": answer,
                "evidence": {
                    "rag": [{"text": c.text, "source": c.source, "loc": c.loc} for c in rag_chunks],
                    "memory": mem_results,
                },
            }
        except Exception:
            _assist_failures.inc()
            raise


@app.post("/intent/process")
async def intent_process(req: IntentProcessRequest):
    """统一意图处理入口（语音与文本复用）。"""
    manager = _require_conversation_manager()
    registry = _require_intent_registry()
    metadata = dict(req.metadata or {})
    if req.incident_id:
        metadata.setdefault("incident_id", req.incident_id)

    result: IntentProcessResult = await process_intent_core(
        user_id=req.user_id,
        thread_id=req.thread_id,
        message=req.message,
        metadata=metadata,
        manager=manager,
        registry=registry,
        orchestrator_graph=_require_intent_graph(),
        voice_control_graph=_require_voice_control_graph(),
        mem=_mem,
        build_history=_build_history,
        mem0_metrics=_mem0_metrics_factory(),
        channel=req.channel,
        context_service=_context_service,
    )
    return {
        "status": result.status,
        "intent": result.intent,
        "result": result.result,
        "history": result.history,
        "memory_hits": result.memory_hits,
        "audit_log": result.audit_log,
        "ui_actions": result.ui_actions,
    }


@app.post("/conversations/history")
async def conversation_history(req: ConversationHistoryRequest):
    """查询指定会话历史记录。"""
    manager = _require_conversation_manager()
    conversation = await manager.fetch_conversation(req.thread_id)
    if conversation is None:
        return {
            "history": [],
            "total": 0,
            "user_id": req.user_id,
            "thread_id": req.thread_id,
        }
    if conversation.user_id != req.user_id:
        raise HTTPException(status_code=403, detail="thread owner mismatch")
    records = await manager.get_history(req.thread_id, limit=req.limit)
    history_payload = _build_history(records)
    return {
        "history": history_payload,
        "total": len(history_payload),
        "user_id": req.user_id,
        "thread_id": req.thread_id,
    }

# WebSocket 语音对话路由
@app.websocket("/ws/voice/chat")
async def voice_chat_endpoint(websocket: WebSocket) -> None:
    await handle_voice_chat(websocket)
