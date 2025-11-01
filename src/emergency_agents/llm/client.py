from __future__ import annotations

from typing import Optional, Protocol

from openai import AsyncOpenAI, OpenAI
from langchain_openai import ChatOpenAI

from emergency_agents.config import AppConfig
from emergency_agents.llm.endpoint_manager import LLMEndpointConfig, LLMEndpointManager


class _ChatCompletionsProtocol(Protocol):
    def create(self, *args, **kwargs): ...


class _ChatNamespace(Protocol):
    completions: _ChatCompletionsProtocol


class LLMClientProtocol(Protocol):
    chat: _ChatNamespace


_MANAGER: LLMEndpointManager | None = None


def _get_manager(cfg: AppConfig) -> LLMEndpointManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = LLMEndpointManager.from_config(cfg)
    return _MANAGER


class _FailoverChatCompletions:
    """同步聊天完成封装：负责调用端点管理器。"""

    def __init__(self, manager: LLMEndpointManager) -> None:
        self._manager = manager

    def create(self, *args, **kwargs):
        # 中文注释：每次生成时都让管理器选择最优端点并执行请求。
        def caller(client: OpenAI, endpoint: LLMEndpointConfig):
            return client.chat.completions.create(*args, **kwargs)

        return self._manager.call_sync("chat_completion", caller)


class _FailoverChat:
    def __init__(self, manager: LLMEndpointManager) -> None:
        self.completions = _FailoverChatCompletions(manager)


class FailoverLLMClient:
    """同步LLM客户端封装，外部接口与OpenAI兼容。"""

    def __init__(self, manager: LLMEndpointManager) -> None:
        self.chat = _FailoverChat(manager)


class _AsyncFailoverChatCompletions:
    """异步聊天完成封装：适配语音等异步场景。"""

    def __init__(self, manager: LLMEndpointManager) -> None:
        self._manager = manager

    async def create(self, *args, **kwargs):
        async def caller(client: AsyncOpenAI, endpoint: LLMEndpointConfig):
            return await client.chat.completions.create(*args, **kwargs)

        return await self._manager.call_async("chat_completion", caller)


class _AsyncFailoverChat:
    def __init__(self, manager: LLMEndpointManager) -> None:
        self.completions = _AsyncFailoverChatCompletions(manager)


class FailoverAsyncLLMClient:
    def __init__(self, manager: LLMEndpointManager) -> None:
        self.chat = _AsyncFailoverChat(manager)


def get_openai_client(config: Optional[AppConfig] = None) -> LLMClientProtocol:
    cfg = config or AppConfig.load_from_env()
    manager = _get_manager(cfg)
    return FailoverLLMClient(manager)


def get_async_openai_client(config: Optional[AppConfig] = None) -> FailoverAsyncLLMClient:
    cfg = config or AppConfig.load_from_env()
    manager = _get_manager(cfg)
    return FailoverAsyncLLMClient(manager)


def get_chat_llm(config: Optional[AppConfig] = None) -> ChatOpenAI:
    """仍返回 LangChain ChatOpenAI，目前取第一个端点，后续可扩展为多端点策略。"""

    cfg = config or AppConfig.load_from_env()
    chosen = cfg.llm_endpoints[0] if cfg.llm_endpoints else None
    if chosen is None:
        # 回退到旧逻辑
        chosen = LLMEndpointConfig(
            name="primary",
            base_url=cfg.openai_base_url,
            api_key=cfg.openai_api_key,
            priority=100,
        )
    return ChatOpenAI(
        model=cfg.llm_model,
        openai_api_base=chosen.base_url,
        openai_api_key=chosen.api_key,
        temperature=0.2,
    )
