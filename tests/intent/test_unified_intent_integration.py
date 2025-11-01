# Copyright 2025 msq
"""统一意图处理集成测试（真实LLM调用）。

测试覆盖：
1. 端到端意图识别流程（unified mode）
2. 专家咨询触发（低置信度和未知意图）
3. 与intent_processor.py的集成
4. 配置切换（unified vs legacy）
5. 性能基准测试

注意：
- 这些测试会调用真实的LLM API
- 需要配置 OPENAI_BASE_URL 和 OPENAI_API_KEY
- 标记为 @pytest.mark.integration

参考：
- openspec/changes/unify-intent-processing/tasks.md (Phase 2.3)
- openspec/changes/unify-intent-processing/specs/intent-processing/spec.md
"""
import os
import time

import pytest

from emergency_agents.config import AppConfig
from emergency_agents.intent.expert_consult import expert_consult_node
from emergency_agents.intent.unified_intent import unified_intent_node
from emergency_agents.llm.client import get_openai_client


@pytest.fixture(scope="module")
def llm_client():
    """创建真实LLM客户端"""
    cfg = AppConfig.load_from_env()
    return get_openai_client(cfg)


@pytest.fixture(scope="module")
def llm_model():
    """获取LLM模型名称"""
    return os.getenv("LLM_MODEL", "glm-4.5-air")


