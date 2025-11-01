from __future__ import annotations

from typing import Any, Dict, List

import httpx
import pytest

from emergency_agents.external.amap_client import AmapClient, AmapError, Coordinate


def _mock_transport(responses: List[Dict[str, Any]]) -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        if not responses:
            raise AssertionError("unexpected request: no scripted response left")
        payload = responses.pop(0)
        status_code = payload.pop("_status", 200)
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_geocode_success() -> None:
    responses = [
        {"status": "1", "geocodes": [{"formatted_address": "映秀镇", "location": "103.850000,31.680000", "level": "town"}]},
    ]
    client = AmapClient(
        api_key="key",
        backup_key=None,
        base_url="https://mock.amap.com",
        http_client=httpx.AsyncClient(transport=_mock_transport(responses), base_url="https://mock.amap.com"),
    )
    result = await client.geocode("映秀镇")
    assert result is not None
    assert result["location"]["lng"] == pytest.approx(103.85)
    await client.close()


@pytest.mark.asyncio
async def test_direction_uses_cache() -> None:
    origin: Coordinate = {"lng": 103.85, "lat": 31.68}
    dest: Coordinate = {"lng": 103.90, "lat": 31.70}
    responses = [
        {
            "status": "1",
            "route": {
                "paths": [
                    {"distance": "1000", "duration": "600", "steps": [{"instruction": "直行", "distance": "1000", "duration": "600", "polyline": "103,31"}]},
                ]
            },
        }
    ]
    client = AmapClient(
        api_key="key",
        backup_key=None,
        base_url="https://mock.amap.com",
        http_client=httpx.AsyncClient(transport=_mock_transport(responses), base_url="https://mock.amap.com"),
    )
    plan1 = await client.direction(origin=origin, destination=dest, mode="driving")
    plan2 = await client.direction(origin=origin, destination=dest, mode="driving")
    assert plan1 == plan2
    await client.close()


@pytest.mark.asyncio
async def test_direction_uses_backup_key() -> None:
    origin: Coordinate = {"lng": 103.85, "lat": 31.68}
    dest: Coordinate = {"lng": 103.90, "lat": 31.70}
    responses = [
        {"status": "0", "info": "DAILY_QUERY_OVER_LIMIT"},
        {
            "status": "1",
            "route": {
                "paths": [
                    {"distance": "500", "duration": "300", "steps": []},
                ]
            },
        },
    ]
    transport = _mock_transport(responses)
    client = AmapClient(
        api_key="primary",
        backup_key="backup",
        base_url="https://mock.amap.com",
        http_client=httpx.AsyncClient(transport=transport, base_url="https://mock.amap.com"),
    )
    plan = await client.direction(origin=origin, destination=dest, mode="walking")
    assert plan["distance_meters"] == 500
    await client.close()


@pytest.mark.asyncio
async def test_direction_error_without_backup() -> None:
    origin: Coordinate = {"lng": 103.85, "lat": 31.68}
    dest: Coordinate = {"lng": 103.90, "lat": 31.70}
    responses = [{"status": "0", "info": "INVALID_KEY"}]
    client = AmapClient(
        api_key="key",
        backup_key=None,
        base_url="https://mock.amap.com",
        http_client=httpx.AsyncClient(transport=_mock_transport(responses), base_url="https://mock.amap.com"),
    )
    with pytest.raises(AmapError):
        await client.direction(origin=origin, destination=dest, mode="driving")
    await client.close()
