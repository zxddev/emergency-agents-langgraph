# Copyright 2025 msq
from __future__ import annotations

from typing import Any, Optional
import logging

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class ServiceContainer:
    """简单的服务容器，用于解耦 main.py 的依赖注入。"""

    _instance: Optional[ServiceContainer] = None
    
    def __init__(self):
        self._services: dict[str, Any] = {}
        self._config: Any = None

    @classmethod
    def get_instance(cls) -> ServiceContainer:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, service: Any) -> None:
        """注册服务实例。"""
        self._services[name] = service
        logger.info(f"Service registered: {name}")

    def get(self, name: str) -> Any:
        """获取服务实例。"""
        if name not in self._services:
            raise KeyError(f"Service not found: {name}")
        return self._services[name]

    def set_config(self, config: Any) -> None:
        self._config = config

    @property
    def config(self) -> Any:
        if self._config is None:
            raise RuntimeError("Config not initialized")
        return self._config

    @property
    def llm_client(self) -> BaseChatModel:
        """获取标准的 LangChain ChatModel 实例 (Lazy load preferred but simplified here)."""
        return self.get("llm_client")
    
    @property
    def db_pool(self) -> Any:
        return self.get("db_pool")

    @property
    def kg_service(self) -> Any:
        return self.get("kg_service")
        
    @property
    def rag_pipeline(self) -> Any:
        return self.get("rag_pipeline")

# 全局单例访问点
container = ServiceContainer.get_instance()
