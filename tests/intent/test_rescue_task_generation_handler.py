from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import sys
import types

_psycopg_stub = types.ModuleType("psycopg")
_psycopg_rows_stub = types.ModuleType("psycopg.rows")
_psycopg_pool_stub = types.ModuleType("psycopg_pool")
_psycopg_rows_stub.AsyncDictRow = Dict[str, Any]  # type: ignore[attr-defined]
_psycopg_rows_stub.dict_row = object()
_psycopg_rows_stub.DictRow = Dict[str, Any]  # type: ignore[attr-defined]


def _class_row_stub(_cls: Any) -> None:
    return None


_psycopg_rows_stub.class_row = _class_row_stub  # type: ignore[attr-defined]


class _DummyAsyncConnectionPool:
    def __class_getitem__(cls, _item: Any) -> type:
        return cls  # type: ignore[return-value]


_psycopg_pool_stub.AsyncConnectionPool = _DummyAsyncConnectionPool  # type: ignore[attr-defined]
_psycopg_pool_stub.ConnectionPool = _DummyAsyncConnectionPool  # type: ignore[attr-defined]
_psycopg_stub.errors = types.SimpleNamespace(UndefinedColumn=RuntimeError, UndefinedTable=RuntimeError)  # type: ignore[attr-defined]
class _StubGeneric:
    def __class_getitem__(cls, _item: Any) -> type:
        return cls  # type: ignore[return-value]


_psycopg_stub.Capabilities = type("Capabilities", (_StubGeneric,), {})  # type: ignore[attr-defined]
_psycopg_stub.Connection = type("Connection", (_StubGeneric,), {})  # type: ignore[attr-defined]
_psycopg_stub.Cursor = type("Cursor", (_StubGeneric,), {})  # type: ignore[attr-defined]
_psycopg_stub.Pipeline = type("Pipeline", (_StubGeneric,), {})  # type: ignore[attr-defined]
_psycopg_stub.AsyncConnection = type("AsyncConnection", (_StubGeneric,), {})  # type: ignore[attr-defined]
_psycopg_stub.AsyncCursor = type("AsyncCursor", (_StubGeneric,), {})  # type: ignore[attr-defined]
_psycopg_stub.AsyncPipeline = type("AsyncPipeline", (_StubGeneric,), {})  # type: ignore[attr-defined]

sys.modules.setdefault("psycopg", _psycopg_stub)
sys.modules.setdefault("psycopg.rows", _psycopg_rows_stub)
sys.modules.setdefault("psycopg_pool", _psycopg_pool_stub)
_psycopg_types_stub = types.ModuleType("psycopg.types")
_psycopg_types_json_stub = types.ModuleType("psycopg.types.json")
_psycopg_types_json_stub.Jsonb = object  # type: ignore[attr-defined]
sys.modules.setdefault("psycopg.types", _psycopg_types_stub)
sys.modules.setdefault("psycopg.types.json", _psycopg_types_json_stub)

_neo4j_stub = types.ModuleType("neo4j")


class _DummyDriver:
    def session(self) -> Any:
        raise RuntimeError("neo4j session should not be used in tests")

    def close(self) -> None:
        return None


class _DummyGraphDatabase:
    @staticmethod
    def driver(*_args: Any, **_kwargs: Any) -> _DummyDriver:
        return _DummyDriver()


_neo4j_stub.GraphDatabase = _DummyGraphDatabase  # type: ignore[attr-defined]
sys.modules.setdefault("neo4j", _neo4j_stub)

_qdrant_stub = types.ModuleType("qdrant_client")


class _DummyQdrantClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None


_qdrant_stub.QdrantClient = _DummyQdrantClient  # type: ignore[attr-defined]
sys.modules.setdefault("qdrant_client", _qdrant_stub)

_llama_core_stub = types.ModuleType("llama_index.core")


class _DummyDocument:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None


