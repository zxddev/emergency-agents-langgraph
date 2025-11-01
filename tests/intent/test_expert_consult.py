# Copyright 2025 msq
"""专家咨询模块单元测试（Mock LLM）。

测试覆盖：
1. 提示词加载功能
2. expert_consult_node基础功能
3. 幂等性检查
4. 触发原因识别（low_confidence/unknown_intent）
5. 用户输入提取
6. 专业响应生成
7. 异常处理和兜底机制

参考：
- src/emergency_agents/intent/expert_consult.py
- openspec/changes/unify-intent-processing/tasks.md (Phase 1.3)
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from emergency_agents.intent.expert_consult import (
    ExpertConsultResult,
    expert_consult_node,
    load_expert_prompt,
)


class TestLoadExpertPrompt:
    """测试提示词加载函数"""

    def test_load_prompt_success(self):
        """测试成功加载提示词"""
        prompt = load_expert_prompt()

        # 验证提示词不为空
        assert prompt
        assert len(prompt) > 0

        # 验证包含关键内容
        assert "应急指挥车" in prompt or "应急救援" in prompt
        assert "专业" in prompt

    def test_prompt_file_exists(self):
        """测试提示词文件存在"""
        project_root = Path(__file__).parent.parent.parent
        prompt_path = project_root / "config" / "prompts" / "emergency_command_expert.txt"

        assert prompt_path.exists(), f"Prompt file not found: {prompt_path}"

    @patch("emergency_agents.intent.expert_consult.Path.read_text")
    def test_prompt_read_error_handling(self, mock_read_text):
        """测试提示词读取错误处理"""
        mock_read_text.side_effect = OSError("读取文件失败")

        with pytest.raises(OSError):
            load_expert_prompt()


class TestExpertConsultResult:
    """测试Pydantic模型验证"""

    def test_valid_result(self):
        """测试有效结果"""
        result = ExpertConsultResult(
            response="根据《国家自然灾害救助应急预案》，一级响应...",
            source="emergency_expert_system",
            trigger_reason="low_confidence",
            confidence=0.6
        )
        assert result.response.startswith("根据《国家自然灾害救助应急预案》")
        assert result.source == "emergency_expert_system"
        assert result.trigger_reason == "low_confidence"
        assert result.confidence == 0.6

    def test_default_source(self):
        """测试默认source值"""
        result = ExpertConsultResult(
            response="测试响应",
            trigger_reason="unknown_intent"
        )
        assert result.source == "emergency_expert_system"

    def test_optional_confidence(self):
        """测试可选的confidence字段"""
        result = ExpertConsultResult(
            response="测试响应",
            trigger_reason="manual_trigger",
            confidence=None
        )
        assert result.confidence is None


class TestExpertConsultNode:
    """测试专家咨询节点"""

    @pytest.fixture
    def mock_llm_client(self):
        """创建Mock LLM客户端"""
        client = MagicMock()
        return client

    @pytest.fixture
    def professional_response(self):
        """模拟专业应急响应"""
        return """根据《国家自然灾害救助应急预案》，启动一级响应需要满足以下条件：

1. 灾害严重程度：
   - 死亡人数达到或预计达到100人以上
   - 紧急转移安置10万人以上
   - 房屋倒塌或严重损坏1万间以上

2. 决策流程：
   - 由国家减灾委主任决定启动
   - 国务院统一指挥协调
   - 省级政府负责具体实施

3. 响应措施：
   - 调动国家应急救援队伍
   - 启动中央救灾物资储备
   - 派遣工作组赴灾区指导

建议：当前如有灾情，请立即评估是否达到上述标准，并逐级上报。"""

    @pytest.fixture
    def out_of_scope_response(self):
        """模拟超范围问题的拒绝响应"""
        return """抱歉，您的问题超出了应急救灾指挥系统的专业范围。

