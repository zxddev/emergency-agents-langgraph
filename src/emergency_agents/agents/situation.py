# Copyright 2025 msq
from __future__ import annotations

import json
import logging
from typing import Dict, Any

from emergency_agents.agents.base import LLMAgentNode
from emergency_agents.agents.schemas import Situation
from emergency_agents.agents.memory_commit import prepare_memory_node

logger = logging.getLogger(__name__)

# 定义态势感知节点的 Prompt
SITUATION_PROMPT = """从以下灾情报告中提取结构化信息：

{raw_report}

请提取关键信息如灾害类型、震级、震中、时间、受灾区域、附近设施及伤亡估算。
"""

class SituationAgentNode(LLMAgentNode[Situation]):
    """态势感知智能体 (Refactored)"""

    def __init__(self):
        super().__init__(
            name="situation",
            output_schema=Situation,
            prompt_template=SITUATION_PROMPT,
            state_key="situation"
        )

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 执行标准 LLM 逻辑
        # 注意：LLMAgentNode 默认处理了 state["raw_report"] 到 {raw_report} 的映射
        # 如果 state 中没有 raw_report，需要提前检查或处理
        if not state.get("raw_report"):
             return state | {"situation": {"error": "无输入报告"}}

        new_state = await super().run(state)
        
        # 2. 执行自定义的 Memory & Audit 逻辑 (保留原有业务逻辑)
        # 注意：基类已经做了基础日志和 Timeline，这里补充 Memory 和 Audit
        
        situation_data = new_state.get("situation")
        if not situation_data or new_state.get("last_error"):
            return new_state

        # 审计日志
        from emergency_agents.audit.logger import log_ai_decision
        log_ai_decision(
            rescue_id=state.get("rescue_id", "unknown"),
            user_id=state.get("user_id", "unknown"),
            agent_name="situation_agent",
            decision_type="situation_analysis",
            decision_data={"situation": situation_data}
        )

        # Memory 两阶段提交
        # 注意：situation_data 在这里是 dict (因为基类做了 model_dump)
        content = json.dumps({"kind": "situation", "data": situation_data}, ensure_ascii=False)
        final_state = prepare_memory_node(
            new_state,
            content=content,
            metadata={"agent": "situation", "step": "001"},
        )
        
        return final_state

# 导出单例或函数适配器以兼容旧 Graph 定义
_agent_instance = SituationAgentNode()

async def situation_agent(state: Dict[str, Any], llm_client: Any = None, llm_model: str = None) -> Dict[str, Any]:
    """
    兼容旧签名的适配器函数。
    注意：llm_client 和 llm_model 参数将被忽略，转而使用 Container 中的配置。
    """
    return await _agent_instance.run(state)
