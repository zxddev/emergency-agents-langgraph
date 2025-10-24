# Copyright 2025 msq
from __future__ import annotations

from typing import Dict, Any, List, Tuple


def interpolate_line(start_lng: float, start_lat: float, end_lng: float, end_lat: float, steps: int = 20) -> List[Tuple[float, float]]:
    """两点间等距插值。"""
    if steps <= 1:
        return [(start_lng, start_lat), (end_lng, end_lat)]
    coords: List[Tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        lng = start_lng + (end_lng - start_lng) * t
        lat = start_lat + (end_lat - start_lat) * t
        coords.append((lng, lat))
    return coords


def build_track_feature(fleet: Dict[str, Any], target_lng: float, target_lat: float, alt_m: int = 80, steps: int = 20) -> Dict[str, Any]:
    """构造UAV轨迹GeoJSON Feature。"""
    coords = interpolate_line(float(fleet.get("lng", 103.80)), float(fleet.get("lat", 31.66)), target_lng, target_lat, steps)
    return {
        "type": "LineString",
        "coordinates": [[lng, lat] for (lng, lat) in coords],
        "properties": {"alt_m": alt_m, "steps": steps},
    }


