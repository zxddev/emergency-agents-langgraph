# Copyright 2025 msq
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional, Type, TypeVar, Generic

from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable
from langchain_core.messages import SystemMessage, HumanMessage

from emergency_agents.container import container
from emergency_agents.utils.merge import deep_merge_non_null, append_timeline

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMAgentNode(Generic[T]):
    """标准化的 LLM 智能体节点 (LangChain 1.0 Style)。

    封装了：
    1. 幂等性检查 (Idempotency)
    2. Prompt 渲染 (LCEL)
    3. 结构化输出 (with_structured_output)
    4. 状态更新与日志 (State Update & Logging)
    """

    def __init__(
        self,
        name: str,
        output_schema: Type[T],
        prompt_template: str,
        system_prompt: str = "你是专业的应急救援专家。",
        state_key: str = "result",
        llm_model: Optional[str] = None,
    ):
        self.name = name
        self.output_schema = output_schema
        self.prompt_template = prompt_template
        self.system_prompt = system_prompt
        self.state_key = state_key
        # 如果未指定模型，尝试从容器配置获取，否则用默认
        self.llm_model = llm_model 

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑。"""
        
        # 1. 幂等性检查
        existing = state.get(self.state_key)
        if existing and not isinstance(existing, dict): 
            # 简单的非空检查，实际业务可能需要更复杂的判断
            logger.info(f"[{self.name}] 结果已存在，跳过执行 (Idempotency)")
            return state

        # 2. 准备 LLM (从容器获取)
        try:
            # 这里假设容器里注册的是 ChatOpenAI 实例
            # 如果需要针对特定 Agent 换模型，可以在这里 clone 并修改 model_name
            base_llm = container.llm_client
            if self.llm_model:
                llm = base_llm.bind(model=self.llm_model) # 或者配置一个新的
            else:
                llm = base_llm
        except Exception as e:
            logger.error(f"[{self.name}] 无法获取 LLM 服务: {e}")
            return state | {"last_error": {"agent": self.name, "error": "LLM service unavailable"}}

        # 3. 构建 Chain (LCEL)
        # 使用 with_structured_output 替代手动解析
        structured_llm = llm.with_structured_output(self.output_schema)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", self.prompt_template),
        ])
        
        chain = prompt | structured_llm

        # 4. 执行
        try:
            # state 直接作为参数传入 prompt template
            # 确保 prompt_template 中的变量名与 state 中的 key 匹配
            result: T = await chain.ainvoke(state)
            
            # 5. 处理结果
            result_dict = result.model_dump()
            logger.info(f"[{self.name}] 执行成功: {result_dict.keys()}")
            
            # 6. 更新状态
            # 自动做一次 deep merge (可选，取决于业务)
            # 这里简单覆盖或合并
            current_val = state.get(self.state_key, {})
            merged_val = deep_merge_non_null(current_val, result_dict) if isinstance(current_val, dict) else result_dict
            
            new_state = state | {self.state_key: merged_val}
            
            # 7. 时间轴记录
            new_state = append_timeline(new_state, f"{self.name}_completed", {"summary": "Executed successfully"})
            
            return new_state

        except Exception as e:
            logger.error(f"[{self.name}] 执行失败: {e}", exc_info=True)
            return state | {"last_error": {"agent": self.name, "error": str(e)}}
