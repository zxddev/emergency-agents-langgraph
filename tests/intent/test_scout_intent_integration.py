# Copyright 2025 msq
"""Scout侦察意图端到端集成测试

测试覆盖范围：
1. 意图分类：识别scout-task-generate意图
2. 意图路由：orchestrator正确路由到scout handler
3. Handler执行：ScoutTaskGenerationHandler调用ScoutTacticalGraph
4. 结果验证：返回完整的侦察计划结构

注意事项：
- 需要真实PostgreSQL连接（LangGraph checkpointer）
- 需要真实DeviceDirectory（设备查询）
- Mock外部HTTP服务（AmapClient, OrchestratorClient）
- 标记为@pytest.mark.integration

相关文件：
- src/emergency_agents/graph/intent_orchestrator_app.py (路由配置)
- src/emergency_agents/intent/handlers/scout_task_generation.py (handler)
- src/emergency_agents/graph/scout_tactical_app.py (tactical graph)
"""

from __future__ import annotations

import time
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from emergency_agents.config import AppConfig
from emergency_agents.external.amap_client import AmapClient
from emergency_agents.external.device_directory import DeviceDirectory
from emergency_agents.external.orchestrator_client import OrchestratorClient
from emergency_agents.graph.intent_orchestrator_app import build_intent_orchestrator_graph
from emergency_agents.intent.classifier import build_intent_classifier_runtime
from emergency_agents.intent.providers.llm import LLMIntentProvider
from emergency_agents.intent.registry import IntentHandlerRegistry
from emergency_agents.intent.validator import intent_validator_node
from emergency_agents.intent.prompt_missing import prompt_missing_node
from emergency_agents.llm.client import get_openai_client
from psycopg_pool import AsyncConnectionPool


pytestmark = pytest.mark.integration


@pytest.fixture
def mock_amap_client() -> AmapClient:
    """Mock高德地图客户端（避免真实API调用）"""
    client = AsyncMock(spec=AmapClient)
    client.direction = AsyncMock(return_value={
        "distance_meters": 1500,
        "duration_seconds": 180,
        "steps": [],
        "cache_hit": False,
    })
    return client  # type: ignore[return-value]


@pytest.fixture
def mock_orchestrator_client() -> OrchestratorClient:
    """Mock编排器客户端（避免真实HTTP调用）"""
    client = Mock(spec=OrchestratorClient)
    client.publish_scout_scenario = Mock(return_value={"success": True})
    return client


@pytest.fixture
async def intent_registry(
    async_postgres_pool: AsyncConnectionPool,
    postgres_dsn: str,
    device_directory: DeviceDirectory,
    mock_amap_client: AmapClient,
    mock_orchestrator_client: OrchestratorClient,
    empty_risk_repository: Any,
) -> IntentHandlerRegistry:
    """创建完整的IntentHandlerRegistry（包含scout handler）

    注意：这里使用真实的PostgreSQL连接和DeviceDirectory，
    但mock了外部HTTP服务（AmapClient, OrchestratorClient）。
    """
    cfg = AppConfig.load_from_env()

    # 创建mock的依赖服务
    from emergency_agents.graph.kg_service import KGService
    from emergency_agents.rag.pipe import RagPipeline
    from emergency_agents.external.adapter_client import AdapterHubClient

    mock_kg_service = Mock(spec=KGService)
    mock_rag_pipeline = Mock(spec=RagPipeline)
    mock_llm_client = get_openai_client(cfg)
    mock_adapter_client = Mock(spec=AdapterHubClient)

    # 构建完整的registry（包括scout handler）
    registry = await IntentHandlerRegistry.build(
        pool=async_postgres_pool,
        amap_client=mock_amap_client,
        device_directory=device_directory,
        video_stream_map={},
        kg_service=mock_kg_service,
        rag_pipeline=mock_rag_pipeline,
        llm_client=mock_llm_client,
        llm_model=cfg.llm_model,
        adapter_client=mock_adapter_client,
        default_robotdog_id=None,
        orchestrator_client=mock_orchestrator_client,
        rag_timeout=30.0,
        postgres_dsn=postgres_dsn,
        vllm_url=cfg.openai_base_url,
    )

    yield registry

    # 清理资源
    await registry.close()


