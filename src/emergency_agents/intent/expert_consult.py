# Copyright 2025 msq
"""专业应急专家咨询模块：处理未知意图或低置信度查询。

本模块实现专业应急指挥专家系统，当用户查询超出预定义意图范围时：
1. 加载专业应急领域提示词
2. 调用LLM进行专业解答
3. 返回结构化响应（包含source标识）

设计原则：
- 专业性：基于应急管理理论和实战经验
- 精准性：引用具体预案、规范、流程
- 实操性：给出可执行建议
- 拒绝超范围：礼貌拒绝非应急领域问题

参考文档：
- config/prompts/emergency_command_expert.txt
- openspec/changes/unify-intent-processing/design.md (Decision 2)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, Field
from emergency_agents.llm.endpoint_manager import LLMEndpointsExhaustedError

logger = logging.getLogger(__name__)


class ExpertConsultResult(BaseModel):
    """专家咨询结果（强类型）。

    Attributes:
        response: 专家回答内容（中文，专业应急术语）
        source: 响应来源标识（固定为'emergency_expert_system'）
        trigger_reason: 触发原因（low_confidence或unknown_intent）
        confidence: 原始意图识别置信度（如果适用）
    """
    response: str = Field(..., description="专家回答内容")
    source: str = Field(default="emergency_expert_system", description="响应来源")
    trigger_reason: str = Field(..., description="触发原因")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="原始置信度")


def load_expert_prompt() -> str:
    """从配置文件加载应急专家提示词。

    Returns:
        专家系统提示词文本

    Raises:
        FileNotFoundError: 如果提示词文件不存在
        OSError: 如果文件读取失败
    """
    project_root = Path(__file__).parent.parent.parent.parent
    prompt_path = project_root / "config" / "prompts" / "emergency_command_expert.txt"

    if not prompt_path.exists():
        logger.error("expert_prompt_not_found", extra={"path": str(prompt_path)})
        raise FileNotFoundError(f"Expert prompt file not found: {prompt_path}")

    try:
        content = prompt_path.read_text(encoding="utf-8")
        logger.debug("expert_prompt_loaded", extra={"length": len(content)})
        return content
    except OSError as e:
        logger.error("expert_prompt_read_failed", extra={"error": str(e)}, exc_info=True)
        raise


def expert_consult_node(
    state: Dict[str, Any],
    llm_client,
    llm_model: str
) -> Dict[str, Any]:
    """专家咨询节点：处理未知意图或低置信度查询。

    触发条件：
    1. unified_intent["confidence"] < UNKNOWN_CONFIDENCE_THRESHOLD（默认0.7）
    2. unified_intent["validation_status"] == "unknown"

    工作流程：
    1. 幂等性检查：如果state["expert_consult"]已存在，直接返回
    2. 提取用户输入：从messages或raw_report获取
    3. 加载专家提示词：从config/prompts/emergency_command_expert.txt
    4. 调用LLM：temperature=0.3（允许适度创造性）
    5. 返回结构化结果：包含response和source

    Args:
        state: 图状态，期望包含messages或raw_report
        llm_client: LLM客户端（OpenAI兼容接口）
        llm_model: 模型名（推荐glm-4.5-air或glm-4）

    Returns:
        更新后的state，包含expert_consult字段

    示例：
        >>> state = {
        ...     "messages": [{"role": "user", "content": "什么情况启动一级响应？"}],
        ...     "unified_intent": {"confidence": 0.5, "validation_status": "unknown"}
        ... }
        >>> result = expert_consult_node(state, llm_client, "glm-4.5-air")
        >>> result["expert_consult"]["response"]
        '根据《国家自然灾害救助应急预案》...'
    """
    # 幂等性检查（避免重复LLM调用）
    if "expert_consult" in state and state["expert_consult"]:
        logger.debug("expert_consult already exists, skipping LLM call")
        return state

    # 提取用户输入
    input_text = ""
    msgs = state.get("messages") or []
    if isinstance(msgs, list) and msgs:
        for msg in reversed(msgs):
            if isinstance(msg, dict) and msg.get("role") == "user" and msg.get("content"):
                input_text = str(msg.get("content"))
                break

    if not input_text:
        input_text = str(state.get("raw_report") or "").strip()

    if not input_text:
        # 无输入则返回默认响应
        logger.warning("expert_consult: no input text found")
        result = ExpertConsultResult(
            response="您好，我是应急指挥系统的AI专家顾问。请描述您遇到的应急救援问题，我将为您提供专业建议。",
            source="emergency_expert_system",
            trigger_reason="no_input",
            confidence=None
        )
        return state | {"expert_consult": result.model_dump()}

    # 确定触发原因
    unified_intent = state.get("unified_intent", {})
    confidence = unified_intent.get("confidence")
    validation_status = unified_intent.get("validation_status")

    if validation_status == "unknown":
        trigger_reason = "unknown_intent"
    elif confidence is not None and confidence < float(os.getenv("UNKNOWN_CONFIDENCE_THRESHOLD", "0.7")):
        trigger_reason = "low_confidence"
    else:
        trigger_reason = "manual_trigger"

    try:
        logger.info("expert_consult_triggered", extra={
            "input_preview": input_text[:50],
            "trigger_reason": trigger_reason,
            "confidence": confidence
        })

        # 加载专家提示词
        try:
            system_prompt = load_expert_prompt()
        except (FileNotFoundError, OSError) as e:
            logger.error("expert_consult_prompt_load_failed", extra={"error": str(e)})
            # 使用内置兜底提示词
            system_prompt = """你是车载前突应急指挥车的AI专家顾问。
