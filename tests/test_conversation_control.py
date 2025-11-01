# Copyright 2025 msq
"""对话管控测试：取消/重试/帮助。

验证专家在演示中可以随时脱困。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_conversation_control_cancel():
    """测试取消指令。"""
    print("\n=== 测试1：对话管控 - 取消 ===")
    
    from emergency_agents.intent.router import intent_router_node
    
    state = {
        "intent": {
            "intent_type": "conversation_control",
            "slots": {"command": "cancel"},
            "meta": {}
        },
        "validation_attempt": 2
    }
    
    result = intent_router_node(state)
    
    assert result.get("status") == "cancelled", "应设置status为cancelled"
    assert result.get("validation_attempt") == 0, "应重置validation_attempt"
    assert result.get("router_next") == "done", "应路由到done"
    
    timeline = result.get("timeline", [])
    assert any("conversation_cancel" in str(e) for e in timeline), "应记录timeline事件"
    
    print("✅ 取消指令测试通过")


def test_conversation_control_retry():
    """测试重试指令。"""
    print("\n=== 测试2：对话管控 - 重试 ===")
    
    from emergency_agents.intent.router import intent_router_node
    
    state = {
        "intent": {
            "intent_type": "conversation_control",
            "slots": {"command": "retry"},
            "meta": {}
        },
        "validation_attempt": 3
    }
    
    result = intent_router_node(state)
    
    assert result.get("validation_attempt") == 0, "应重置validation_attempt"
    assert result.get("router_next") == "analysis", "应重新进入分析流程"
    assert result.get("intent") == {}, "应清空intent"
    
    print("✅ 重试指令测试通过")


def test_conversation_control_help():
    """测试帮助指令。"""
    print("\n=== 测试3：对话管控 - 帮助 ===")
    
    from emergency_agents.intent.router import intent_router_node
    
    state = {
        "intent": {
            "intent_type": "conversation_control",
            "slots": {"command": "help"},
            "meta": {}
        }
    }
    
    result = intent_router_node(state)
    
    assert "help_response" in result, "应生成帮助文本"
    assert "侦察" in result["help_response"], "帮助文本应包含示例"
    assert result.get("router_next") == "done", "应路由到done"
    
    print(f"帮助文本: {result['help_response']}")
    print("✅ 帮助指令测试通过")


def test_conversation_control_schema():
    """测试conversation_control schema定义。"""
    print("\n=== 测试4：conversation_control Schema ===")
    
    from emergency_agents.intent.schemas import INTENT_SCHEMAS
    
    assert "conversation_control" in INTENT_SCHEMAS, "应注册conversation_control"
    
    schema = INTENT_SCHEMAS["conversation_control"]
    assert "command" in schema["required"], "command应为必填字段"
    
    print(f"Schema: {schema}")
    print("✅ Schema定义正确")


def test_conversation_control_in_validator():
    """测试conversation_control在validator中正确验证。"""
    print("\n=== 测试5：conversation_control通过validator ===")
    
    from emergency_agents.intent.validator import validate_and_prompt_node
    
    class MockLLM:
        class Completion:
            def __init__(self):
                self.message = type('obj', (object,), {'content': '请提供指令。'})()
        
        class Completions:
            def create(self, **kwargs):
                return type('obj', (object,), {'choices': [MockLLM.Completion()]})()
        
        def __init__(self):
            self.chat = type('obj', (object,), {'completions': self.Completions()})()
    
    state_完整 = {
        "intent": {
            "intent_type": "conversation_control",
            "slots": {"command": "cancel"},
            "meta": {}
        }
    }
    
    result = validate_and_prompt_node(state_完整, MockLLM(), "mock")
    
    assert result.get("validation_status") == "valid", "完整command应通过验证"
    print("✅ 完整command验证通过")
    
    state_缺槽 = {
        "intent": {
            "intent_type": "conversation_control",
            "slots": {},
            "meta": {}
        }
    }
    
    result = validate_and_prompt_node(state_缺槽, MockLLM(), "mock")
    
    assert result.get("validation_status") == "invalid", "缺command应触发追问"
    assert "command" in result.get("missing_fields", []), "应识别缺失command"
    print("✅ 缺槽追问正确")


if __name__ == "__main__":
    print("=" * 60)
    print("对话管控测试套件")
    print("=" * 60)
    
    try:
        test_conversation_control_schema()
        test_conversation_control_in_validator()
        test_conversation_control_cancel()
        test_conversation_control_retry()
        test_conversation_control_help()
        
        print("\n" + "=" * 60)
        print("✅ 所有对话管控测试通过 (5/5)")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

