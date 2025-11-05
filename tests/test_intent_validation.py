# Copyright 2025 msq
"""意图识别与槽位校验测试。

验证完整闭环：
1. 缺槽追问：输入缺坐标 → validator追问 → 补充后通过
2. 高风险确认：机器狗控制 → 读回确认 → 确认后执行
3. 完整槽位：直接通过验证 → 路由执行
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from emergency_agents.intent.schemas import INTENT_SCHEMAS
from emergency_agents.intent.validator import validate_and_prompt_node, set_default_robotdog_id

set_default_robotdog_id(None)


class MockLLMClient:
    """Mock LLM客户端用于测试。"""
    
    class Completion:
        def __init__(self, content: str):
            self.message = type('obj', (object,), {'content': content})()
    
    class Completions:
        def create(self, **kwargs):
            return type('obj', (object,), {
                'choices': [MockLLMClient.Completion("请提供目标坐标（经度/纬度）。")]
            })()
    
    def __init__(self):
        self.chat = type('obj', (object,), {'completions': self.Completions()})()


def test_schema_loading():
    """测试Schema是否正确加载。"""
    print("\n=== 测试1：Schema加载 ===")
    print(f"✅ 已注册{len(INTENT_SCHEMAS)}个intent")
    assert len(INTENT_SCHEMAS) >= 19, f"期望至少19个intent，实际{len(INTENT_SCHEMAS)}"
    
    required_intents = [
        "recon_minimal",
        "device_control_robotdog",
        "trapped_report",
        "task-progress-query",
        "location-positioning",
        "device-control",
        "video-analysis",
    ]
    for intent in required_intents:
        assert intent in INTENT_SCHEMAS, f"缺少{intent}"
        print(f"✅ {intent} schema已定义")
    
    print("✅ 测试1通过")


def test_recon_minimal_missing_slots():
    """测试缺槽追问：recon_minimal缺少坐标。"""
    print("\n=== 测试2：缺槽追问（recon_minimal） ===")
    
    state = {
        "intent": {
            "intent_type": "recon_minimal",
            "slots": {"alt_m": 50},
            "meta": {"need_confirm": False}
        }
    }
    
    mock_llm = MockLLMClient()
    result = validate_and_prompt_node(state, mock_llm, "mock-model")
    
    print(f"validation_status: {result.get('validation_status')}")
    print(f"missing_fields: {result.get('missing_fields')}")
    print(f"prompt: {result.get('prompt')}")
    
    assert result.get("validation_status") == "invalid", "应返回invalid"
    assert "lng" in result.get("missing_fields", []), "应包含lng"
    assert "lat" in result.get("missing_fields", []), "应包含lat"
    assert result.get("prompt"), "应生成追问文本"
    assert result.get("validation_attempt") == 1, "首次尝试应为1"
    
    print("✅ 测试2通过")


def test_trapped_report_valid_slots():
    """测试完整槽位通过验证。"""
    print("\n=== 测试3：完整槽位通过（trapped_report） ===")
    
    state = {
        "intent": {
            "intent_type": "trapped_report",
            "slots": {
                "count": 10,
                "lat": 31.68,
                "lng": 103.85,
                "description": "水磨镇被困群众"
            },
            "meta": {"need_confirm": False}
        }
    }
    
    mock_llm = MockLLMClient()
    result = validate_and_prompt_node(state, mock_llm, "mock-model")
    
    print(f"validation_status: {result.get('validation_status')}")
    
    assert result.get("validation_status") == "valid", "应返回valid"
    assert "prompt" not in result or not result["prompt"], "不应生成追问"
    
    print("✅ 测试3通过")


def test_robotdog_missing_device_id():
    """测试机器狗控制缺少设备ID时触发追问。"""
    print("\n=== 测试4：缺槽追问（device_control_robotdog 缺设备ID） ===")
    set_default_robotdog_id(None)

    state = {
        "intent": {
            "intent_type": "device_control_robotdog",
            "slots": {"action": "forward"},
            "meta": {"need_confirm": True}
        }
    }

    mock_llm = MockLLMClient()
    result = validate_and_prompt_node(state, mock_llm, "mock-model")

    print(f"validation_status: {result.get('validation_status')}")
    print(f"missing_fields: {result.get('missing_fields')}")
    print(f"prompt: {result.get('prompt')}")

    assert result.get("validation_status") == "invalid", "缺设备ID应返回invalid"
    assert "device_id" in result.get("missing_fields", []), "缺失字段应包含device_id"
    assert result.get("prompt"), "缺设备ID时必须生成追问"
    assert result.get("validation_attempt") == 1, "首次尝试计数应为1"

    print("✅ 测试4通过")


def test_robotdog_with_device_id_pass():
    """测试机器狗控制提供设备ID时正常通过。"""
    print("\n=== 测试5：完整槽位通过（device_control_robotdog） ===")
    set_default_robotdog_id(None)

    state = {
        "intent": {
            "intent_type": "device_control_robotdog",
            "slots": {"action": "forward", "device_id": "dog-1"},
            "meta": {"need_confirm": True}
        }
    }

    mock_llm = MockLLMClient()
    result = validate_and_prompt_node(state, mock_llm, "mock-model")

    print(f"validation_status: {result.get('validation_status')}")

    assert result.get("validation_status") == "valid", "提供完整参数应返回valid"
    assert not result.get("prompt"), "完整参数不应生成追问"

    print("✅ 测试5通过")


def test_robotdog_uses_default_device_id():
    """测试配置默认ID时允许缺省槽位。"""
    print("\n=== 测试5.1：默认设备ID放行 ===")
    previous = set_default_robotdog_id("dog-11")
    try:
        state = {
            "intent": {
                "intent_type": "device_control_robotdog",
                "slots": {"action": "forward"},
                "meta": {"need_confirm": False},
            }
        }

        mock_llm = MockLLMClient()
        result = validate_and_prompt_node(state, mock_llm, "mock-model")

        print(f"validation_status: {result.get('validation_status')}")
        assert result.get("validation_status") == "valid", "配置默认ID时应直接通过"
        assert not result.get("prompt"), "默认ID放行不应生成追问"
    finally:
        set_default_robotdog_id(previous)

    print("✅ 测试5.1通过")


def test_max_attempts_protection():
    """测试max_attempts=3保护。"""
    print("\n=== 测试6：max_attempts保护 ===")
    
    state = {
        "intent": {
            "intent_type": "recon_minimal",
            "slots": {},
            "meta": {}
        },
        "validation_attempt": 3
    }
    
    mock_llm = MockLLMClient()
    result = validate_and_prompt_node(state, mock_llm, "mock-model")
    
    print(f"validation_status: {result.get('validation_status')}")
    print(f"validation_attempt: {result.get('validation_attempt')}")
    
    assert result.get("validation_status") == "failed", "超过3次应返回failed"
    assert result.get("validation_attempt") == 4, "尝试次数应为4"
    
    print("✅ 测试6通过")


def test_unknown_intent_skip_validation():
    """测试未知intent跳过验证。"""
    print("\n=== 测试7：未知intent跳过验证 ===")
    
    state = {
        "intent": {
            "intent_type": "unregistered_custom_intent",
            "slots": {},
            "meta": {}
        }
    }
    
    mock_llm = MockLLMClient()
    result = validate_and_prompt_node(state, mock_llm, "mock-model")
    
    print(f"validation_status: {result.get('validation_status')}")
    
    assert result.get("validation_status") == "valid", "无schema的intent应返回valid跳过"
    
    print("✅ 测试7通过")


if __name__ == "__main__":
    print("=" * 60)
    print("意图识别与槽位校验测试套件")
    print("=" * 60)
    
    try:
        test_schema_loading()
        test_recon_minimal_missing_slots()
        test_trapped_report_valid_slots()
        test_robotdog_missing_device_id()
        test_robotdog_with_device_id_pass()
        test_max_attempts_protection()
        test_unknown_intent_skip_validation()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过 (7/7)")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