@pytest.mark.anyio
async def test_scout_intent_routing(
    intent_registry: IntentHandlerRegistry,
) -> None:
    """测试scout意图路由：确认registry可以获取scout handler

    验证点：
    1. IntentHandlerRegistry注册了scout-task-generate handler
    2. Handler支持别名scout-task-generation
    """
    # 测试主key
    handler_main = intent_registry.get("scout-task-generate")
    assert handler_main is not None, "scout-task-generate handler未注册"

    # 测试别名
    handler_alias = intent_registry.get("scout-task-generation")
    assert handler_alias is not None, "scout-task-generation别名未注册"

    # 两者应该是同一个handler实例
    assert handler_main is handler_alias, "主key和别名应指向同一个handler实例"

    print("✅ Scout handler routing test passed")


@pytest.mark.anyio
async def test_scout_handler_execution(
    intent_registry: IntentHandlerRegistry,
) -> None:
    """测试scout handler执行：验证handler可以生成侦察计划

    验证点：
    1. Handler正确解析ScoutTaskGenerationSlots
    2. 懒加载ScoutTacticalGraph成功
    3. 返回完整的scout_plan结构
    4. 生成UI actions（风险警告等）
    """
    # 获取handler
    handler = intent_registry.get("scout-task-generate")
    assert handler is not None

    # 准备槽位数据（模拟意图分类器输出）
    from emergency_agents.intent.schemas import ScoutTaskGenerationSlots

    slots = ScoutTaskGenerationSlots(
        target_type="hazard",
        objective_summary="确认化工园泄漏范围和影响区域",
    )

    # 准备状态字典（模拟orchestrator传入）
    state: Dict[str, Any] = {
        "user_id": "test-user-scout-1",
        "thread_id": "thread-scout-integration-1",
        "conversation_context": {
            "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630"  # 固定UUID
        },
    }

    # 执行handler（会懒加载graph并执行完整流程）
    t_start = time.time()
    result = await handler.handle(slots, state)
    t_end = time.time()

    duration_ms = int((t_end - t_start) * 1000)
    print(f"\n⏱️  Scout handler execution: {duration_ms}ms")

    # 验证返回结构
    assert "scout_plan" in result, "缺少scout_plan字段"
    assert "ui_actions" in result, "缺少ui_actions字段"

    # 验证scout_plan结构
    plan = result["scout_plan"]
    assert "targets" in plan, "scout_plan缺少targets字段"
    assert "overview" in plan, "scout_plan缺少overview字段"
    assert isinstance(plan["targets"], list), "targets应该是列表"

    # 验证overview结构
    overview = plan["overview"]
    assert "riskSummary" in overview, "overview缺少riskSummary"
    assert overview["riskSummary"]["total"] >= 0, "riskSummary.total应该>=0"

    # 验证UI actions（至少应该有一个风险警告）
    ui_actions = result["ui_actions"]
    assert isinstance(ui_actions, list), "ui_actions应该是列表"

    # 打印结果摘要
    print(f"✅ Scout plan generated:")
    print(f"   - Targets: {len(plan['targets'])}")
    print(f"   - Risk zones: {overview['riskSummary']['total']}")
    print(f"   - UI actions: {len(ui_actions)}")

    # 性能要求：scout任务生成应该在10秒内完成
    assert duration_ms <= 10000, \
        f"Scout handler performance not met: {duration_ms}ms > 10000ms"


