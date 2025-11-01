from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagClientConfig:
    base_url: str
    timeout: float = 10.0
    api_key: str | None = None


class RagClient:
    """RAG 检索 HTTP 客户端（同步）。"""

    def __init__(self, config: RagClientConfig, client: httpx.Client | None = None) -> None:
        timeout = httpx.Timeout(config.timeout, connect=config.timeout)
        headers: dict[str, str] = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=config.base_url.rstrip("/"), timeout=timeout, headers=headers)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, *, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        response = self._client.post("/rag/search", json={"query": query, "top_k": top_k})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("RAG search response must be a list")
        return data
