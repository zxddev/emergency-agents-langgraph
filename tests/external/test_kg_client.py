from __future__ import annotations

import json

import httpx
import pytest

from emergency_agents.external.kg_client import KGClient, KGClientConfig


def _build_client(transport: httpx.BaseTransport) -> KGClient:
    http_client = httpx.Client(transport=transport, base_url="http://kg.test")
    return KGClient(KGClientConfig(base_url="http://kg.test"), client=http_client)


def test_get_equipment_requirements_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/kg/equipment/requirements"
        payload = json.loads(request.content.decode())
        assert payload == {"disasters": ["earthquake"]}
        return httpx.Response(200, json=[{"equipment_name": "life_detector"}])

    client = _build_client(httpx.MockTransport(handler))
    try:
        result = client.get_equipment_requirements(disaster_types=["earthquake"])
        assert result == [{"equipment_name": "life_detector"}]
    finally:
        client.close()


def test_get_equipment_requirements_invalid_shape() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    client = _build_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError):
            client.get_equipment_requirements(disaster_types=["flood"])
    finally:
        client.close()
