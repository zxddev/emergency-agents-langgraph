from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KGClientConfig:
    base_url: str
    timeout: float = 10.0
    api_key: str | None = None


class KGClient:
    """知识图谱 HTTP 客户端（同步）。"""

    def __init__(self, config: KGClientConfig, client: httpx.Client | None = None) -> None:
        timeout = httpx.Timeout(config.timeout, connect=config.timeout)
        headers: dict[str, str] = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=config.base_url.rstrip("/"), timeout=timeout, headers=headers)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_equipment_requirements(self, *, disaster_types: List[str]) -> List[Dict[str, Any]]:
        response = self._client.post("/kg/equipment/requirements", json={"disasters": disaster_types})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("KG equipment requirements must be a list")
        return data

    def predict_secondary_disasters(self, *, primary_disaster: str, magnitude: float = 0.0) -> List[Dict[str, Any]]:
        payload = {"primary_disaster": primary_disaster, "magnitude": magnitude}
        response = self._client.post("/kg/disasters/secondary", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("KG secondary disasters response must be a list")
        return data

    def get_compound_risks(self, *, disaster_ids: List[str]) -> List[Dict[str, Any]]:
        response = self._client.post("/kg/disasters/compound", json={"disasters": disaster_ids})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("KG compound risks response must be a list")
        return data

    def recommend_forces(self, *, scenario: Dict[str, Any]) -> Dict[str, Any]:
        response = self._client.post("/kg/forces/recommend", json=scenario)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("KG forces response must be an object")
        return data