class _DummyQueryEngine:
    def query(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(source_nodes=[])


class _DummyVectorStoreIndex:
    @classmethod
    def from_documents(cls, *_args: Any, **_kwargs: Any) -> "._DummyVectorStoreIndex":
        return cls()

    @classmethod
    def from_vector_store(cls, *_args: Any, **_kwargs: Any) -> "._DummyVectorStoreIndex":
        return cls()

    def as_query_engine(self, similarity_top_k: int) -> _DummyQueryEngine:
        return _DummyQueryEngine()


class _DummyStorageContext:
    @classmethod
    def from_defaults(cls, *_args: Any, **_kwargs: Any) -> "._DummyStorageContext":
        return cls()


class _DummySettings:
    llm: Any = None
    embed_model: Any = None


_llama_core_stub.Document = _DummyDocument  # type: ignore[attr-defined]
_llama_core_stub.VectorStoreIndex = _DummyVectorStoreIndex  # type: ignore[attr-defined]
_llama_core_stub.StorageContext = _DummyStorageContext  # type: ignore[attr-defined]
_llama_core_stub.Settings = _DummySettings  # type: ignore[attr-defined]
sys.modules.setdefault("llama_index.core", _llama_core_stub)

_llama_qdrant_stub = types.ModuleType("llama_index.vector_stores.qdrant")


class _DummyVectorStore:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None


_llama_qdrant_stub.QdrantVectorStore = _DummyVectorStore  # type: ignore[attr-defined]
sys.modules.setdefault("llama_index.vector_stores.qdrant", _llama_qdrant_stub)

_llama_llms_stub = types.ModuleType("llama_index.llms.openai_like")


class _DummyOpenAILike:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None


_llama_llms_stub.OpenAILike = _DummyOpenAILike  # type: ignore[attr-defined]
sys.modules.setdefault("llama_index.llms.openai_like", _llama_llms_stub)

_llama_embed_stub = types.ModuleType("llama_index.embeddings.openai")


class _DummyOpenAIEmbedding:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None


_llama_embed_stub.OpenAIEmbedding = _DummyOpenAIEmbedding  # type: ignore[attr-defined]
sys.modules.setdefault("llama_index.embeddings.openai", _llama_embed_stub)

_prometheus_stub = types.ModuleType("prometheus_client")


class _DummyMetric:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None

    def labels(self, *args: Any, **kwargs: Any) -> "._DummyMetric":
        return self

    def inc(self) -> None:
        return None

    def time(self) -> "._DummyMetric":
        return self

    def __enter__(self) -> "_DummyMetric":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


_prometheus_stub.Counter = _DummyMetric  # type: ignore[attr-defined]
_prometheus_stub.Histogram = _DummyMetric  # type: ignore[attr-defined]
sys.modules.setdefault("prometheus_client", _prometheus_stub)

import pytest

from emergency_agents.constants import RESCUE_DEMO_INCIDENT_ID
from emergency_agents.db.models import (
    EntityRecord,
    IncidentEntityCreateInput,
    IncidentEntityDetail,
    IncidentEntityLink,
    RescuerRecord,
    RiskZoneRecord,
    TaskRecord,
    TaskRoutePlanRecord,
)
from emergency_agents.external.amap_client import Coordinate, RoutePlan
from emergency_agents.graph.kg_service import KGService
from emergency_agents.intent.handlers.rescue_task_generation import (
    RescueSimulationHandler,
    RescueTaskGenerationHandler,
)
from emergency_agents.intent.schemas import RescueTaskGenerationSlots
from emergency_agents.rag.equipment_extractor import ExtractedEquipment
from emergency_agents.rag.pipe import RagChunk, RagPipeline
from emergency_agents.risk.service import RiskCacheState
from langgraph.checkpoint.memory import MemorySaver


def _rescue_record_from_row(row: Dict[str, Any]) -> RescuerRecord:
    return RescuerRecord(
        rescuer_id=str(row.get("resource_id")),
        name=str(row.get("name", row.get("resource_id", "unknown"))),
        rescuer_type=str(row.get("rescuer_type", "unknown")),
        status=row.get("status"),
        availability=bool(row.get("availability", True)),
        lng=float(row["lng"]) if row.get("lng") is not None else None,
        lat=float(row["lat"]) if row.get("lat") is not None else None,
        skills=list(row.get("skills") or []),
        equipment=dict(row.get("equipment") or {}),
    )


class FakeCursor:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    async def execute(self, *_args, **_kwargs) -> None:
        return None

    async def fetchall(self) -> List[RescuerRecord]:
        return [_rescue_record_from_row(row) for row in self._rows]


class FakeConnection:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def cursor(self, *, row_factory=None) -> FakeCursor:  # type: ignore[override]
        return FakeCursor(self._rows)

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class FakePool:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def connection(self) -> "FakePool":  # type: ignore[override]
        return self

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(self._rows)

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class IncidentRepoStub:
    def __init__(self, entity_id: str = "entity-1") -> None:
        self.called = False
        self.payload: IncidentEntityCreateInput | None = None
        self.entity_id = entity_id

    async def create_entity_with_link(self, payload: IncidentEntityCreateInput) -> IncidentEntityDetail:
        self.called = True
        self.payload = payload
        now = datetime.now(timezone.utc)
        entity = EntityRecord(
            entity_id=self.entity_id,
            entity_type=payload.entity_type,
            geometry_geojson={"type": "Point", "coordinates": [120.0, 30.0]},
            properties=dict(payload.properties),
            layer_code=payload.layer_code,
            display_name="示例救援目标",
            created_by=payload.created_by,
            updated_by=payload.created_by,
            created_at=now,
            updated_at=now,
        )
        link = IncidentEntityLink(
            incident_id=payload.incident_id,
            entity_id=entity.entity_id,
            relation_type=payload.relation_type,
            notes=payload.relation_description,
            display_priority=payload.display_priority,
            linked_at=now,
        )
        return IncidentEntityDetail(link=link, entity=entity)


class IncidentDAOStub:
    def __init__(self, zones: Optional[List[RiskZoneRecord]] = None) -> None:
        self._zones = zones or []
        self.calls = 0

    async def list_active_risk_zones(self, reference_time: Any | None = None) -> List[RiskZoneRecord]:
        self.calls += 1
        return list(self._zones)


@dataclass
class FakeKGService:
    requirements: List[Dict[str, Any]]

    def get_equipment_requirements(self, disasters: List[str]) -> List[Dict[str, Any]]:
        assert disasters, "灾害类型不可为空"
        return self.requirements


@dataclass
class FakeRagPipeline:
    chunks: List[RagChunk]

    def query(self, question: str, domain: str, top_k: int = 5) -> List[RagChunk]:
        assert domain == "案例"
        assert top_k == 5
        assert question
        return self.chunks


class FakeAmapClient:
    async def geocode(self, place: str) -> Dict[str, Any] | None:
        return {"name": place, "location": {"lng": 120.1, "lat": 30.2}, "level": "poi"}

    async def direction(self, *, origin: Coordinate, destination: Coordinate, mode: str, cache_key: str | None = None) -> RoutePlan:
        assert mode == "driving"
        assert origin["lng"] and destination["lng"]
        return RoutePlan(
            distance_meters=12000,
            duration_seconds=900,
            steps=[],
            cache_hit=False,
        )


@pytest.fixture(name="fake_rows")
def fake_rows_fixture() -> List[Dict[str, Any]]:
    return [
        {
            "resource_id": "r1",
            "name": "救援队一号",
            "rescuer_type": "rescue_team",
            "lng": 120.05,
            "lat": 30.25,
            "skills": ["rescue", "medical"],
            "equipment": {"life_detector": 2, "thermal_camera": 1},
            "availability": True,
            "status": "available",
        }
    ]


@pytest.fixture(name="risk_zone_records")
def risk_zone_records_fixture() -> List[RiskZoneRecord]:
    now = datetime.now(timezone.utc)
    polygon = [
        [120.0, 30.0],
        [120.01, 30.0],
        [120.01, 30.01],
        [120.0, 30.01],
        [120.0, 30.0],
    ]
    return [
        RiskZoneRecord(
            zone_id="risk-1",
            zone_name="危险区域-1",
            hazard_type="landslide",
            severity=4,
            description="滑坡风险区域",
            geometry_geojson={"type": "Polygon", "coordinates": [polygon]},
            properties={"alertLevel": "red"},
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=2),
            created_at=now - timedelta(hours=1),
            updated_at=now,
        )
    ]


