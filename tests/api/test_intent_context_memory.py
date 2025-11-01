# Copyright 2025 msq
"""mem0集成单元测试（Backend Phase 1.4）

测试mem0在意图处理中的上下文检索和写入功能。
使用Mock避免真实mem0连接，快速验证集成逻辑。

参考: openspec/changes/add-intent-context-chat-history/tasks.md lines 121-189
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def client():
    """FastAPI测试客户端"""
    from emergency_agents.api.main import app
    return TestClient(app)


@pytest.mark.unit
def test_mem0_search_called_on_intent_process(client, mocker):
    """测试用例1: mem0成功检索上下文

    验证点:
    1. mem0.search被正确调用
    2. 传递正确的参数(query, user_id, run_id, top_k)

    参考: tasks.md lines 124-151
    """
    mock_mem = mocker.patch('emergency_agents.api.main._mem')
    mock_mem.search.return_value = [
        {"memory": "意图: rescue-task-generate, 槽位: {\"location\": \"汶川\"}"}
    ]

    mock_manager_func = mocker.patch('emergency_agents.api.main._require_conversation_manager')
    mock_manager = MagicMock()
    mock_manager.save_message = mocker.AsyncMock(return_value=MagicMock(conversation_id="test-conv-id"))
    mock_manager_func.return_value = mock_manager

    mock_build_history = mocker.patch('emergency_agents.api.main._build_history')
    mock_build_history.return_value = []

    mock_classifier = mocker.patch('emergency_agents.api.main.intent_classifier_node')
    mock_classifier.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川"}},
        "messages": []
    }

    mock_validator = mocker.patch('emergency_agents.api.main.validate_and_prompt_node')
    mock_validator.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川"}},
        "validation_status": "valid"
    }

    mock_registry_func = mocker.patch('emergency_agents.api.main._require_intent_registry')
    mock_registry = MagicMock()
    mock_handler = MagicMock()
    mock_handler.handle = mocker.AsyncMock(return_value={"response_text": "已处理"})
    mock_registry.get.return_value = mock_handler
    mock_registry_func.return_value = mock_registry

    response = client.post("/intent/process", json={
        "user_id": "test-user",
        "thread_id": "test-thread",
        "message": "坐标是103.85,31.68"
    })

    assert response.status_code == 200

    mock_mem.search.assert_called_once_with(
        query="坐标是103.85,31.68",
        user_id="test-user",
        run_id="test-thread",
        top_k=3
    )


@pytest.mark.unit
def test_mem0_add_after_valid_intent(client, mocker):
    """测试用例3: mem0写入成功

    验证点:
    1. 意图验证通过后mem0.add被调用
    2. 写入内容包含意图类型和槽位信息

    参考: tasks.md lines 174-189
    """
    mock_mem = mocker.patch('emergency_agents.api.main._mem')
    mock_mem.search.return_value = []

    mock_classifier = mocker.patch('emergency_agents.api.main.intent_classifier_node')
    mock_classifier.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川", "disaster_type": "地震"}},
        "messages": []
    }

    mock_validator = mocker.patch('emergency_agents.api.main.validate_and_prompt_node')
    mock_validator.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川", "disaster_type": "地震"}},
        "validation_status": "valid"
    }

    mock_registry_func = mocker.patch('emergency_agents.api.main._require_intent_registry')
    mock_registry = MagicMock()
    mock_handler = MagicMock()
    mock_handler.handle = mocker.AsyncMock(return_value={"response_text": "已处理"})
    mock_registry.get.return_value = mock_handler
    mock_registry_func.return_value = mock_registry

    response = client.post("/intent/process", json={
        "user_id": "test-user",
        "thread_id": "test-thread",
        "message": "四川地震，坐标103.85,31.68，300人被困"
    })

    assert response.status_code == 200

    mock_mem.add.assert_called_once()
    call_kwargs = mock_mem.add.call_args[1]
    assert "意图:" in call_kwargs["content"]
    assert call_kwargs["user_id"] == "test-user"
    assert call_kwargs["run_id"] == "test-thread"


@pytest.mark.unit
def test_mem0_metrics_recorded_on_search(client, mocker):
    """测试Prometheus指标记录（search操作）

    验证点:
    1. search成功后_mem0_search_success.inc()被调用
    2. search延迟被_mem0_search_duration.observe()记录

    参考: tasks.md lines 109-118
    """
    mock_mem = mocker.patch('emergency_agents.api.main._mem')
    mock_mem.search.return_value = []

    mock_search_success = mocker.patch('emergency_agents.api.main._mem0_search_success')
    mock_search_duration = mocker.patch('emergency_agents.api.main._mem0_search_duration')

    mock_classifier = mocker.patch('emergency_agents.api.main.intent_classifier_node')
    mock_classifier.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川"}},
        "messages": []
    }

    mock_validator = mocker.patch('emergency_agents.api.main.validate_and_prompt_node')
    mock_validator.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川"}},
        "validation_status": "valid"
    }

    mock_registry_func = mocker.patch('emergency_agents.api.main._require_intent_registry')
    mock_registry = MagicMock()
    mock_handler = MagicMock()
    mock_handler.handle = mocker.AsyncMock(return_value={"response_text": "已处理"})
    mock_registry.get.return_value = mock_handler
    mock_registry_func.return_value = mock_registry

    response = client.post("/intent/process", json={
        "user_id": "test-user",
        "thread_id": "test-thread",
        "message": "测试消息"
    })

    assert response.status_code == 200
    mock_search_success.inc.assert_called_once()
    mock_search_duration.observe.assert_called_once()


@pytest.mark.unit
def test_mem0_metrics_recorded_on_add(client, mocker):
    """测试Prometheus指标记录（add操作）

    验证点:
    1. add成功后_mem0_add_success.inc()被调用

    参考: 基于search指标模式推导
    """
    mock_mem = mocker.patch('emergency_agents.api.main._mem')
    mock_mem.search.return_value = []

    mock_add_success = mocker.patch('emergency_agents.api.main._mem0_add_success')

    mock_classifier = mocker.patch('emergency_agents.api.main.intent_classifier_node')
    mock_classifier.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川"}},
        "messages": []
    }

    mock_validator = mocker.patch('emergency_agents.api.main.validate_and_prompt_node')
    mock_validator.return_value = {
        "intent": {"intent_type": "rescue-task-generate", "slots": {"location": "汶川"}},
        "validation_status": "valid"
    }

    mock_registry_func = mocker.patch('emergency_agents.api.main._require_intent_registry')
    mock_registry = MagicMock()
    mock_handler = MagicMock()
    mock_handler.handle = mocker.AsyncMock(return_value={"response_text": "已处理"})
    mock_registry.get.return_value = mock_handler
    mock_registry_func.return_value = mock_registry

    response = client.post("/intent/process", json={
        "user_id": "test-user",
        "thread_id": "test-thread",
        "message": "四川地震，坐标103.85,31.68"
    })

    assert response.status_code == 200
    mock_add_success.inc.assert_called()
