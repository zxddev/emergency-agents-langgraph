# Copyright 2025 msq
"""mem0集成测试（Backend Phase 1.5）

测试完整的多轮对话场景，验证mem0上下文检索和写入功能。
使用真实的mem0、Qdrant、Neo4j连接。

参考: openspec/changes/add-intent-context-chat-history/tasks.md lines 191-218
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def client():
    """FastAPI测试客户端"""
    from emergency_agents.api.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.integration
def test_multiturn_location_completion(client):
    """测试场景1: 多轮对话补全地点信息

    用户第一轮说："四川地震"
    用户第二轮说："坐标是103.85,31.68"
    验证第二轮能从mem0检索到第一轮的灾害类型

    参考: tasks.md lines 191-200
    """
    user_id = "test-user-location"
    thread_id = "test-thread-location"

    # 第一轮：仅汇报灾情，期望系统提示补充经纬度等战术信息
    response_1 = client.post("/intent/process", json={
        "user_id": user_id,
        "thread_id": thread_id,
        "message": "四川汶川县发生地震，出现建筑垮塌。"
    }, timeout=120.0)
    assert response_1.status_code == 200
    result_1 = response_1.json()
    assert result_1["status"] == "needs_input"
    missing_1 = set(result_1["result"]["missing_fields"])
    assert {"coordinates", "situation_summary"} <= missing_1

    # 第二轮：补充经纬度和现场细节
    response_2 = client.post("/intent/process", json={
        "user_id": user_id,
        "thread_id": thread_id,
        "message": "坐标103.85,31.68，南新村教学楼倒塌有10人被困，请立即安排救援队。"
    }, timeout=120.0)
    assert response_2.status_code == 200
    result_2 = response_2.json()
    assert result_2.get("intent") is not None

    intent = result_2["intent"]
    assert intent.get("intent_type") == "rescue-task-generate"

    slots = intent.get("slots", {})
    assert "coordinates" in slots and isinstance(slots["coordinates"], dict)
    assert "situation_summary" in slots and slots["situation_summary"]
    assert slots["coordinates"]["lng"] and slots["coordinates"]["lat"]


@pytest.mark.integration
def test_multiturn_severity_completion(client):
    """测试场景2: 多轮对话补全严重程度

    用户第一轮说："汶川有人被困"
    用户第二轮说："大概300人"
    验证第二轮能从mem0检索到第一轮的地点和灾害类型

    参考: tasks.md lines 201-210
    """
    user_id = "test-user-severity"
    thread_id = "test-thread-severity"

    # 第一轮：提供地点但缺少经纬度/详细情况，应提示补充
    response_1 = client.post("/intent/process", json={
        "user_id": user_id,
        "thread_id": thread_id,
        "message": "汶川有人被困"
    }, timeout=120.0)
    assert response_1.status_code == 200
    result_1 = response_1.json()
    assert result_1["status"] == "needs_input"

    # 第二轮：补充人数、经纬度及现场描述
    response_2 = client.post("/intent/process", json={
        "user_id": user_id,
        "thread_id": thread_id,
        "message": "具体人数大概300人，坐标103.90,31.70，厂房坍塌需要紧急破拆救援。"
    }, timeout=120.0)
    assert response_2.status_code == 200
    result_2 = response_2.json()

    assert result_2.get("intent") is not None
    assert result_2["intent"].get("intent_type") == "rescue-task-generate"


@pytest.mark.integration
def test_conversation_history_api(client):
    """测试场景3: 验证/conversations/history API

    发送多条消息后，验证能正确检索历史记录

    参考: tasks.md lines 219-237
    """
    user_id = "test-user-history"
    thread_id = "test-thread-history"

    # 发送3条消息
    messages = [
        "四川地震",
        "坐标103.85,31.68",
        "300人被困"
    ]

    for msg in messages:
        response = client.post("/intent/process", json={
            "user_id": user_id,
            "thread_id": thread_id,
            "message": msg
        }, timeout=120.0)
        assert response.status_code == 200

    # 查询历史记录
    history_response = client.post("/conversations/history", json={
        "user_id": user_id,
        "thread_id": thread_id,
        "limit": 10
    }, timeout=120.0)

    assert history_response.status_code == 200
    history_data = history_response.json()

    # 验证返回格式
    assert "history" in history_data
    assert "total" in history_data
    assert "user_id" in history_data
    assert "thread_id" in history_data

    # 验证消息数量（用户消息3条 + AI回复3条 = 6条）
    retrieved_messages = history_data["history"]
    assert len(retrieved_messages) >= 3  # 至少有用户的3条消息


@pytest.mark.integration
def test_prometheus_metrics_recorded(client):
    """测试场景4: 验证Prometheus指标记录

    发送请求后，验证/metrics端点包含mem0相关指标

    参考: tasks.md lines 109-118
    """
    user_id = "test-user-metrics"
    thread_id = "test-thread-metrics"

    # 触发mem0操作
    response = client.post("/intent/process", json={
        "user_id": user_id,
        "thread_id": thread_id,
        "message": "四川地震，坐标103.85,31.68"
    }, timeout=120.0)
    assert response.status_code == 200

    # 查询Prometheus指标
    metrics_response = client.get("/metrics", timeout=120.0)
    assert metrics_response.status_code == 200

    metrics_text = metrics_response.text

    # 验证mem0指标存在
    assert "mem0_search_duration_seconds" in metrics_text
    assert "mem0_search_success_total" in metrics_text
    assert "mem0_add_success_total" in metrics_text


@pytest.mark.integration
def test_tenant_isolation(client):
    """测试场景5: 验证多租户隔离

    不同用户的对话历史应该完全隔离

    参考: 多租户设计原则
    """
    # 用户A的对话
    client.post("/intent/process", json={
        "user_id": "user-a",
        "thread_id": "thread-a",
        "message": "北京地震"
    }, timeout=120.0)

    # 用户B的对话
    client.post("/intent/process", json={
        "user_id": "user-b",
        "thread_id": "thread-b",
        "message": "上海地震"
    }, timeout=120.0)

    # 查询用户A的历史（不应该看到用户B的消息）
    history_a = client.post("/conversations/history", json={
        "user_id": "user-a",
        "thread_id": "thread-a",
        "limit": 10
    }, timeout=120.0)

    assert history_a.status_code == 200
    messages_a = history_a.json()["history"]

    # 验证用户A的历史中不包含"上海"
    for msg in messages_a:
        assert "上海" not in msg.get("content", "")