@pytest.fixture(name="fake_kg")
def fake_kg_fixture() -> KGService:
    return FakeKGService(
        requirements=[
            {"equipment_name": "life_detector", "display_name": "生命探测仪"},
            {"equipment_name": "thermal_camera", "display_name": "热成像仪"},
            {"equipment_name": "medkit", "display_name": "医疗包"},
        ]
    )  # type: ignore[return-value]


@pytest.fixture(name="fake_rag")
def fake_rag_fixture() -> RagPipeline:
    return FakeRagPipeline(
        chunks=[
            RagChunk(text="案例1", source="case1", loc="p1"),
            RagChunk(text="案例2", source="case2", loc="p2"),
        ]
    )  # type: ignore[return-value]


def test_rescue_task_generation_happy_path(monkeypatch: pytest.MonkeyPatch, fake_rows: List[Dict[str, Any]], fake_kg: KGService, fake_rag: RagPipeline, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    pool = FakePool(fake_rows)
    amap_client = FakeAmapClient()

    def fake_extract_equipment(_cases: List[RagChunk], _llm_client: Any, _llm_model: str) -> List[ExtractedEquipment]:
        return [
            ExtractedEquipment(
                name="生命探测仪",
                quantity=10,
                context="调用生命探测仪执行搜救。",
                confidence=0.95,
                source_chunk_id="case_1",
            )
        ]

    fake_recommendation = {"equipment_name": "life_detector", "display_name": "生命探测仪", "recommended_quantity": 10}

    def fake_build_recommendations(*_args: Any, **_kwargs: Any) -> List[Any]:
        return [SimpleNamespace(to_dict=lambda: fake_recommendation)]

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.extract_equipment_from_cases",
        fake_extract_equipment,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.build_equipment_recommendations",
        fake_build_recommendations,
    )

    async def fake_list_rescuers(_self, *, limit: int = 25) -> List[RescuerRecord]:
        return [_rescue_record_from_row(fake_rows[0])]

    async def fake_create_task(_self, payload: Any) -> TaskRecord:
        now = datetime.now(timezone.utc)
        return TaskRecord(
            id="task-db-1",
            task_type=payload.task_type,
            status=payload.status,
            priority=payload.priority,
            description=payload.description,
            deadline=payload.deadline,
            progress=0,
            event_id=payload.event_id,
            code=payload.code,
            created_at=now,
            updated_at=now,
        )

    async def fake_create_route(_self, payload: Any) -> TaskRoutePlanRecord:
        now = datetime.now(timezone.utc)
        return TaskRoutePlanRecord(
            id="route-db-1",
            task_id=payload.task_id,
            status=payload.status,
            strategy=payload.strategy,
            origin_geojson=payload.origin_geojson,
            destination_geojson=payload.destination_geojson,
            polyline_geojson=payload.polyline_geojson,
            distance_meters=payload.distance_meters,
            duration_seconds=payload.duration_seconds,
            estimated_arrival_time=payload.estimated_arrival_time,
            avoid_polygons=payload.avoid_polygons,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueDAO.list_available_rescuers",
        fake_list_rescuers,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_task",
        fake_create_task,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_route_plan",
        fake_create_route,
    )

    incident_repo_stub = IncidentRepoStub()
    incident_dao_stub = IncidentDAOStub()

    class _OrchestratorStub:
        def __init__(self) -> None:
            self.calls: List[Any] = []

        def publish_rescue_scenario(self, payload: Any) -> Dict[str, Any]:
            self.calls.append(payload)
            task_attr = getattr(payload, "task_id", None)
            return {"status": "ok", "task_id": task_attr}

    orchestrator_stub = _OrchestratorStub()

    handler = RescueTaskGenerationHandler(
        pool=pool,  # type: ignore[arg-type]
        kg_service=fake_kg,
        rag_pipeline=fake_rag,
        amap_client=amap_client,  # type: ignore[arg-type]
        llm_client=object(),
        llm_model="test-model",
        orchestrator_client=orchestrator_stub,
        rag_timeout=5.0,
        postgres_dsn=TEST_POSTGRES_DSN,
    )
    handler._incident_repository = incident_repo_stub  # type: ignore[attr-defined]
    handler._incident_dao = incident_dao_stub  # type: ignore[attr-defined]

    slots = RescueTaskGenerationSlots(
        mission_type="rescue",
        location_name="测试地点",
        disaster_type="earthquake",
    )

    async def _run() -> None:
        result = await handler.handle(
            slots,
            {
                "user_id": "u1",
                "thread_id": "thread-1",
                "conversation_context": {"incident_id": "incident-1", "incident_title": "测试事件"},
                "metadata": {"source": "manual"},
            },
        )
        rescue_task = result["rescue_task"]
        assert rescue_task is not None
        assert rescue_task["recommendation"]["resource_id"] == "r1"
        assert incident_repo_stub.called
        assert rescue_task["entity"]["entity_id"] == "entity-1"
        assert result["ui_actions"]
        assert any(action["action"] == "open_panel" for action in result["ui_actions"])
        assert rescue_task["plan"]["taskId"] == rescue_task["task_id"]
        summary = rescue_task["analysis_summary"]
        assert summary["matched_count"] == 1
        assert summary["kg_count"] == 3
        assert summary["rag_count"] == 2

    asyncio.run(_run())
    assert orchestrator_stub.calls, "未触发场景广播调用"


