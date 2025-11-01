from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import structlog
from psycopg_pool import AsyncConnectionPool

from emergency_agents.db.dao import RescueTaskRepository
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.device_directory import DeviceDirectory
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.scout_tactical_app import ScoutTacticalGraph, ScoutTacticalState
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from emergency_agents.risk.repository import RiskDataRepository
from emergency_agents.risk.service import RiskCacheManager
from emergency_agents.ui.actions import camera_fly_to, open_panel, serialize_actions, show_risk_warning, UIAction

logger = structlog.get_logger(__name__)


@dataclass
class ScoutTaskGenerationHandler(IntentHandler[ScoutTaskGenerationSlots]):
    """侦察任务生成处理器（懒加载模式）"""

    risk_repository: RiskDataRepository
    device_directory: DeviceDirectory
    amap_client: AmapClient
    orchestrator_client: OrchestratorClient
    postgres_dsn: str
    pool: AsyncConnectionPool

    def __post_init__(self) -> None:
        """延迟初始化ScoutTacticalGraph，避免启动时阻塞"""
        self._graph: Optional[ScoutTacticalGraph] = None
        self._graph_lock = asyncio.Lock()
        self._risk_cache: Optional[RiskCacheManager] = None

    async def _ensure_graph(self) -> ScoutTacticalGraph:
        """懒加载：首次调用时异步初始化ScoutTacticalGraph"""
        if self._graph is not None:
            return self._graph

        async with self._graph_lock:
            if self._graph is None:
                logger.info("scout_tactical_graph_lazy_init_start")

                # 使用pool创建task_repository
                task_repository = RescueTaskRepository.create(self.pool)

                # 调用异步build()方法初始化图
                self._graph = await ScoutTacticalGraph.build(
                    risk_repository=self.risk_repository,
                    device_directory=self.device_directory,
                    amap_client=self.amap_client,
                    orchestrator_client=self.orchestrator_client,
                    task_repository=task_repository,
                    postgres_dsn=self.postgres_dsn,
                )

                logger.info("scout_tactical_graph_lazy_init_complete")

        return self._graph

    async def aclose(self) -> None:
        """关闭图资源（如果已初始化）"""
        if self._graph is not None:
            # ScoutTacticalGraph可能有close()方法（如果有checkpointer）
            if hasattr(self._graph, "close"):
                await self._graph.close()
            self._graph = None

    def attach_risk_cache(self, risk_cache: Optional[RiskCacheManager]) -> None:
        """挂载共享风险缓存"""
        self._risk_cache = risk_cache

    async def handle(self, slots: ScoutTaskGenerationSlots, state: Dict[str, object]) -> Dict[str, object]:
        """处理侦察任务生成意图"""
        # 首行调用_ensure_graph()确保图已初始化
        graph = await self._ensure_graph()

        conversation_context: Dict[str, Any] = dict(state.get("conversation_context") or {})
        incident_id = conversation_context.get("incident_id") or ""
        tactical_state: ScoutTacticalState = {
            "incident_id": incident_id,
            "user_id": str(state.get("user_id")),
            "thread_id": str(state.get("thread_id")),
            "slots": slots,
        }

        result = await graph.invoke(
            tactical_state,
            config={"durability": "sync"},  # 长流程（侦察任务生成），同步保存checkpoint确保高可靠性
        )

        plan = result.get("scout_plan", {})
        response_text = result.get("response_text", "已生成侦察建议。")
        ui_actions = self._compose_ui_actions(plan, incident_id)

        logger.info(
            "scout_plan_ready",
            incident_id=incident_id,
            target_count=len(plan.get("targets", [])),
        )

        return {
            "response_text": response_text,
            "scout_plan": plan,
            "ui_actions": ui_actions,
            "conversation_context": conversation_context,
        }

    def _compose_ui_actions(self, plan: Mapping[str, Any], incident_id: str) -> List[Dict[str, Any]]:
        actions: List[UIAction] = []
        targets = plan.get("targets") or []
        metadata = {"incident_id": incident_id}
        if targets:
            first = targets[0]
            location = first.get("location") or {}
            lng = location.get("lng")
            lat = location.get("lat")
            if isinstance(lng, (int, float)) and isinstance(lat, (int, float)):
                actions.append(camera_fly_to(float(lng), float(lat), metadata=metadata))
        actions.append(open_panel(panel="scout_plan", params={"plan": plan}, metadata=metadata))
        for hint in plan.get("riskHints", []):
            actions.append(show_risk_warning(str(hint), metadata=metadata))
        return serialize_actions(actions)