@pytest.mark.integration
class TestUnifiedIntentIntegration:
    """统一意图处理集成测试"""

    def test_valid_rescue_intent_recognition(self, llm_client, llm_model):
        """测试有效救援意图识别（完整场景）"""
        state = {
            "messages": [
                {
                    "role": "user",
                    "content": "现在四川茂县发生了地震，需要去前突处置，坐标是103.85,31.68"
                }
            ]
        }

        t_start = time.time()
        result_state = unified_intent_node(state, llm_client, llm_model)
        t_end = time.time()

        duration_ms = int((t_end - t_start) * 1000)
        print(f"\n⏱️  Unified intent processing: {duration_ms}ms")

        unified_intent = result_state["unified_intent"]

        # 验证意图类型
        assert unified_intent["intent_type"] in [
            "RESCUE_TASK_GENERATION",
            "HAZARD_REPORT"
        ], f"Unexpected intent_type: {unified_intent['intent_type']}"

        # 验证置信度
        assert unified_intent["confidence"] >= 0.7, \
            f"Confidence too low: {unified_intent['confidence']}"

        # 验证验证状态
        assert unified_intent["validation_status"] in ["valid", "invalid"], \
            f"Unexpected validation_status: {unified_intent['validation_status']}"

        # 验证槽位提取
        slots = unified_intent["slots"]
        mission_type = slots.get("mission_type")
        assert mission_type, "Missing mission_type slot"
        assert any(keyword in str(mission_type) for keyword in ["前突", "救援", "处置"]), \
            f"mission_type不正确: {mission_type}"

        # 如果验证通过，应该有location
        if unified_intent["validation_status"] == "valid":
            location_value = slots.get("location_name") or slots.get("location_text") or slots.get("location")
            assert location_value, "Missing location slot"
            assert "茂县" in str(location_value) or "四川" in str(location_value), \
                f"location不正确: {location_value}"

        print(f"✅ Intent: {unified_intent['intent_type']}")
        print(f"✅ Confidence: {unified_intent['confidence']}")
        print(f"✅ Validation: {unified_intent['validation_status']}")
        print(f"✅ Slots: {slots}")

        # 性能要求：≤18秒（P95）
        assert duration_ms <= 18000, \
            f"Performance requirement not met: {duration_ms}ms > 18000ms"

    def test_invalid_intent_missing_fields(self, llm_client, llm_model):
        """测试缺少必填字段的无效意图"""
        state = {
            "messages": [{"role": "user", "content": "地震发生了"}]
        }

        result_state = unified_intent_node(state, llm_client, llm_model)
        unified_intent = result_state["unified_intent"]

        # 验证意图类型
        assert unified_intent["intent_type"] != "UNKNOWN", \
            "应该识别为具体意图类型，不是UNKNOWN"

        # 验证验证状态
        assert unified_intent["validation_status"] == "invalid", \
            f"Expected invalid, got: {unified_intent['validation_status']}"

        # 验证缺失字段
        missing_fields = set(unified_intent["missing_fields"])
        assert missing_fields, "Should have missing_fields"
        assert "location" in missing_fields, \
            f"缺失字段应包含location，实际为: {unified_intent['missing_fields']}"

        # 验证提示生成
        assert unified_intent["prompt"], \
            "Should generate prompt for missing fields"
        assert "地点" in unified_intent["prompt"], \
            f"Prompt should guide to补充地点, got: {unified_intent['prompt']}"

        print(f"✅ Invalid intent detected")
        print(f"✅ Missing fields: {unified_intent['missing_fields']}")
        print(f"✅ Prompt: {unified_intent['prompt']}")

    def test_unknown_intent_professional_question(self, llm_client, llm_model):
        """测试未知意图（专业应急问题）"""
        state = {
            "messages": [
                {"role": "user", "content": "什么情况下需要启动一级响应？"}
            ]
        }

        result_state = unified_intent_node(state, llm_client, llm_model)
        unified_intent = result_state["unified_intent"]

        # 可能识别为UNKNOWN或低置信度
        if unified_intent["confidence"] < 0.7 or unified_intent["validation_status"] == "unknown":
            print(f"✅ Triggered expert consultation")
            print(f"   Confidence: {unified_intent['confidence']}")
            print(f"   Validation: {unified_intent['validation_status']}")

            # 测试专家咨询节点
            result_state = expert_consult_node(result_state, llm_client, llm_model)
            expert_consult = result_state["expert_consult"]

            # 验证专家响应
            assert expert_consult["response"], "Expert response should not be empty"
            assert len(expert_consult["response"]) > 50, \
                "Expert response should be substantial"
            assert expert_consult["source"] == "emergency_expert_system"
            assert expert_consult["trigger_reason"] in [
                "low_confidence", "unknown_intent"
            ]

            # 验证专业性（应该包含应急术语）
            response_text = expert_consult["response"]
            professional_keywords = ["应急", "响应", "预案", "救援", "灾害", "指挥"]
            has_keywords = any(kw in response_text for kw in professional_keywords)
            assert has_keywords, \
                f"Response should contain professional emergency terms: {response_text[:100]}"

            print(f"✅ Expert response length: {len(expert_consult['response'])} chars")
            print(f"✅ Trigger reason: {expert_consult['trigger_reason']}")
            print(f"✅ Response preview: {expert_consult['response'][:200]}...")
        else:
            print(f"ℹ️  Recognized as valid intent: {unified_intent['intent_type']}")

    def test_out_of_scope_refusal(self, llm_client, llm_model):
        """测试超范围问题的礼貌拒绝"""
        state = {
            "messages": [{"role": "user", "content": "今天天气怎么样？"}]
        }

        result_state = unified_intent_node(state, llm_client, llm_model)
        unified_intent = result_state["unified_intent"]

        # 应该识别为未知或低置信度
        if unified_intent["confidence"] < 0.7 or unified_intent["validation_status"] == "unknown":
            result_state = expert_consult_node(result_state, llm_client, llm_model)
            expert_consult = result_state["expert_consult"]

            response_text = expert_consult["response"]

            # 验证拒绝表述
            refusal_keywords = ["抱歉", "超出", "范围", "不支持", "不提供"]
            has_refusal = any(kw in response_text for kw in refusal_keywords)
            assert has_refusal, \
                f"Response should politely refuse out-of-scope questions: {response_text}"

            # 验证引导回应急领域
            emergency_keywords = ["应急", "救援", "灾害"]
            has_guidance = any(kw in response_text for kw in emergency_keywords)
            assert has_guidance, \
                f"Response should guide back to emergency domain: {response_text}"

            print(f"✅ Out-of-scope question properly refused")
            print(f"✅ Response: {response_text[:200]}...")
        else:
            print(f"ℹ️  Unexpected: classified as {unified_intent['intent_type']}")

    def test_idempotency(self, llm_client, llm_model):
        """测试幂等性：多次调用只执行一次LLM"""
        state = {
            "messages": [
                {"role": "user", "content": "四川茂县地震，需要救援"}
            ]
        }

        # 第一次调用
        t1_start = time.time()
        result_state = unified_intent_node(state, llm_client, llm_model)
        t1_end = time.time()
        duration1_ms = int((t1_end - t1_start) * 1000)

        # 第二次调用（应该直接返回，不调用LLM）
        t2_start = time.time()
        result_state2 = unified_intent_node(result_state, llm_client, llm_model)
        t2_end = time.time()
        duration2_ms = int((t2_end - t2_start) * 1000)

        print(f"⏱️  First call: {duration1_ms}ms")
        print(f"⏱️  Second call (cached): {duration2_ms}ms")

        # 第二次调用应该非常快（<10ms）
        assert duration2_ms < 10, \
            f"Second call should be instant (cached): {duration2_ms}ms"

        # 结果应该完全相同
        assert result_state2["unified_intent"] == result_state["unified_intent"]

        print(f"✅ Idempotency verified: {duration1_ms}ms → {duration2_ms}ms")

    def test_performance_target(self, llm_client, llm_model):
        """测试性能目标：单次统一调用≤18秒（P95）"""
        test_inputs = [
            "四川茂县发生地震，坐标103.85,31.68",
            "需要紧急医疗救援",
            "请求空中支援",
        ]

        durations = []

        for input_text in test_inputs:
            state = {"messages": [{"role": "user", "content": input_text}]}

            t_start = time.time()
            result_state = unified_intent_node(state, llm_client, llm_model)
            t_end = time.time()

            duration_ms = int((t_end - t_start) * 1000)
            durations.append(duration_ms)

            print(f"⏱️  '{input_text[:30]}...': {duration_ms}ms")

        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)

        print(f"\n📊 Performance Summary:")
        print(f"   Average: {avg_duration:.0f}ms")
        print(f"   Max (P100): {max_duration}ms")
        print(f"   Min: {min(durations)}ms")

        # P95目标：≤18秒
        assert max_duration <= 18000, \
            f"Performance target not met: {max_duration}ms > 18000ms"

        # 期望平均值≤15秒
        assert avg_duration <= 15000, \
            f"Average performance target not met: {avg_duration:.0f}ms > 15000ms"

        print(f"✅ Performance targets met")