def test_rescue_task_generation_requires_incident(
    monkeypatch: pytest.MonkeyPatch,
    fake_rows: List[Dict[str, Any]],
    fake_kg: KGService,
    fake_rag: RagPipeline,
    risk_zone_records: List[RiskZoneRecord],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    pool = FakePool(fake_rows)

    async def fake_list_rescuers(_self, *, limit: int = 25) -> List[RescuerRecord]:
        return [_rescue_record_from_row(fake_rows[0])]

    async def fake_create_task(_self, payload: Any) -> TaskRecord:
        now = datetime.now(timezone.utc)
        return TaskRecord(
            id="task-default-1",
            task_type=payload.task_type,
            status=payload.status,
            priority=payload.priority,
            description=payload.description,
            deadline=payload.deadline,
            progress=0,
            event_id=payload.event_id,
            code=payload.code,
            created_at=now,
            updated_at=now,
        )

    async def fake_create_route(_self, payload: Any) -> TaskRoutePlanRecord:
        now = datetime.now(timezone.utc)
        return TaskRoutePlanRecord(
            id="route-default-1",
            task_id=payload.task_id,
            status=payload.status,
            strategy=payload.strategy,
            origin_geojson=payload.origin_geojson,
            destination_geojson=payload.destination_geojson,
            polyline_geojson=payload.polyline_geojson,
            distance_meters=payload.distance_meters,
            duration_seconds=payload.duration_seconds,
            estimated_arrival_time=payload.estimated_arrival_time,
            avoid_polygons=payload.avoid_polygons,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueDAO.list_available_rescuers",
        fake_list_rescuers,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_task",
        fake_create_task,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_route_plan",
        fake_create_route,
    )

    class _StubLLMCreateResponse:
        """最小响应体，确保装备提取流程拿到空列表。"""

        def __init__(self) -> None:
            self.choices: List[Any] = [
                SimpleNamespace(message=SimpleNamespace(content="[]"))
            ]

    class _StubLLMCompletions:
        """模拟 chat.completions 接口。"""

        def create(
            self,
            *,
            model: str,
            messages: List[Dict[str, Any]],
            temperature: float,
            response_format: Dict[str, Any],
        ) -> Any:
            return _StubLLMCreateResponse()

    class _StubLLMChat:
        """提供 completions 子对象以匹配真实调用结构。"""

        def __init__(self) -> None:
            self.completions: _StubLLMCompletions = _StubLLMCompletions()

    class _StubLLMClient:
        """仿真 llm_client，满足 chat.completions.create 访问路径。"""

        def __init__(self) -> None:
            self.chat: _StubLLMChat = _StubLLMChat()

    handler = RescueTaskGenerationHandler(
        pool=pool,  # type: ignore[arg-type]
        kg_service=fake_kg,
        rag_pipeline=fake_rag,
        amap_client=FakeAmapClient(),  # type: ignore[arg-type]
        llm_client=_StubLLMClient(),
        llm_model="test-model",
        orchestrator_client=None,
        rag_timeout=5.0,
        postgres_dsn=TEST_POSTGRES_DSN,
    )
    repo_stub = IncidentRepoStub()
    handler._incident_repository = repo_stub  # type: ignore[attr-defined]
    dao_stub = IncidentDAOStub(risk_zone_records)
    handler._incident_dao = dao_stub  # type: ignore[attr-defined]
    slots = RescueTaskGenerationSlots(
        mission_type="rescue",
        location_name="默认演示地点",
        disaster_type="earthquake",
    )

    async def _run() -> Dict[str, Any]:
        return await handler.handle(
            slots,
            {
                "user_id": "u2",
                "thread_id": "thread-missing",
                "metadata": {"source": "voice"},
            },
        )

    result = asyncio.run(_run())
    rescue_task = result["rescue_task"]
    assert rescue_task is not None
    context = result["conversation_context"]
    assert context.get("incident_id") == RESCUE_DEMO_INCIDENT_ID
    assert repo_stub.called
    assert result["ui_actions"], "应返回前端动作"
    plan = rescue_task["plan"]
    overview = plan["overview"]
    assert overview["riskOutline"]
    risks = plan["risks"]
    assert len(risks) == len(risk_zone_records)
    assert risks[0]["zoneId"] == risk_zone_records[0].zone_id
    assert plan["routeWarnings"], "应生成路线风险提示"
    warning_toasts = [
        action
        for action in result["ui_actions"]
        if action["action"] == "show_toast" and action["payload"]["level"] == "warning"
    ]
    assert warning_toasts, "需要给指挥员风险提示"
    assert "附近存在1处危险区域" in warning_toasts[0]["payload"]["message"]
    risk_warning_actions = [action for action in result["ui_actions"] if action["action"] == "show_risk_warning"]
    assert risk_warning_actions, "需要推送 show_risk_warning UI 动作"
    assert dao_stub.calls == 1


def test_rescue_task_uses_risk_cache_summary(
    monkeypatch: pytest.MonkeyPatch,
    fake_rows: List[Dict[str, Any]],
    fake_kg: KGService,
    fake_rag: RagPipeline,
    risk_zone_records: List[RiskZoneRecord],
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.INFO)
    pool = FakePool(fake_rows)

    async def fake_list_rescuers(_self, *, limit: int = 25) -> List[RescuerRecord]:
        return [_rescue_record_from_row(fake_rows[0])]

    async def fake_create_task(_self, payload: Any) -> TaskRecord:
        now = datetime.now(timezone.utc)
        return TaskRecord(
            id="task-cache-1",
            task_type=payload.task_type,
            status=payload.status,
            priority=payload.priority,
            description=payload.description,
            deadline=payload.deadline,
            progress=0,
            event_id=payload.event_id,
            code=payload.code,
            created_at=now,
            updated_at=now,
        )

    async def fake_create_route(_self, payload: Any) -> TaskRoutePlanRecord:
        now = datetime.now(timezone.utc)
        return TaskRoutePlanRecord(
            id="route-cache-1",
            task_id=payload.task_id,
            status=payload.status,
            strategy=payload.strategy,
            origin_geojson=payload.origin_geojson,
            destination_geojson=payload.destination_geojson,
            polyline_geojson=payload.polyline_geojson,
            distance_meters=payload.distance_meters,
            duration_seconds=payload.duration_seconds,
            estimated_arrival_time=payload.estimated_arrival_time,
            avoid_polygons=payload.avoid_polygons,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueDAO.list_available_rescuers",
        fake_list_rescuers,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_task",
        fake_create_task,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_route_plan",
        fake_create_route,
    )

    class _StubLLMCreateResponse:
        def __init__(self) -> None:
            self.choices = [SimpleNamespace(message=SimpleNamespace(content="[]"))]

    class _StubLLMCompletions:
        def create(
            self,
            *,
            model: str,
            messages: List[Dict[str, Any]],
            temperature: float,
            response_format: Dict[str, Any],
        ) -> Any:
            return _StubLLMCreateResponse()

    class _StubLLMChat:
        def __init__(self) -> None:
            self.completions = _StubLLMCompletions()

    class _StubLLMClient:
        def __init__(self) -> None:
            self.chat = _StubLLMChat()

    class RiskCacheStub:
        def __init__(self, zones: List[RiskZoneRecord]) -> None:
            self._zones = zones
            self.calls = 0
            self._state = RiskCacheState(list(zones), datetime.now(timezone.utc))

        async def get_active_zones(self, *, force_refresh: bool = False) -> List[RiskZoneRecord]:
            self.calls += 1
            return list(self._zones)

        def snapshot(self) -> RiskCacheState:
            return RiskCacheState(list(self._zones), self._state.refreshed_at)

    handler = RescueTaskGenerationHandler(
        pool=pool,  # type: ignore[arg-type]
        kg_service=fake_kg,
        rag_pipeline=fake_rag,
        amap_client=FakeAmapClient(),  # type: ignore[arg-type]
        llm_client=_StubLLMClient(),
        llm_model="test-model",
        orchestrator_client=None,
        rag_timeout=5.0,
        postgres_dsn=TEST_POSTGRES_DSN,
    )
    repo_stub = IncidentRepoStub()
    handler._incident_repository = repo_stub  # type: ignore[attr-defined]
    dao_stub = IncidentDAOStub([])
    handler._incident_dao = dao_stub  # type: ignore[attr-defined]
    cache_stub = RiskCacheStub(risk_zone_records)
    handler.attach_risk_cache(cache_stub)

    slots = RescueTaskGenerationSlots(
        mission_type="rescue",
        location_name="缓存风险区域",
        disaster_type="earthquake",
    )

    async def _run() -> Dict[str, Any]:
        return await handler.handle(
            slots,
            {
                "user_id": "u-cache",
                "thread_id": "thread-cache",
                "metadata": {"source": "voice"},
            },
        )

    result = asyncio.run(_run())
    rescue_task = result["rescue_task"]
    assert rescue_task is not None
    plan = rescue_task["plan"]
    overview = plan["overview"]
    assert overview["riskOutline"]
    assert len(plan["risks"]) == len(risk_zone_records)
    assert rescue_task["risk_summary"]["source"] == "cache"
    assert rescue_task["risk_summary"]["count"] == len(risk_zone_records)
    assert plan["routeWarnings"], "缓存模式同样需要生成路线风险提示"
    assert cache_stub.calls == 1
    assert dao_stub.calls == 0
    stdout = capsys.readouterr().out
    assert "risk_assessment_summary" in stdout
    assert "source=cache" in stdout


def test_rescue_simulation_text_only(monkeypatch: pytest.MonkeyPatch, fake_rows: List[Dict[str, Any]], fake_kg: KGService, fake_rag: RagPipeline, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    pool = FakePool(fake_rows)
    amap_client = FakeAmapClient()

    def fake_extract_equipment(_cases: List[RagChunk], _llm_client: Any, _llm_model: str) -> List[ExtractedEquipment]:
        return [
            ExtractedEquipment(
                name="生命探测仪",
                quantity=8,
                context="示例案例。",
                confidence=0.9,
                source_chunk_id="case_1",
            )
        ]

    def fake_build_recommendations(*_args: Any, **_kwargs: Any) -> List[Any]:
        return [SimpleNamespace(to_dict=lambda: {"equipment_name": "life_detector", "display_name": "生命探测仪"})]

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.extract_equipment_from_cases",
        fake_extract_equipment,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.build_equipment_recommendations",
        fake_build_recommendations,
    )

    async def sim_list_rescuers(_self, *, limit: int = 25) -> List[RescuerRecord]:
        return [_rescue_record_from_row(fake_rows[0])]

    async def sim_create_task(_self, payload: Any) -> TaskRecord:
        now = datetime.now(timezone.utc)
        return TaskRecord(
            id="task-sim-1",
            task_type=payload.task_type,
            status=payload.status,
            priority=payload.priority,
            description=payload.description,
            deadline=payload.deadline,
            progress=0,
            event_id=payload.event_id,
            code=payload.code,
            created_at=now,
            updated_at=now,
        )

    async def sim_create_route(_self, payload: Any) -> TaskRoutePlanRecord:
        now = datetime.now(timezone.utc)
        return TaskRoutePlanRecord(
            id="route-sim-1",
            task_id=payload.task_id,
            status=payload.status,
            strategy=payload.strategy,
            origin_geojson=payload.origin_geojson,
            destination_geojson=payload.destination_geojson,
            polyline_geojson=payload.polyline_geojson,
            distance_meters=payload.distance_meters,
            duration_seconds=payload.duration_seconds,
            estimated_arrival_time=payload.estimated_arrival_time,
            avoid_polygons=payload.avoid_polygons,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueDAO.list_available_rescuers",
        sim_list_rescuers,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_task",
        sim_create_task,
    )
    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.RescueTaskRepository.create_route_plan",
        sim_create_route,
    )

    handler = RescueSimulationHandler(
        pool=pool,  # type: ignore[arg-type]
        kg_service=fake_kg,
        rag_pipeline=fake_rag,
        amap_client=amap_client,  # type: ignore[arg-type]
        llm_client=object(),
        llm_model="test-model",
        orchestrator_client=None,
        rag_timeout=5.0,
        postgres_dsn=TEST_POSTGRES_DSN,
    )
    sim_repo_stub = IncidentRepoStub()
    handler._incident_repository = sim_repo_stub  # type: ignore[attr-defined]
    handler._incident_dao = IncidentDAOStub()  # type: ignore[attr-defined]

    slots = RescueTaskGenerationSlots(
        mission_type="rescue",
        location_name="测试地点",
        disaster_type="earthquake",
    )

    async def _run() -> Dict[str, Any]:
        return await handler.handle(
            slots,
            {
                "user_id": "u1",
                "thread_id": "thread-2",
                "conversation_context": {"incident_id": "incident-2", "incident_title": "测试事件"},
                "metadata": {"source": "simulation"},
            },
        )

    result = asyncio.run(_run())
    assert "模拟结果" in result["response_text"]
    simulation = result["simulation"]
    assert simulation is not None
    assert simulation["recommendation"]["resource_id"] == "r1"
    assert not sim_repo_stub.called, "模拟模式不应写入实体"
    assert simulation["analysis_summary"]["matched_count"] == 1
TEST_POSTGRES_DSN = "postgresql://tests"


@pytest.fixture(autouse=True)
def _patch_checkpointer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_checkpointer(**_kwargs: Any) -> tuple[MemorySaver, Any]:
        saver = MemorySaver()

        async def _close() -> None:
            return None

        return saver, _close

    monkeypatch.setattr(
        "emergency_agents.graph.rescue_tactical_app.create_async_postgres_checkpointer",
        _fake_checkpointer,
    )