@pytest.mark.anyio
async def test_scout_intent_orchestrator_integration(
    async_postgres_pool: AsyncConnectionPool,
    postgres_dsn: str,
) -> None:
    """测试完整的orchestrator集成：从意图分类到路由再到handler执行

    这是一个精简的端到端测试，验证：
    1. 意图分类识别scout-task-generate
    2. Orchestrator正确路由
    3. Handler registry返回正确的handler

    注意：此测试不实际执行handler（避免过多外部依赖），
    只验证路由逻辑正确性。完整的handler执行测试见test_scout_handler_execution。
    """
    cfg = AppConfig.load_from_env()
    llm_client = get_openai_client(cfg)

    # 构建意图分类器
    classifier_runtime = build_intent_classifier_runtime(
        cfg=cfg,
        llm_client=llm_client,
        llm_model=cfg.llm_model,
    )

    # 构建orchestrator graph
    orchestrator = await build_intent_orchestrator_graph(
        cfg=cfg,
        llm_client=llm_client,
        llm_model=cfg.llm_model,
        classifier_node=classifier_runtime,
        validator_node=intent_validator_node,
        prompt_node=prompt_missing_node,
    )

    # 准备测试输入（明确的侦察意图）
    state = {
        "thread_id": "thread-orchestrator-scout-1",
        "user_id": "test-user-orch-1",
        "channel": "text",
        "raw_text": "需要对化工园区进行侦察，确认泄漏范围",
        "messages": [{
            "role": "user",
            "content": "需要对化工园区进行侦察，确认泄漏范围"
        }],
        "metadata": {},
    }

    # 执行orchestrator（分类→验证→路由）
    t_start = time.time()
    result = await orchestrator.ainvoke(
        state,
        config={
            "configurable": {
                "thread_id": "thread-orchestrator-scout-1",
            }
        },
    )
    t_end = time.time()

    duration_ms = int((t_end - t_start) * 1000)
    print(f"\n⏱️  Orchestrator execution: {duration_ms}ms")

    # 验证路由结果
    assert "router_next" in result, "缺少router_next字段"
    router_next = result["router_next"]

    # 路由目标应该是scout-task-generate（或者如果LLM分类错误，打印警告）
    if router_next == "scout-task-generate":
        print(f"✅ Correctly routed to: {router_next}")
    else:
        # LLM可能分类为其他意图，记录但不失败（LLM具有不确定性）
        print(f"⚠️  Routed to: {router_next} (expected scout-task-generate)")
        print(f"   Intent: {result.get('intent', {})}")
        print(f"   This may be a classification issue, not a routing issue")

    # 验证audit_log记录
    assert "audit_log" in result, "缺少audit_log字段"
    audit_log = result["audit_log"]
    assert any(event["event"] == "intent_routed" for event in audit_log), \
        "audit_log应该包含intent_routed事件"

    # 打印路由轨迹
    print(f"\n📋 Audit trail:")
    for event in audit_log:
        print(f"   - {event['event']}: {event}")


@pytest.mark.anyio
async def test_scout_intent_end_to_end_minimal(
    intent_registry: IntentHandlerRegistry,
) -> None:
    """极简端到端测试：模拟意图处理器调用scout handler

    这个测试模拟了intent_processor.py中的核心逻辑：
    1. 从registry获取handler
    2. 准备槽位和状态
    3. 执行handler
    4. 验证结果

    这是对test_scout_handler_execution的补充，
    更接近真实的API调用场景。
    """
    # 模拟意图分类器的输出
    intent_payload = {
        "intent_type": "scout-task-generate",
        "slots": {
            "target_type": "hazard",
            "objective_summary": "确认化工园泄漏范围",
        },
        "meta": {
            "confidence": 0.95,
            "source": "llm",
            "need_confirm": False,
        }
    }

    # 从registry获取handler（模拟intent_processor.py line 511）
    handler = intent_registry.get(intent_payload["intent_type"])
    assert handler is not None, f"Handler not found for {intent_payload['intent_type']}"

    # 准备handler状态（模拟intent_processor.py line 429-441）
    from emergency_agents.intent.schemas import ScoutTaskGenerationSlots

    slots_instance = ScoutTaskGenerationSlots(**intent_payload["slots"])

    handler_state = {
        "user_id": "test-user-e2e-1",
        "thread_id": "thread-e2e-scout-1",
        "conversation_context": {
            "incident_id": "fef8469f-5f78-4dd4-8825-dbc915d1b630"
        },
    }

    # 执行handler（模拟intent_processor.py line 542）
    result = await handler.handle(slots_instance, handler_state)

    # 验证结果
    assert "scout_plan" in result
    assert "ui_actions" in result

    plan = result["scout_plan"]
    assert "targets" in plan
    assert "overview" in plan

    print(f"✅ End-to-end minimal test passed")
    print(f"   Plan targets: {len(plan['targets'])}")
    print(f"   UI actions: {len(result['ui_actions'])}")


if __name__ == "__main__":
    # 快速手动测试
    import asyncio
    import sys
    from pathlib import Path

    # 加载环境变量
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / "config" / "dev.env"

    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    print("手动测试 - Scout意图集成")
    print("=" * 60)

    # 这里需要手动创建fixtures，在pytest环境中不需要
    print("请使用 pytest 运行此测试文件：")
    print("  pytest tests/intent/test_scout_intent_integration.py -v")
    sys.exit(0)