@pytest.mark.integration
class TestIntegrationWithProcessor:
    """测试与intent_processor.py的集成"""

    @pytest.mark.skip(reason="需要完整的数据库和服务依赖，在实际环境中测试")
    def test_end_to_end_unified_mode(self):
        """端到端测试：统一模式完整流程"""
        # 这个测试需要：
        # 1. PostgreSQL数据库
        # 2. Mem0服务
        # 3. Intent handler注册表
        # 4. 完整的process_intent_core函数
        pass

    @pytest.mark.skip(reason="需要完整的数据库和服务依赖，在实际环境中测试")
    def test_mode_switching(self):
        """测试统一模式和旧版模式切换"""
        # 测试通过环境变量切换模式
        pass


if __name__ == "__main__":
    # 快速手动测试
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

    print("手动测试 - 统一意图处理集成")
    print("=" * 60)

    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    model = os.getenv("LLM_MODEL", "glm-4.5-air")

    test_state = {
        "messages": [
            {"role": "user", "content": "四川茂县发生地震，需要救援，坐标103.85,31.68"}
        ]
    }

    print(f"测试输入: {test_state['messages'][0]['content']}")
    print(f"使用模型: {model}")

    t_start = time.time()
    result = unified_intent_node(test_state, client, model)
    t_end = time.time()

    print(f"\n⏱️  耗时: {int((t_end - t_start) * 1000)}ms")
    print(f"🎯 结果:")

    import json
    print(json.dumps(result["unified_intent"], ensure_ascii=False, indent=2))

    print("\n✅ 手动测试完成")
