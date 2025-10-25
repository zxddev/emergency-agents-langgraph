from __future__ import annotations

from typing import Optional

import httpx
from openai import AsyncOpenAI, OpenAI
from langchain_openai import ChatOpenAI

from emergency_agents.config import AppConfig


def get_openai_client(config: Optional[AppConfig] = None) -> OpenAI:
    cfg = config or AppConfig.load_from_env()
    # 禁用环境代理读取，避免 httpx 因 SOCKS 代理缺少依赖而失败
    http_client = httpx.Client(trust_env=False)
    return OpenAI(base_url=cfg.openai_base_url, api_key=cfg.openai_api_key, http_client=http_client)


def get_async_openai_client(config: Optional[AppConfig] = None) -> AsyncOpenAI:
    cfg = config or AppConfig.load_from_env()
    http_client = httpx.AsyncClient(trust_env=False)
    return AsyncOpenAI(base_url=cfg.openai_base_url, api_key=cfg.openai_api_key, http_client=http_client)


def get_chat_llm(config: Optional[AppConfig] = None) -> ChatOpenAI:
    cfg = config or AppConfig.load_from_env()
    return ChatOpenAI(
        model=cfg.llm_model,
        openai_api_base=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        temperature=0.2,
    )
