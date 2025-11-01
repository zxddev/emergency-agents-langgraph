from __future__ import annotations

import json

import httpx
import pytest

from emergency_agents.external.rag_client import RagClient, RagClientConfig


def _build_client(transport: httpx.BaseTransport) -> RagClient:
    http_client = httpx.Client(transport=transport, base_url="http://rag.test")
    return RagClient(RagClientConfig(base_url="http://rag.test"), client=http_client)


def test_rag_search_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rag/search"
        payload = json.loads(request.content.decode())
        assert payload == {"query": "案例", "top_k": 3}
        return httpx.Response(200, json=[{"text": "案例1"}])

    client = _build_client(httpx.MockTransport(handler))
    try:
        result = client.search(query="案例", top_k=3)
        assert result == [{"text": "案例1"}]
    finally:
        client.close()


def test_rag_search_invalid_shape() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": True})

    client = _build_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError):
            client.search(query="案例", top_k=1)
    finally:
        client.close()
