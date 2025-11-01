from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import structlog

from emergency_agents.graph.scout_tactical_app import ScoutTacticalGraph, ScoutTacticalState
from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import ScoutTaskGenerationSlots
from emergency_agents.risk.service import RiskCacheManager
from emergency_agents.ui.actions import camera_fly_to, open_panel, serialize_actions, show_risk_warning, UIAction

logger = structlog.get_logger(__name__)


@dataclass
class ScoutTaskGenerationHandler(IntentHandler[ScoutTaskGenerationSlots]):
    graph: ScoutTacticalGraph
    risk_cache: Optional[RiskCacheManager] = None

    def attach_risk_cache(self, risk_cache: Optional[RiskCacheManager]) -> None:
        self.risk_cache = risk_cache

    async def handle(self, slots: ScoutTaskGenerationSlots, state: Dict[str, object]) -> Dict[str, object]:
        conversation_context: Dict[str, Any] = dict(state.get("conversation_context") or {})
        incident_id = conversation_context.get("incident_id") or ""
        tactical_state: ScoutTacticalState = {
            "incident_id": incident_id,
            "user_id": str(state.get("user_id")),
            "thread_id": str(state.get("thread_id")),
            "slots": slots,
        }
        result = await self.graph.invoke(
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
