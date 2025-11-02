from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Dict

from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

from emergency_agents.db.dao import DeviceDAO, LocationDAO, TaskDAO, IncidentDAO
from emergency_agents.external.adapter_client import AdapterHubClient
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.device_directory import DeviceDirectory
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.kg_service import KGService
from emergency_agents.intent.handlers import (
    DeviceControlHandler,
    LocationPositioningHandler,
    RescueSimulationHandler,
    RescueTaskGenerationHandler,
    ScoutTaskGenerationHandler,
    TaskProgressQueryHandler,
    VideoAnalysisHandler,
    UIControlHandler,
)
from emergency_agents.risk.service import RiskCacheManager
from emergency_agents.risk.repository import RiskDataRepository
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.services import RescueDraftService


@dataclass
class IntentHandlerRegistry:
    handlers: Dict[str, Any]
    device_dao: DeviceDAO | None = None  # 暴露给main.py用于创建device_map_getter

    @classmethod
    async def build(
        cls,
        pool: AsyncConnectionPool[DictRow],
        amap_client: AmapClient,
        device_directory: DeviceDirectory | None,
        video_stream_map: Dict[str, str],
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
    ) -> "IntentHandlerRegistry":
        if not postgres_dsn:
            raise RuntimeError("POSTGRES_DSN 未配置，无法初始化意图处理器注册表。")
        location_dao = LocationDAO.create(pool)
        task_dao = TaskDAO.create(pool)
        device_dao = DeviceDAO.create(pool)

        rescue_generation = RescueTaskGenerationHandler(
            pool=pool,
            kg_service=kg_service,
            rag_pipeline=rag_pipeline,
            amap_client=amap_client,
            llm_client=llm_client,
            llm_model=llm_model,
            orchestrator_client=orchestrator_client,
            rag_timeout=rag_timeout,
            postgres_dsn=postgres_dsn,
        )
        rescue_simulation = RescueSimulationHandler(
            pool=pool,
            kg_service=kg_service,
            rag_pipeline=rag_pipeline,
            amap_client=amap_client,
            llm_client=llm_client,
            llm_model=llm_model,
            orchestrator_client=orchestrator_client,
            rag_timeout=rag_timeout,
            postgres_dsn=postgres_dsn,
        )
        risk_repository = RiskDataRepository(IncidentDAO.create(pool))
        scout_handler = ScoutTaskGenerationHandler(
            risk_repository=risk_repository,
            device_directory=device_directory,  # type: ignore  # 允许None，运行时暴露问题
            amap_client=amap_client,
            orchestrator_client=orchestrator_client,  # type: ignore  # 允许None，运行时暴露问题
            postgres_dsn=postgres_dsn,
            pool=pool,
        )

        handlers: Dict[str, Any] = {
            "task-progress-query": TaskProgressQueryHandler(task_dao),
            "location-positioning": LocationPositioningHandler(location_dao, amap_client),
            "device-control": DeviceControlHandler(device_dao, adapter_client, default_robotdog_id),
            "video-analysis": VideoAnalysisHandler(device_dao, video_stream_map, vllm_url),
            "rescue-task-generate": rescue_generation,
            "rescue_task_generate": rescue_generation,
            "rescue-simulation": rescue_simulation,
            "rescue_simulation": rescue_simulation,
            "scout-task-generate": scout_handler,
            "scout_task_generate": scout_handler,
            # UI 控制
            "ui_camera_flyto": UIControlHandler(),
            "ui_toggle_layer": UIControlHandler(),
        }
        return cls(handlers=handlers, device_dao=device_dao)

    def get(self, intent_type: str) -> Any | None:
        return self.handlers.get(intent_type)

    def attach_risk_cache(self, risk_cache: RiskCacheManager | None) -> None:
        """为救援/模拟处理器挂载共享风险缓存。"""
        for handler in self.handlers.values():
            if isinstance(handler, (RescueTaskGenerationHandler, ScoutTaskGenerationHandler)):
                handler.attach_risk_cache(risk_cache)

    def attach_rescue_draft_service(self, draft_service: RescueDraftService | None) -> None:
        """为救援处理器挂载草稿服务。"""
        for handler in self.handlers.values():
            if isinstance(handler, RescueTaskGenerationHandler):
                handler.attach_draft_service(draft_service)

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
