from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, TypedDict

import httpx

logger = logging.getLogger(__name__)

RouteMode = Literal["driving", "walking"]


class AmapError(RuntimeError):
    """高德地图 API 调用失败。"""

    def __init__(self, message: str, *, info: str | None = None) -> None:
        super().__init__(message)
        self.info = info


class Coordinate(TypedDict):
    lng: float
    lat: float


class RouteStep(TypedDict, total=False):
    instruction: str
    distance_meters: int
    duration_seconds: int
    polyline: str


class RoutePlan(TypedDict, total=False):
    distance_meters: int
    duration_seconds: int
    steps: list[RouteStep]
    cache_hit: bool


class GeocodeResult(TypedDict):
    name: str
    location: Coordinate
    level: str | None


@dataclass(slots=True)
class _CacheEntry:
    value: RoutePlan
    expires_at: float


class AmapClient:
    """高德地图 Web 服务客户端，包含简易缓存与备份 key 切换。"""

    def __init__(
        self,
        *,
        api_key: str,
        backup_key: str | None,
        base_url: str,
        connect_timeout: float = 10.0,
        read_timeout: float = 10.0,
        cache_ttl: float = 300.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._backup_key = backup_key
        self._cache_ttl = cache_ttl
        self._owns_client = http_client is None
        timeout = httpx.Timeout(
            timeout=max(connect_timeout, read_timeout),
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout,
        )
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            trust_env=False,
        )
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_lock = asyncio.Lock()
        self._rate_lock = asyncio.Semaphore(5)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def geocode(self, place: str) -> GeocodeResult | None:
        """地名解析，返回第一个匹配坐标。"""
        params = {"address": place, "key": self._api_key}
        data = await self._request("/v3/geocode/geo", params)
        geocodes = data.get("geocodes") or []
        if not geocodes:
            return None
        first = geocodes[0]
        location = first.get("location", "")
        if not location:
            return None
        lng_str, lat_str = location.split(",")
        return {
            "name": first.get("formatted_address", place),
            "location": {"lng": float(lng_str), "lat": float(lat_str)},
            "level": first.get("level"),
        }

    async def direction(
        self,
        *,
        origin: Coordinate,
        destination: Coordinate,
        mode: RouteMode,
        cache_key: str | None = None,
    ) -> RoutePlan:
        """路径规划，使用缓存避免重复调用。"""
        computed_key = cache_key or self._build_cache_key(origin, destination, mode)
        cached = await self._get_cached(computed_key)
        if cached is not None:
            logger.info("amap_cache_hit", extra={"cache_key": computed_key})
            cached_plan = dict(cached)
            cached_plan["cache_hit"] = True
            return cached_plan  # type: ignore[return-value]

        params = {
            "origin": f"{origin['lng']},{origin['lat']}",
            "destination": f"{destination['lng']},{destination['lat']}",
            "key": self._api_key,
        }
        endpoint = "/v3/direction/driving" if mode == "driving" else "/v3/direction/walking"
        data = await self._request(endpoint, params)
        path_info = (data.get("route") or {}).get("paths")
        if not path_info:
            raise AmapError("no route returned", info=data.get("info"))

        first_path = path_info[0]
        route = RoutePlan(
            distance_meters=int(first_path.get("distance", 0)),
            duration_seconds=int(first_path.get("duration", 0)),
            steps=[],
        )
        steps = first_path.get("steps") or []
        for step in steps:
            route["steps"].append(
                RouteStep(
                    instruction=step.get("instruction", ""),
                    distance_meters=int(step.get("distance", 0)),
                    duration_seconds=int(step.get("duration", 0)),
                    polyline=step.get("polyline", ""),
                )
            )

        route["cache_hit"] = False
        await self._set_cache(computed_key, route)
        return route

    async def _request(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with self._rate_lock:
            response = await self._client.get(path, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AmapError("http error", info=str(exc)) from exc
        data = response.json()
        if data.get("status") == "1":
            return data
        if self._backup_key and params.get("key") == self._api_key:
            logger.warning("amap_primary_key_failed", extra={"info": data.get("info")})
            params = dict(params)
            params["key"] = self._backup_key
            return await self._request(path, params)
        raise AmapError("amap api error", info=str(data.get("info")))

    async def _get_cached(self, key: str) -> RoutePlan | None:
        async with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                self._cache.pop(key, None)
                return None
            cached = dict(entry.value)
            return cached  # type: ignore[return-value]

    async def _set_cache(self, key: str, value: RoutePlan) -> None:
        async with self._cache_lock:
            to_store = dict(value)
            to_store.pop("cache_hit", None)
            self._cache[key] = _CacheEntry(value=to_store, expires_at=time.monotonic() + self._cache_ttl)  # type: ignore[arg-type]

    @staticmethod
    def _build_cache_key(origin: Coordinate, destination: Coordinate, mode: RouteMode) -> str:
        return f"{origin['lng']:.6f},{origin['lat']:.6f}->{destination['lng']:.6f},{destination['lat']:.6f}-{mode}"
