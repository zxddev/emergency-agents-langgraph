from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

import structlog

from emergency_agents.db.dao import (
    IncidentRepository,
    IncidentSnapshotRepository,
    RescueTaskRepository,
)
from emergency_agents.db.models import (
    IncidentEntityDetail,
    IncidentSnapshotCreateInput,
    IncidentSnapshotRecord,
    TaskCreateInput,
    TaskRecord,
)

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class RescueDraftRecord:
    """救援方案草稿的缓存结构。"""

    draft_id: str
    incident_id: str
    entity_id: Optional[str]
    plan: Mapping[str, Any]
    risk_summary: Mapping[str, Any]
    ui_actions: Sequence[Mapping[str, Any]]
    created_at: datetime
    created_by: Optional[str]


class RescueDraftService:
    """负责救援方案草稿的持久化与确认。"""

    def __init__(
        self,
        *,
        incident_repository: IncidentRepository,
        snapshot_repository: IncidentSnapshotRepository,
        task_repository: RescueTaskRepository,
    ) -> None:
        self._incident_repository = incident_repository
        self._snapshot_repository = snapshot_repository
        self._task_repository = task_repository

    async def save_draft(
        self,
        *,
        incident_id: str,
        entity: Optional[IncidentEntityDetail],
        plan: Mapping[str, Any],
        risk_summary: Mapping[str, Any],
        ui_actions: Sequence[Mapping[str, Any]],
        created_by: str,
    ) -> RescueDraftRecord:
        """保存救援方案草稿，返回草稿标识。"""

        payload = {
            "plan": plan,
            "risk_summary": dict(risk_summary),
            "ui_actions": list(ui_actions),
            "entity": self._serialize_entity(entity),
        }
        snapshot_input = IncidentSnapshotCreateInput(
            incident_id=incident_id,
            snapshot_type="rescue_plan_draft",
            payload=self._ensure_mapping(payload),
            generated_at=datetime.now(timezone.utc),
            created_by=created_by,
        )
        snapshot = await self._snapshot_repository.create_snapshot(snapshot_input)
        logger.info(
            "rescue_draft_saved",
            incident_id=incident_id,
            draft_id=snapshot.snapshot_id,
        )
        entity_id = payload["entity"].get("entity_id") if payload.get("entity") else None
        return RescueDraftRecord(
            draft_id=snapshot.snapshot_id,
            incident_id=snapshot.incident_id,
            entity_id=entity_id,
            plan=plan,
            risk_summary=risk_summary,
            ui_actions=ui_actions,
            created_at=snapshot.created_at,
            created_by=snapshot.created_by,
        )

    async def load_draft(self, draft_id: str) -> RescueDraftRecord:
        """读取草稿并返回结构化结果。"""

        snapshot = await self._snapshot_repository.get_snapshot(draft_id)
        if snapshot is None:
            raise ValueError(f"未找到草稿: {draft_id}")
        payload = self._ensure_mapping(snapshot.payload)
        plan = self._ensure_mapping(payload.get("plan"))
        risk_summary = self._ensure_mapping(payload.get("risk_summary"))
        ui_actions_raw = payload.get("ui_actions") or []
        ui_actions: list[Mapping[str, Any]] = []
        for item in ui_actions_raw:
            ui_actions.append(self._ensure_mapping(item))
        entity_id = None
        entity_payload = payload.get("entity")
        if isinstance(entity_payload, Mapping):
            entity_id = entity_payload.get("entity_id")
        return RescueDraftRecord(
            draft_id=snapshot.snapshot_id,
            incident_id=snapshot.incident_id,
            entity_id=entity_id if isinstance(entity_id, str) else None,
            plan=plan,
            risk_summary=risk_summary,
            ui_actions=ui_actions,
            created_at=snapshot.created_at,
            created_by=snapshot.created_by,
        )

    async def confirm_draft(
        self,
        draft_id: str,
        *,
        commander_id: str,
        priority: int = 70,
        description: Optional[str] = None,
        deadline: Optional[datetime] = None,
        task_code: Optional[str] = None,
    ) -> TaskRecord:
        """确认草稿并写入任务表。"""

        draft = await self.load_draft(draft_id)
        if description is None:
            response_text = draft.plan.get("response_text")
            if isinstance(response_text, str) and response_text.strip():
                description = response_text.strip()
            else:
                plan_section = self._ensure_mapping(draft.plan.get("plan"))
                overview = self._ensure_mapping(plan_section.get("overview"))
                analysis = self._ensure_mapping(overview.get("analysis"))
                if analysis:
                    matched = analysis.get("matched_count", 0)
                    try:
                        matched_int = int(matched)
                    except (TypeError, ValueError):
                        matched_int = 0
                    description = f"生成救援方案，匹配 {matched_int} 支力量"
                elif overview.get("situationSummary"):
                    description = f"救援任务：{overview['situationSummary']}"
                else:
                    description = "救援任务草稿确认"
        task_input = TaskCreateInput(
            task_type="rescue",
            status="pending",
            priority=priority,
            description=description,
            deadline=deadline,
            target_entity_id=draft.entity_id,
            event_id=draft.incident_id,
            created_by=commander_id,
            updated_by=commander_id,
            code=task_code or draft_id,
        )
        task_record = await self._task_repository.create_task(task_input)
        logger.info(
            "rescue_draft_confirmed",
            draft_id=draft_id,
            task_id=task_record.id,
            incident_id=draft.incident_id,
        )
        try:
            await self._snapshot_repository.delete_snapshot(draft_id)
        except Exception as exc:  # pragma: no cover - 忽略删除失败，但记录日志
            logger.warning("rescue_draft_delete_failed", draft_id=draft_id, error=str(exc))
        return task_record

    @staticmethod
    def _serialize_entity(entity: Optional[IncidentEntityDetail]) -> Mapping[str, Any] | None:
        if entity is None:
            return None
        link = entity.link
        record = entity.entity
        return {
            "incident_id": link.incident_id,
            "entity_id": record.entity_id,
            "layer_code": record.layer_code,
            "display_name": record.display_name,
            "properties": record.properties,
            "geometry": record.geometry_geojson,
        }

    @staticmethod
    def _ensure_mapping(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        raise TypeError(f"payload 必须是 Mapping，收到: {type(value)!r}")
