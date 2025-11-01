from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Union


@dataclass(slots=True)
class CameraFlyToPayload:
    lng: float
    lat: float
    zoom: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        payload: Dict[str, float] = {"lng": float(self.lng), "lat": float(self.lat)}
        if self.zoom is not None:
            payload["zoom"] = float(self.zoom)
        return payload


@dataclass(slots=True)
class ToggleLayerPayload:
    layer_code: str
    layer_name: Optional[str]
    on: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layerCode": self.layer_code,
            "layer_name": self.layer_name,
            "on": bool(self.on),
        }


@dataclass(slots=True)
class UIAction:
    action: str
    payload: Any
    metadata: Optional[Mapping[str, Any]] = None


UIActionLike = Union[UIAction, Mapping[str, Any]]


def camera_fly_to(
    lng: float,
    lat: float,
    zoom: Optional[float] = None,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
) -> UIAction:
    return UIAction("camera_flyto", CameraFlyToPayload(lng=lng, lat=lat, zoom=zoom), metadata)


def toggle_layer(
    layer_code: str,
    *,
    layer_name: Optional[str],
    on: bool,
    metadata: Optional[Mapping[str, Any]] = None,
) -> UIAction:
    return UIAction(
        "toggle_layer",
        ToggleLayerPayload(layer_code=layer_code, layer_name=layer_name, on=on),
        metadata,
    )


@dataclass(slots=True)
class PanelPayload:
    panel: str
    params: Optional[Mapping[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"panel": self.panel}
        if self.params:
            data["params"] = dict(self.params)
        return data


def open_panel(
    panel: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> UIAction:
    return UIAction(
        "open_panel",
        PanelPayload(panel=panel, params=params),
        metadata,
    )


@dataclass(slots=True)
class FocusEntityPayload:
    entity_id: str
    zoom: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"entityId": self.entity_id}
        if self.zoom is not None:
            payload["zoom"] = float(self.zoom)
        return payload


def focus_entity(
    entity_id: str,
    *,
    zoom: Optional[float] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> UIAction:
    return UIAction(
        "focus_entity",
        FocusEntityPayload(entity_id=entity_id, zoom=zoom),
        metadata,
    )


@dataclass(slots=True)
class ToastPayload:
    message: str
    level: str = "info"
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"message": self.message, "level": self.level}
        if self.duration_ms is not None:
            data["durationMs"] = int(self.duration_ms)
        return data


def show_toast(
    message: str,
    *,
    level: str = "info",
    duration_ms: Optional[int] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> UIAction:
    return UIAction(
        "show_toast",
        ToastPayload(message=message, level=level, duration_ms=duration_ms),
        metadata,
    )


@dataclass(slots=True)
class RiskWarningPayload:
    message: str
    level: str = "warning"
    related_resources: Optional[Sequence[str]] = None
    risk_zones: Optional[Sequence[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"message": self.message, "level": self.level}
        if self.related_resources:
            data["relatedResources"] = list(self.related_resources)
        if self.risk_zones:
            data["riskZones"] = list(self.risk_zones)
        return data


def show_risk_warning(
    message: str,
    *,
    related_resources: Optional[Sequence[str]] = None,
    risk_zones: Optional[Sequence[str]] = None,
    level: str = "warning",
    metadata: Optional[Mapping[str, Any]] = None,
) -> UIAction:
    return UIAction(
        "show_risk_warning",
        RiskWarningPayload(
            message=message,
            level=level,
            related_resources=related_resources,
            risk_zones=risk_zones,
        ),
        metadata,
    )


def raw_action(
    action: str,
    payload: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> UIAction:
    return UIAction(action, dict(payload or {}), dict(metadata or {}))


def serialize_action(action: UIActionLike) -> Dict[str, Any]:
    if isinstance(action, UIAction):
        payload = _serialize_payload(action.payload)
        data: Dict[str, Any] = {"action": action.action, "payload": payload}
        if action.metadata:
            data.update(dict(action.metadata))
        return data
    data = dict(action)
    mapped_payload = data.get("payload") or {}
    data["payload"] = dict(mapped_payload)
    data["action"] = str(data.get("action"))
    return data


def serialize_actions(actions: Iterable[UIActionLike]) -> List[Dict[str, Any]]:
    return [serialize_action(action) for action in actions]


def _serialize_payload(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "to_dict"):
        result = payload.to_dict()  # type: ignore[no-any-return]
        if not isinstance(result, MutableMapping):
            raise TypeError("payload.to_dict() 必须返回 dict")
        return dict(result)
    if isinstance(payload, Mapping):
        return dict(payload)
    raise TypeError(f"不支持的 UI payload 类型: {type(payload)!r}")
