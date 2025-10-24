from __future__ import annotations

from typing import Optional

from openai import OpenAI
from langchain_openai import ChatOpenAI

from emergency_agents.config import AppConfig


def get_openai_client(config: Optional[AppConfig] = None) -> OpenAI:
    cfg = config or AppConfig.load_from_env()
    return OpenAI(base_url=cfg.openai_base_url, api_key=cfg.openai_api_key)


def get_chat_llm(config: Optional[AppConfig] = None) -> ChatOpenAI:
    cfg = config or AppConfig.load_from_env()
    return ChatOpenAI(
        model=cfg.llm_model,
        openai_api_base=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        temperature=0.2,
    )
