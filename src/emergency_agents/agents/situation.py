# Copyright 2025 msq
from __future__ import annotations

import json
import re
import logging
from typing import Dict, Any

from langgraph.func import task

from emergency_agents.agents.memory_commit import prepare_memory_node
from emergency_agents.utils.merge import deep_merge_non_null, append_timeline
from emergency_agents.llm.client import LLMClientProtocol

logger = logging.getLogger(__name__)


def safe_json_parse(text: str) -> Dict[str, Any]:
    """安全的JSON解析，带容错和重试

    尝试多种方式解析LLM输出的JSON:
    1. 直接解析
    2. 提取代码块中的JSON
    3. 提取{}之间的内容
    4. 失败时返回默认值

    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 97-128
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"JSON解析失败: {text[:200]}...")
    return {
        "disaster_type": "unknown",
        "magnitude": 0.0,
        "epicenter": {"lat": 0.0, "lng": 0.0},
        "parse_error": True
    }


@task
def _call_llm_for_situation(raw_report: str, llm_client: LLMClientProtocol, llm_model: str) -> Dict[str, Any]:
    """隔离LLM调用副作用，支持Durable Execution

    使用@task装饰器确保：
    1. workflow恢复时不重复调用（成本节省）
    2. 结果自动持久化到checkpoint
    3. 支持长时间中断恢复

    Args:
        raw_report: 非结构化灾情报告文本
        llm_client: OpenAI兼容的LLM客户端
        llm_model: 模型名称（如glm-4-flash）

    Returns:
        结构化的态势分析结果（JSON dict）

    Reference: LangGraph Durable Execution概念
    """
    prompt = f"""从以下灾情报告中提取结构化信息：

{raw_report}

请以JSON格式返回：
{{
  "disaster_type": "earthquake/flood/fire/chemical_leak/landslide",
  "magnitude": 7.8,
  "epicenter": {{"lat": 31.0, "lng": 103.4}},
  "depth_km": 14,
  "time": "2025-01-15T14:28:00Z",
  "affected_area": "汶川县",
  "nearby_facilities": ["水库", "化工厂"],
  "initial_casualties": {{"estimated": 1000, "confirmed": 100}}
}}

只返回JSON，不要有任何其他文字。如果某些信息缺失，使用null或空数组。"""

    response = llm_client.chat.completions.create(
        model=llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    llm_output = response.choices[0].message.content
    return safe_json_parse(llm_output)


def situation_agent(state: Dict[str, Any], llm_client: LLMClientProtocol, llm_model: str = "glm-4") -> Dict[str, Any]:
    """态势感知智能体

    从非结构化报告提取结构化信息

    输入: state["raw_report"] - 非结构化文本报告
    输出: state["situation"] - 结构化JSON数据

    幂等性: 如果situation已存在，直接返回（避免重复LLM调用）

    Reference: docs/行动计划/ACTION-PLAN-DAY1.md lines 131-183
    """
    if "situation" in state and state["situation"]:
        logger.info("态势感知结果已存在，跳过LLM调用（幂等性）")
        return state

    raw_report = state.get("raw_report", "")

    if not raw_report:
        return state | {"situation": {"error": "无输入报告"}}

    try:
        # 使用@task包装的LLM调用（支持Durable Execution）
        result_task = _call_llm_for_situation(raw_report, llm_client, llm_model)
        # 获取结果：首次执行时调用LLM，恢复时直接从checkpoint读取
        structured = result_task.result()
        
        logger.info(f"态势感知成功: {structured.get('disaster_type')}, magnitude={structured.get('magnitude')}")
        
        from emergency_agents.audit.logger import log_ai_decision
        log_ai_decision(
            rescue_id=state.get("rescue_id", "unknown"),
            user_id=state.get("user_id", "unknown"),
            agent_name="situation_agent",
            decision_type="situation_analysis",
            decision_data={"situation": structured}
        )

        # 合并：若已有部分态势，仅补齐/覆盖非空字段
        merged_situation = deep_merge_non_null(state.get("situation", {}), structured)

        # 时间轴记账
        state = append_timeline(state, "situation_updated", {"summary": merged_situation.get("disaster_type")})

        # 两阶段提交：准备阶段将关键信息写入 pending_memories
        content = json.dumps({"kind": "situation", "data": merged_situation}, ensure_ascii=False)
        state = prepare_memory_node(
            state,
            content=content,
            metadata={"agent": "situation", "step": "001"},
        )

        return state | {"situation": merged_situation}
        
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return state | {
            "situation": {"error": str(e)},
            "last_error": {"agent": "situation", "error": str(e)}
        }
