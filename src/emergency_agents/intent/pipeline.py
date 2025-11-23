# Copyright 2025 msq
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Literal, Optional

from emergency_agents.container import container
from emergency_agents.intent.classifier import intent_classifier_node
from emergency_agents.intent.validator import validate_and_prompt_node

logger = logging.getLogger(__name__)

class IntentPipeline:
    """线性的意图处理管道，替代原有的 IntentGraph。"""

    async def process(
        self,
        input_text: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行: 分类 -> 校验 -> (可选) 追问
        返回: 最终的 Intent 结果 (包含 router_next 指令)
        """
        context = context or {}
        state = {
            "raw_text": input_text,
            "thread_id": context.get("thread_id"),
            "user_id": context.get("user_id"),
            "incident_id": context.get("incident_id"),
            "intent": {},
            "missing_fields": [],
            "validation_status": "unknown",
            "history": context.get("history", []) # 传入历史记录辅助分类
        }

        # 1. Classify
        # 注意：这里我们直接复用旧的 node 函数，但传入 container 的 llm
        # 未来可以将 classifier_node 也重构为 LLMAgentNode
        state = intent_classifier_node(
            state, 
            llm_client=container.llm_client, 
            llm_model=container.config.llm_model
        )
        
        # 2. Validate
        state = validate_and_prompt_node(
            state,
            llm_client=container.llm_client,
            llm_model=container.config.llm_model,
        )

        # 对于线性管道，不再调用基于 LangGraph interrupt 的 prompt_missing_slots_node，
        # 仅返回校验结果和提示文案，由上层 process_intent_core 负责追问与会话交互。
        if state.get("validation_status") == "invalid":
            return {
                "status": "incomplete",
                "prompt": state.get("prompt"),
                "state": state,
            }
        
        # 4. Route (简单映射)
        router_next = self._route(state.get("intent", {}))
        
        return {
            "status": "complete",
            "intent": state.get("intent"),
            "router_next": router_next,
            "state": state
        }

    def _route(self, intent: Dict[str, Any]) -> str:
        intent_type = str(intent.get("intent_type") or "unknown").strip()
        normalized = intent_type.replace(" ", "").replace("_", "-").lower()
        
        # 简单的映射表 (Copied from intent_orchestrator_app.py)
        route_map = {
            "rescue-task-generate": "rescue-task-generate",
            "scout-task-simple": "scout-task-simple",
            "video-analysis": "video-analysis",
            "video-analyze": "video-analysis",
            "device-control-robotdog": "device_control_robotdog",
            "device_control_robotdog": "device_control_robotdog",
            "general-chat": "general-chat",
            # ... 其他映射 ...
        }
        # 默认 fallback
        return route_map.get(normalized, "general-chat")

# 单例导出
intent_pipeline = IntentPipeline()
