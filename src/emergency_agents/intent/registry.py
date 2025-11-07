from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Dict, Mapping

from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

from emergency_agents.db.dao import DeviceDAO, TaskDAO, EventDAO, PoiDAO, RescuerDAO
from emergency_agents.external.adapter_client import AdapterHubClient
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.device_directory import DeviceDirectory
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.kg_service import KGService
from emergency_agents.intent.handlers import (
    DeviceControlHandler,
    RobotDogControlHandler,
    RescueSimulationHandler,
    RescueTaskGenerationHandler,
    RescueTeamDispatchHandler,
    SimpleScoutDispatchHandler,
    TaskProgressQueryHandler,
    VideoAnalysisHandler,
    GeneralChatHandler,
)
from emergency_agents.intent.handlers.device_status import DeviceStatusQueryHandler
from emergency_agents.intent.handlers.system_data_query import SystemDataQueryHandler
from emergency_agents.intent.handlers.disaster_overview import DisasterOverviewHandler
from emergency_agents.risk.service import RiskCacheManager
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.services import RescueDraftService
from emergency_agents.video.stream_catalog import VideoStreamCatalog

# 默认视频流目录，确保在未提供配置时依然能完成巡逻机器狗的视频分析链路
DEFAULT_VIDEO_STREAMS: Dict[str, object] = {
    "scout-robotdog": {
        "display_name": "侦察巡逻机器狗",
        "stream_url": "rtsp://8.147.130.215:8554/live/02",
        "aliases": ("侦察巡逻机器狗", "巡逻机器狗", "侦察机器狗", "机器狗"),
        "device_type": "robotdog",
    }
}

@dataclass
class IntentHandlerRegistry:
    handlers: Dict[str, Any]

    @classmethod
    async def build(
        cls,
        pool: AsyncConnectionPool[DictRow],
        amap_client: AmapClient,
        device_directory: DeviceDirectory | None,
        video_stream_map: Mapping[str, object],
        kg_service: KGService,
        rag_pipeline: RagPipeline,
        llm_client: Any,
        llm_model: str,
        adapter_client: AdapterHubClient,
        default_robotdog_id: str | None,
        orchestrator_client: OrchestratorClient | None,
        rag_timeout: float,
        postgres_dsn: str,
        vllm_url: str,  # GLM-4V 视觉模型 API 地址
        vllm_api_key: str | None,
        vllm_model: str,
        simple_rescue_graph: Any | None = None,
    ) -> "IntentHandlerRegistry":
        if not postgres_dsn:
            raise RuntimeError("POSTGRES_DSN 未配置，无法初始化意图处理器注册表。")
        task_dao = TaskDAO.create(pool)
        device_dao = DeviceDAO.create(pool)
        event_dao = EventDAO.create(pool)
        poi_dao = PoiDAO.create(pool)
        rescuer_dao = RescuerDAO.create(pool)
        merged_streams: Dict[str, object] = dict(DEFAULT_VIDEO_STREAMS)
        merged_streams.update(dict(video_stream_map))
        stream_catalog = VideoStreamCatalog.from_raw_mapping(merged_streams)

        # LangGraph 救援方案流程暂时停用，保留构造逻辑以备后续恢复
        # rescue_generation = RescueTaskGenerationHandler(
        #     pool=pool,
        #     kg_service=kg_service,
        #     rag_pipeline=rag_pipeline,
        #     amap_client=amap_client,
        #     llm_client=llm_client,
        #     llm_model=llm_model,
        #     orchestrator_client=orchestrator_client,
        #     rag_timeout=rag_timeout,
        #     postgres_dsn=postgres_dsn,
        # )
        # rescue_simulation = RescueSimulationHandler(
        #     pool=pool,
        #     kg_service=kg_service,
        #     rag_pipeline=rag_pipeline,
        #     amap_client=amap_client,
        #     llm_client=llm_client,
        #     llm_model=llm_model,
        #     orchestrator_client=orchestrator_client,
        #     rag_timeout=rag_timeout,
        #     postgres_dsn=postgres_dsn,
        # )
        simple_scout_handler = SimpleScoutDispatchHandler(
            pool=pool,
            orchestrator_client=orchestrator_client,
            llm_client=llm_client,
            llm_model=llm_model,
        )

        robotdog_control = RobotDogControlHandler(adapter_client, default_robotdog_id)

        device_status_handler = DeviceStatusQueryHandler(device_dao)
        system_data_query_handler = SystemDataQueryHandler(
            device_dao=device_dao,
            task_dao=task_dao,
            event_dao=event_dao,
            poi_dao=poi_dao,
            rescuer_dao=rescuer_dao
        )
        disaster_overview_handler = DisasterOverviewHandler()
        general_chat_handler = GeneralChatHandler(llm_client, llm_model)

        # if simple_rescue_graph is not None:
        #     rescue_generation.attach_simple_graph(simple_rescue_graph)

        rescue_dispatch_handler = RescueTeamDispatchHandler(
            pool=pool,
            orchestrator_client=orchestrator_client,
        )

        handlers: Dict[str, Any] = {
            "task-progress-query": TaskProgressQueryHandler(task_dao),
            "device-control": DeviceControlHandler(device_dao, adapter_client, default_robotdog_id),
            "device-control-robotdog": robotdog_control,
            "device_control_robotdog": robotdog_control,
            "video-analysis": VideoAnalysisHandler(stream_catalog, vllm_url, vllm_api_key, vllm_model),
            "rescue-task-generate": rescue_dispatch_handler,
            "rescue_task_generate": rescue_dispatch_handler,
            "scout-task-simple": simple_scout_handler,
            "scout_task_simple": simple_scout_handler,
            # 兼容旧的完整侦察意图，暂时重定向到简化处理器
            "scout-task-generate": simple_scout_handler,
            "scout_task_generate": simple_scout_handler,
            "device-status-query": device_status_handler,
            "device_status_query": device_status_handler,
            "system-data-query": system_data_query_handler,  # 统一数据查询
            "disaster-analysis": disaster_overview_handler,
            "situation-overview": disaster_overview_handler,
            "general-chat": general_chat_handler,  # 通用对话
        }
        return cls(handlers=handlers)

    def get(self, intent_type: str) -> Any | None:
        return self.handlers.get(intent_type)

    def attach_risk_cache(self, risk_cache: RiskCacheManager | None) -> None:
        """为救援/模拟处理器挂载共享风险缓存。"""
        for handler in self.handlers.values():
            if isinstance(handler, RescueTaskGenerationHandler):
                handler.attach_risk_cache(risk_cache)

    def attach_rescue_draft_service(self, draft_service: RescueDraftService | None) -> None:
        """为救援处理器挂载草稿服务。"""
        for handler in self.handlers.values():
            if isinstance(handler, RescueTaskGenerationHandler):
                handler.attach_draft_service(draft_service)

    def attach_simple_rescue_graph(self, graph: Any | None) -> None:
        """为支持的救援处理器注入简化子图。"""
        for handler in self.handlers.values():
            attach_fn = getattr(handler, "attach_simple_graph", None)
            if callable(attach_fn):
                attach_fn(graph)

    async def close(self) -> None:
        seen: set[int] = set()
        for handler in self.handlers.values():
            if handler is None:
                continue
            identifier = id(handler)
            if identifier in seen:
                continue
            seen.add(identifier)
            close_fn = getattr(handler, "aclose", None)
            if callable(close_fn):
                result = close_fn()
                if inspect.isawaitable(result):
                    await result