本系统专注于：
- 应急救灾与灾害响应
- 救援力量调度与资源配置
- 指挥决策支持与风险评估

关于天气预报，建议您咨询：
- 气象部门：查看官方天气预报
- 应急气象服务热线：400-xxxx-xxxx

如有应急救援相关问题，我随时为您提供专业建议。"""

    def test_idempotency_check(self, mock_llm_client):
        """测试幂等性检查：如果expert_consult已存在，不调用LLM"""
        existing_result = {
            "response": "已有的专家回答",
            "source": "emergency_expert_system",
            "trigger_reason": "low_confidence"
        }
        state = {
            "messages": [{"role": "user", "content": "什么情况启动一级响应？"}],
            "expert_consult": existing_result
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        # 应该直接返回原状态，不调用LLM
        mock_llm_client.chat.completions.create.assert_not_called()
        assert result_state["expert_consult"] == existing_result

    def test_no_input_returns_default_greeting(self, mock_llm_client):
        """测试无输入时返回默认问候"""
        state = {}  # 无messages和raw_report

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        # 不应调用LLM
        mock_llm_client.chat.completions.create.assert_not_called()

        # 返回默认问候
        expert_consult = result_state["expert_consult"]
        assert "AI专家顾问" in expert_consult["response"]
        assert expert_consult["trigger_reason"] == "no_input"
        assert expert_consult["confidence"] is None

    def test_trigger_reason_low_confidence(self, mock_llm_client, professional_response):
        """测试低置信度触发"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "什么情况启动一级响应？"}],
            "unified_intent": {
                "confidence": 0.5,  # 低于0.7阈值
                "validation_status": "valid"
            }
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        expert_consult = result_state["expert_consult"]
        assert expert_consult["trigger_reason"] == "low_confidence"
        assert expert_consult["confidence"] == 0.5
        assert "一级响应" in expert_consult["response"]

    def test_trigger_reason_unknown_intent(self, mock_llm_client, professional_response):
        """测试未知意图触发"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "地震预警系统如何工作？"}],
            "unified_intent": {
                "confidence": 0.8,
                "validation_status": "unknown"  # 未知状态
            }
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        expert_consult = result_state["expert_consult"]
        assert expert_consult["trigger_reason"] == "unknown_intent"

    @patch.dict(os.environ, {"UNKNOWN_CONFIDENCE_THRESHOLD": "0.6"})
    def test_custom_confidence_threshold(self, mock_llm_client, professional_response):
        """测试自定义置信度阈值"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "测试"}],
            "unified_intent": {
                "confidence": 0.55,  # 低于自定义阈值0.6
                "validation_status": "valid"
            }
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        expert_consult = result_state["expert_consult"]
        assert expert_consult["trigger_reason"] == "low_confidence"

    def test_extract_input_from_messages(self, mock_llm_client, professional_response):
        """测试从messages提取用户输入"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [
                {"role": "system", "content": "系统消息"},
                {"role": "user", "content": "第一条问题"},
                {"role": "assistant", "content": "回答"},
                {"role": "user", "content": "什么情况启动一级响应？"}  # 应该提取这条
            ],
            "unified_intent": {"confidence": 0.5, "validation_status": "valid"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        # 验证LLM被调用，并且使用了正确的输入
        mock_llm_client.chat.completions.create.assert_called_once()
        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args[1]["messages"][1]["content"] == "什么情况启动一级响应？"

    def test_extract_input_from_raw_report(self, mock_llm_client, professional_response):
        """测试从raw_report提取输入（无messages时）"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "raw_report": "地震后如何组织群众疏散？",
            "unified_intent": {"confidence": 0.4, "validation_status": "valid"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        call_args = mock_llm_client.chat.completions.create.call_args
        assert "地震后如何组织群众疏散？" in call_args[1]["messages"][1]["content"]

    def test_llm_call_parameters(self, mock_llm_client, professional_response):
        """测试LLM调用参数"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "测试"}],
            "unified_intent": {"confidence": 0.5, "validation_status": "valid"}
        }

        expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        call_args = mock_llm_client.chat.completions.create.call_args
        assert call_args[1]["model"] == "glm-4.5-air"
        assert call_args[1]["temperature"] == 0.3  # 允许适度创造性
        assert len(call_args[1]["messages"]) == 2  # system + user
        assert call_args[1]["messages"][0]["role"] == "system"
        assert call_args[1]["messages"][1]["role"] == "user"

    def test_professional_response_content(self, mock_llm_client, professional_response):
        """测试专业响应内容"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "什么情况启动一级响应？"}],
            "unified_intent": {"confidence": 0.5, "validation_status": "valid"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        expert_consult = result_state["expert_consult"]
        assert expert_consult["response"] == professional_response
        assert expert_consult["source"] == "emergency_expert_system"
        assert len(expert_consult["response"]) > 50  # 专业回答应该有内容

    def test_out_of_scope_refusal(self, mock_llm_client, out_of_scope_response):
        """测试超范围问题的礼貌拒绝"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = out_of_scope_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "今天天气怎么样？"}],
            "unified_intent": {"confidence": 0.3, "validation_status": "unknown"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        expert_consult = result_state["expert_consult"]
        assert "抱歉" in expert_consult["response"] or "超出" in expert_consult["response"]
        assert "应急" in expert_consult["response"]  # 应该引导回应急领域

    @patch("emergency_agents.intent.expert_consult.load_expert_prompt")
    def test_fallback_prompt_on_load_failure(self, mock_load, mock_llm_client):
        """测试提示词加载失败时使用内置兜底提示词"""
        mock_load.side_effect = FileNotFoundError("提示词文件不存在")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "兜底响应"
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "测试"}],
            "unified_intent": {"confidence": 0.5, "validation_status": "valid"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        # 应该使用内置兜底提示词继续执行
        mock_llm_client.chat.completions.create.assert_called_once()

        # 验证使用了内置提示词
        call_args = mock_llm_client.chat.completions.create.call_args
        system_message = call_args[1]["messages"][0]["content"]
        assert "应急指挥车" in system_message or "应急" in system_message

    def test_exception_handling(self, mock_llm_client):
        """测试异常处理返回兜底响应"""
        mock_llm_client.chat.completions.create.side_effect = Exception("LLM调用失败")

        state = {
            "messages": [{"role": "user", "content": "测试"}],
            "unified_intent": {"confidence": 0.5, "validation_status": "valid"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        # 应该返回兜底响应，不抛出异常
        expert_consult = result_state["expert_consult"]
        assert "抱歉" in expert_consult["response"]
        assert "系统当前无法处理" in expert_consult["response"]
        assert expert_consult["source"] == "emergency_expert_system"
        assert expert_consult["trigger_reason"] == "low_confidence"

    def test_result_structure(self, mock_llm_client, professional_response):
        """测试返回结果结构完整性"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = professional_response
        mock_llm_client.chat.completions.create.return_value = mock_response

        state = {
            "messages": [{"role": "user", "content": "测试"}],
            "unified_intent": {"confidence": 0.6, "validation_status": "valid"}
        }

        result_state = expert_consult_node(state, mock_llm_client, "glm-4.5-air")

        expert_consult = result_state["expert_consult"]

        # 验证所有必需字段存在
        assert "response" in expert_consult
        assert "source" in expert_consult
        assert "trigger_reason" in expert_consult
        assert "confidence" in expert_consult

        # 验证类型正确
        assert isinstance(expert_consult["response"], str)
        assert expert_consult["source"] == "emergency_expert_system"
        assert expert_consult["trigger_reason"] in ["low_confidence", "unknown_intent", "manual_trigger"]
        assert isinstance(expert_consult["confidence"], (float, int)) or expert_consult["confidence"] is None