你的用户是应急救援现场的指挥员（非普通公众）。

专业领域：应急救灾与灾害响应、救援力量调度、指挥决策支持。

回答要求：
1. 专业性：基于应急管理理论和实战经验
2. 精准性：引用具体预案、规范、流程
3. 中文回复：使用应急领域术语
4. 深度思考：分析多个维度（人员、装备、时间、风险）
5. 实操导向：给出可执行建议

不允许：
- 闲聊或娱乐性对话
- 超出应急救灾领域的问题（礼貌拒绝并引导回主题）
- 模棱两可的建议（必须明确是/否，或给出决策依据）
"""

        # 调用LLM（temperature=0.3，允许适度创造性）
        rsp = llm_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text}
            ],
            temperature=0.3  # 比意图识别（0.0）稍高，允许专业解释的灵活性
        )

        response_text = rsp.choices[0].message.content

        result = ExpertConsultResult(
            response=response_text,
            source="emergency_expert_system",
            trigger_reason=trigger_reason,
            confidence=confidence
        )

        logger.info("expert_consult_success", extra={
            "trigger_reason": trigger_reason,
            "response_length": len(response_text)
        })

        return state | {"expert_consult": result.model_dump()}

    except LLMEndpointsExhaustedError as exc:
        logger.error("expert_consult_llm_overloaded", extra={"error": str(exc), "states": getattr(exc, "states", {})})
        fallback_result = ExpertConsultResult(
            response="抱歉，当前模型正忙，请稍后再试或改为人工咨询。",
            source="emergency_expert_system",
            trigger_reason=trigger_reason,
            confidence=confidence
        )
        return state | {
            "expert_consult": fallback_result.model_dump(),
            "llm_overload": {"reason": "rate_limit", "message": "模型限流"},
        }

    except Exception as e:
        logger.error("expert_consult_failed", extra={
            "error": str(e),
            "trigger_reason": trigger_reason
        }, exc_info=True)

        # 返回兜底响应
        fallback_result = ExpertConsultResult(
            response="抱歉，系统当前无法处理您的咨询。请稍后重试或联系现场技术支持。",
            source="emergency_expert_system",
            trigger_reason=trigger_reason,
            confidence=confidence
        )

        return state | {"expert_consult": fallback_result.model_dump()}
