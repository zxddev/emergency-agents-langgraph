from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_async_openai_client


logger = structlog.get_logger(__name__)


class IntentHandler:
    """意图理解与回复生成（使用现有 OpenAI 客户端）。"""

    def __init__(self, config: AppConfig | None = None, client: AsyncOpenAI | None = None) -> None:
        self._config = config or AppConfig.load_from_env()
        self.client = client or get_async_openai_client(self._config)

    async def understand_and_respond(self, user_text: str) -> tuple[str, str]:
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
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("llm_chat_failed", error=str(e))
            return f"收到您的消息：{user_text}"
