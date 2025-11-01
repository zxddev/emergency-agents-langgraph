from __future__ import annotations

import warnings
import structlog

from emergency_agents.config import AppConfig
from emergency_agents.llm.client import FailoverAsyncLLMClient, get_async_openai_client


logger = structlog.get_logger(__name__)


# ============================================================================
# 🚨 DEPRECATED: 该模块已被intent_processor.py替代
# ============================================================================
# 本文件包含的简化意图处理逻辑已被统一的intent_processor.py取代。
#
# 原因:
# - 该模块仅支持5个关键词规则的简化意图分类
# - 缺少LLM驱动的意图分类器、槽位提取和验证机制
# - 无法支持完整的17种意图类型
#
# 新架构:
# - REST API和WebSocket语音对话现在共享相同的intent_processor.process_intent_core()
# - 提供完整的意图识别、槽位验证、处理器注册表功能
#
# 迁移路径:
# - voice_chat.py已迁移至intent_processor.process_intent_core()
# - 该文件将在下一版本中移除
#
# 参考文档:
# - temp/intent-system-comparison-critical-issue.md
# - src/emergency_agents/api/intent_processor.py
# ============================================================================


class IntentHandler:
    """意图理解与回复生成（使用现有 OpenAI 客户端）。

    ⚠️ DEPRECATED: 该类已被intent_processor.py中的统一处理逻辑取代。
    请使用 emergency_agents.api.intent_processor.process_intent_core() 代替。
    """

    def __init__(self, config: AppConfig | None = None, client: FailoverAsyncLLMClient | None = None) -> None:
        self._config = config or AppConfig.load_from_env()
        self.client = client or get_async_openai_client(self._config)

    async def understand_and_respond(self, user_text: str) -> tuple[str, str]:
        """理解用户意图并生成回复。

        ⚠️ DEPRECATED: 该方法已不再使用，voice_chat.py现在直接调用
        emergency_agents.api.intent_processor.process_intent_core()

        该方法仅提供5个关键词的简化分类，无法支持完整的意图识别系统。
        """
        warnings.warn(
            "IntentHandler.understand_and_respond() is deprecated. "
            "Use emergency_agents.api.intent_processor.process_intent_core() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        try:
            intent = self._classify_intent(user_text)
            if intent == "chat":
                reply = await self._chat_llm(user_text)
                return intent, reply
            # 其他意图先返回占位文本，后续逐步实现
            return intent, f"收到您的请求：{user_text}（该功能正在开发中）"
        except Exception as e:
            logger.error("intent_handling_failed", error=str(e))
            return "error", "抱歉，我遇到了一些问题，请稍后再试"

    def _classify_intent(self, text: str) -> str:
        if "救援" in text or "方案" in text:
            return "rescue_plan"
        if "侦察" in text:
            return "scout_plan"
        if "无人机" in text:
            return "drone_control"
        if "机器狗" in text:
            return "robot_control"
        return "chat"

    async def _chat_llm(self, user_text: str) -> str:
        try:
            # 使用官方 OpenAI Python SDK 的异步接口
            response = await self.client.chat.completions.create(
                model=self._config.llm_model,
                messages=[
                    {"role": "system", "content": "你是应急救援智能助手，请用简洁、专业中文回复。"},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=500,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            if not content or content.strip() == "":
                logger.warning("llm_returned_empty_content", user_text=user_text, model=self._config.llm_model)
                return "抱歉，我无法回答这个问题。请换一个话题试试。"
            return content
        except Exception as e:
            logger.error("llm_chat_failed", error=str(e))
            return f"收到您的消息：{user_text}"
