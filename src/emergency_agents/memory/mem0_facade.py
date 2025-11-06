# Copyright 2025 msq
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass  # 引入数据类装饰器
import threading  # 引入线程同步工具
from typing import Any, Dict, List, Optional, Tuple  # 引入类型集合

import structlog  # 引入结构化日志库
from mem0 import Memory

logger = structlog.get_logger(__name__)  # 初始化模块级日志器


@dataclass(frozen=True)
class Mem0Config:
    """Mem0 配置。"""

    qdrant_url: str  # Qdrant 服务地址
    qdrant_api_key: Optional[str]  # Qdrant API密钥
    qdrant_collection: str  # Qdrant 集合名称
    embedding_model: str  # 嵌入模型名称
    embedding_dim: int  # 嵌入维度
    neo4j_uri: str  # Neo4j 地址
    neo4j_user: str  # Neo4j 用户名
    neo4j_password: str  # Neo4j 密码
    openai_base_url: str  # OpenAI 兼容 API 地址
    openai_api_key: str  # LLM 调用 Key
    graph_llm_model: Optional[str] = None  # 图记忆模型


class MemoryFacade:
    """Mem0 内嵌封装，统一 add/search 契约并强制多租户与审计。

    采用惰性初始化，首次使用时才建立 Mem0 实例，避免应用启动期外部连接。
    """

    def __init__(self, cfg: Mem0Config) -> None:
        self._cfg: Mem0Config = cfg  # 保存配置对象
        self._mem: Optional[Memory] = None  # 延迟初始化的 Mem0 实例
        self._lock: threading.Lock = threading.Lock()  # 写入熔断状态锁
        self._disabled_until: float = 0.0  # 熔断截止时间
        self._disabled_reason: str = ""  # 熔断原因
        self._max_retries: int = int(os.getenv("MEM0_MAX_RETRIES", "2"))  # 最大重试次数
        self._retry_backoff_base: float = float(os.getenv("MEM0_RETRY_BACKOFF_BASE", "0.5"))  # 退避基准
        self._rate_limit_cooldown: int = int(os.getenv("MEM0_RATE_LIMIT_COOLDOWN", "60"))  # 限流冷却秒数

        vector_store_config: Dict[str, Any] = {  # 构建向量存储配置
            "url": cfg.qdrant_url,  # Qdrant 地址
            "collection_name": cfg.qdrant_collection,  # 集合名称
            "embedding_model_dims": cfg.embedding_dim,  # 嵌入维度
        }
        if cfg.qdrant_api_key:  # 若存在 Qdrant Key
            vector_store_config["api_key"] = cfg.qdrant_api_key  # 写入认证信息

        self._config_dict: Dict[str, Any] = {  # 组合完整配置
            "vector_store": {
                "provider": "qdrant",  # 指定向量存储类型
                "config": vector_store_config,  # 注入配置
            },
            "graph_store": {
                "provider": "neo4j",  # 指定图存储类型
                "config": {
                    "url": cfg.neo4j_uri,  # Neo4j 地址
                    "username": cfg.neo4j_user,  # 用户名
                    # pragma: allowlist secret - placeholder credential for development
                    "password": cfg.neo4j_password,  # 密码
                },
            },
            "llm": {
                "provider": "openai",  # 指定 LLM 提供方
                "config": {
                    "model": cfg.graph_llm_model or os.getenv("LLM_MODEL", "glm-4-flash"),  # 选择模型
                    "openai_base_url": cfg.openai_base_url,  # LLM 接口地址
                    # pragma: allowlist secret - placeholder credential for development
                    "api_key": cfg.openai_api_key,  # LLM key
                },
            },
            "embedder": {
                "provider": "openai",  # 指定嵌入提供方
                "config": {
                    "model": cfg.embedding_model,  # 嵌入模型
                    # pragma: allowlist secret - placeholder credential for development
                    "api_key": cfg.openai_api_key,  # 嵌入 key
                    "openai_base_url": cfg.openai_base_url,  # 嵌入接口地址
                },
            },
        }

    def _ensure_mem(self) -> Memory:
        """首次访问时创建 Mem0 实例。"""
        if self._mem is None:
            self._mem = Memory.from_config(config_dict=self._config_dict)
        return self._mem

    def _classify_exception(self, exc: Exception) -> Tuple[str, str]:
        """根据异常内容判断类型。"""
        message: str = str(exc).lower()  # 转小写便于匹配
        if "429" in message or "rate limit" in message or "并发数过高" in message:
            return ("rate_limit", message)  # 返回限流类型
        if "timeout" in message or "timed out" in message:
            return ("timeout", message)  # 返回超时类型
        return ("fatal", message)  # 默认视为致命类型

    def add(
        self,
        *,
        content: str,
        user_id: str,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        actor: str = "ai_agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """写入记忆并入图。

        Args:
            content: 需要持久化的记忆内容。
            user_id: 租户标识，强制隔离维度。
            run_id: 会话标识（推荐，与 rescue_id 对齐）。
            agent_id: 责任主体元信息，不作为主键分区。
            actor: 写入发起者（用于审计）。
            metadata: 额外元信息，将合并写入。
        """
        if not user_id:
            raise ValueError("user_id is required for multi-tenant isolation")

        now: float = time.time()  # 当前时间戳
        with self._lock:  # 进入互斥锁
            if now < self._disabled_until:  # 判断是否处于熔断
                remaining: float = self._disabled_until - now  # 计算剩余时间
                logger.warning(
                    "mem0_write_skipped_due_to_cooldown",
                    remaining_seconds=int(remaining),
                    reason=self._disabled_reason,
                )
                return False  # 跳过写入

        meta = dict(metadata or {})
        if run_id:
            meta["run_id"] = run_id
        if agent_id:
            meta["agent"] = agent_id
        meta["actor"] = actor
        meta["ts"] = int(time.time())
        meta["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()

        mem = self._ensure_mem()
        attempt: int = 0  # 初始化尝试次数
        while attempt <= self._max_retries:
            attempt += 1  # 增加计数
            try:
                mem.add(content, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=meta)
                if attempt > 1:
                    logger.info("mem0_add_retry_success", attempt=attempt)
                return True  # 写入成功
            except Exception as exc:  # noqa: BLE001
                category, text = self._classify_exception(exc)  # 分类异常
                logger.warning(
                    "mem0_add_attempt_failed",
                    attempt=attempt,
                    category=category,
                    error=text,
                )
                if category == "rate_limit":
                    if attempt > self._max_retries:
                        with self._lock:
                            self._disabled_until = time.time() + self._rate_limit_cooldown
                            self._disabled_reason = "rate_limit"
                        logger.error(
                            "mem0_rate_limit_cooldown_activated",
                            cooldown_seconds=self._rate_limit_cooldown,
                        )
                        return False
                    time.sleep(self._retry_backoff_base * attempt)
                    continue
                if category == "timeout" and attempt <= self._max_retries:
                    time.sleep(self._retry_backoff_base * attempt)
                    continue
                raise

        return False  # 理论上不会到达

    def search(
        self,
        *,
        query: str,
        user_id: str,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """按多租户维度检索记忆。

        Args:
            query: 查询语句。
            user_id: 租户标识，强制过滤。
            run_id: 会话标识，可选。
            agent_id: 责任主体元信息，可选。
            top_k: 返回数量上限。

        Returns:
            Mem0 返回的检索结果列表；开启图记忆时包含实体/关系结构。
        """
        if not user_id:
            raise ValueError("user_id is required for multi-tenant isolation")

        mem = self._ensure_mem()
        return mem.search(query, user_id=user_id, agent_id=agent_id, run_id=run_id, limit=top_k)


class DisabledMemoryFacade:
    """Mem0 关闭时的占位实现，显式记录禁用原因。"""

    def __init__(self) -> None:
        logger.warning("mem0_disabled", reason="ENABLE_MEM0=false")

    def add(
        self,
        *,
        content: str,
        user_id: str,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        actor: str = "ai_agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        logger.info(
            "mem0_add_skipped_disabled",
            user_id=user_id,
            run_id=run_id,
        )
        return False

    def search(
        self,
        *,
        query: str,
        user_id: str,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        logger.info(
            "mem0_search_skipped_disabled",
            user_id=user_id,
            run_id=run_id,
            query_preview=query[:32],
        )
        return []
