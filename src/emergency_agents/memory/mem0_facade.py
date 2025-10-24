# Copyright 2025 msq
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mem0 import Memory


@dataclass(frozen=True)
class Mem0Config:
    """Mem0 配置。

    Args:
        qdrant_url: Qdrant 服务地址。
        qdrant_collection: Qdrant 集合名称。
        embedding_model: 嵌入模型名称（需与 RAG 一致）。
        embedding_dim: 嵌入维度（需与 RAG 一致）。
        neo4j_uri: Neo4j bolt 地址。
        neo4j_user: Neo4j 用户名。
        neo4j_password: Neo4j 密码。
        openai_base_url: OpenAI 兼容 API 基址（可指向 vLLM）。
        openai_api_key: LLM API Key。
        graph_llm_model: 图记忆的专用模型，可选。
    """
    qdrant_url: str
    qdrant_collection: str
    embedding_model: str
    embedding_dim: int
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    openai_base_url: str
    openai_api_key: str
    graph_llm_model: Optional[str] = None


class MemoryFacade:
    """Mem0 内嵌封装，统一 add/search 契约并强制多租户与审计。"""

    def __init__(self, cfg: Mem0Config) -> None:
        self._cfg = cfg
        vector_store = {
            "provider": "qdrant",
            "config": {
                "url": cfg.qdrant_url,
                "collection_name": cfg.qdrant_collection,
                "embedding_model_dims": cfg.embedding_dim,
            },
        }
        graph_store = {
            "provider": "neo4j",
            "config": {
                "url": cfg.neo4j_uri,
                "username": cfg.neo4j_user,
                # pragma: allowlist secret - placeholder credential for development
                "password": cfg.neo4j_password,
            },
        }
        llm = {
            "provider": "openai",
            "config": {
                "model": cfg.graph_llm_model or os.getenv("LLM_MODEL", "glm-4-flash"),
                "openai_base_url": cfg.openai_base_url,
                # pragma: allowlist secret - placeholder credential for development
                "api_key": cfg.openai_api_key,
            },
        }
        embedder = {
            "provider": "openai",
            "config": {
                "model": cfg.embedding_model,
                # pragma: allowlist secret - placeholder credential for development
                "api_key": cfg.openai_api_key,
                "openai_base_url": cfg.openai_base_url,
            },
        }
        self._mem = Memory.from_config(
            config_dict={
                "vector_store": vector_store,
                "graph_store": graph_store,
                "llm": llm,
                "embedder": embedder,
            }
        )

    def add(
        self,
        *,
        content: str,
        user_id: str,
        run_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        actor: str = "ai_agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
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

        meta = dict(metadata or {})
        if run_id:
            meta["run_id"] = run_id
        if agent_id:
            meta["agent"] = agent_id
        meta["actor"] = actor
        meta["ts"] = int(time.time())
        meta["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()

        self._mem.add(content, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=meta)

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

        return self._mem.search(query, user_id=user_id, agent_id=agent_id, run_id=run_id, limit=top_k)


