# Copyright 2025 msq
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

import httpx
from qdrant_client import QdrantClient
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core import Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.openai import OpenAIEmbedding
from prometheus_client import Counter, Histogram

# 全局注册一次 Prometheus 指标，避免多实例重复注册
_RAG_IDX_COUNTER = Counter('rag_index_total', 'RAG index requests', ['domain'])
_RAG_QRY_COUNTER = Counter('rag_query_total', 'RAG query requests', ['domain'])
_RAG_QRY_LATENCY = Histogram('rag_query_seconds', 'RAG query latency seconds', ['domain'])


@dataclass
class RagChunk:
    """检索到的可引用片段。"""
    text: str
    source: str  # 文档ID或路径
    loc: str     # 页码/段落


class RagPipeline:
    """基于 LlamaIndex 与 Qdrant 的最小 RAG 外观。

    仅承担向量化索引与相似度检索，返回可引用的文本片段。LLM 设置使用
    OpenAI 兼容接口，确保与全局配置一致，不进行兜底降级。
    """

    def __init__(self, *, qdrant_url: str, qdrant_api_key: str | None, embedding_model: str, embedding_dim: int, openai_base_url: str, openai_api_key: str, llm_model: str) -> None:
        """初始化管道。

        Args:
            qdrant_url: Qdrant 服务地址。
            qdrant_api_key: Qdrant API Key（可选，本地部署无需认证可传None）。
            embedding_model: 嵌入模型名称。
            embedding_dim: 嵌入维度，必须与集合一致。
            openai_base_url: OpenAI 兼容 API 基址。
            openai_api_key: API Key。
            llm_model: LLM 模型名，用于 LlamaIndex 内部能力。
        """
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.openai_base_url = openai_base_url
        self.openai_api_key = openai_api_key

        # 创建自定义 HTTP 客户端，禁用系统代理环境变量，并设置有界超时
        timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
        custom_http_client = httpx.Client(trust_env=False, timeout=timeout)

        # 明确指定 LLM 与嵌入模型，不依赖环境兜底
        Settings.llm = OpenAILike(
            model=llm_model,
            api_key=self.openai_api_key,
            api_base=self.openai_base_url,
            context_window=128000,
            is_chat_model=True,
            is_function_calling_model=False,
            http_client=custom_http_client,  # 使用自定义客户端
        )
        Settings.embed_model = OpenAIEmbedding(
            model_name=self.embedding_model,
            api_key=self.openai_api_key,
            api_base=self.openai_base_url,
            http_client=custom_http_client,  # 使用自定义客户端
            embed_batch_size=32,  # 智谱GLM API限制：最大64条，设置32保守处理
        )

        # metrics（指向模块级单例指标）
        self._idx_counter = _RAG_IDX_COUNTER
        self._qry_counter = _RAG_QRY_COUNTER
        self._qry_latency = _RAG_QRY_LATENCY

    def _vector_store(self, collection: str) -> QdrantVectorStore:
        """构造 Qdrant 向量存储实例。"""
        client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        return QdrantVectorStore(client=client, collection_name=collection)

    def index_documents(self, domain: str, docs: List[Dict[str, Any]]) -> None:
        """索引一批文档。

        Args:
            domain: 域（规范/案例/地理/装备）。
            docs: 文档列表，元素需包含 {"id": str, "text": str, "meta": dict}。

        Raises:
            ValueError: 当已存在的集合维度与配置不一致。
        """
        collection = f"rag_{domain}"
        vector_store = self._vector_store(collection)
        storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
        li_docs = [Document(text=d["text"], id_=d.get("id"), metadata=d.get("meta", {})) for d in docs]

        # 强校验：已存在集合的维度必须一致，否则直接失败
        try:
            client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
            info = client.get_collection(collection)
            actual = info.config.params.vectors.size  # type: ignore[attr-defined]
            if int(actual) != int(self.embedding_dim):
                raise ValueError(f"Qdrant collection '{collection}' dim={actual} != EMBEDDING_DIM={self.embedding_dim}")
        except Exception:
            # 集合不存在时由 VectorStore 创建，随后维度即为配置值
            pass

        VectorStoreIndex.from_documents(li_docs, storage_context=storage_ctx)
        self._idx_counter.labels(domain=domain).inc()

    def query(self, question: str, domain: str, top_k: int = 3) -> List[RagChunk]:
        """查询返回可引用片段。

        Args:
            question: 查询问题。
            domain: 域（规范/案例/地理/装备）。
            top_k: 返回片段数量。

        Returns:
            可引用片段列表（文本+来源+位置）。
        """
        collection = f"rag_{domain}"
        vector_store = self._vector_store(collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        engine = index.as_query_engine(similarity_top_k=top_k)
        with self._qry_latency.labels(domain=domain).time():
            resp = engine.query(question)
        chunks: List[RagChunk] = []
        for node in getattr(resp, "source_nodes", []) or []:
            meta = node.node.metadata or {}
            source = meta.get("id") or meta.get("source") or "unknown"
            loc = meta.get("loc") or meta.get("page") or ""
            chunks.append(RagChunk(text=node.node.get_content(), source=source, loc=str(loc)))
        self._qry_counter.labels(domain=domain).inc()
        return chunks
