from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

import structlog

from emergency_agents.intent.handlers.base import IntentHandler
from emergency_agents.intent.schemas import (
    BaseSlots,
    UICameraFlytoSlots,
    UIToggleLayerSlots,
)
from emergency_agents.ui.actions import (
    UIAction,
    camera_fly_to,
    raw_action,
    serialize_actions,
    toggle_layer,
)


logger = structlog.get_logger(__name__)


class UIControlHandler(IntentHandler[BaseSlots]):
    """将 UI 意图槽位翻译为标准化 ui_actions（不做下发）。

    输出结构：
    {
      "ui_actions": [ {"action": str, "payload": dict} ... ],
      "response_text": str
    }
    """

    async def handle(self, slots: BaseSlots, state: Dict[str, Any]) -> Dict[str, Any]:
        ui_actions: List[UIAction] = []
        response_text = ""

        if isinstance(slots, UICameraFlytoSlots):
            ui_actions.append(camera_fly_to(slots.lng, slots.lat, slots.zoom))
            response_text = "已调整视角。"

        elif isinstance(slots, UIToggleLayerSlots):
            code = slots.layerCode or slots.layer_name or ""
            ui_actions.append(
                toggle_layer(
                    layer_code=code,
                    layer_name=slots.layer_name,
                    on=bool(slots.on),
                )
            )
            response_text = f"图层已{'显示' if slots.on else '隐藏'}。"

        else:
            # 未覆盖的 UI 类型：退化为透传（尽量不丢信息）
            try:
                payload = asdict(slots)
            except Exception:
                payload = {}
            ui_actions.append(raw_action("unknown_ui", payload))
            response_text = "已记录请求。"

        serialized = serialize_actions(ui_actions)
        logger.info("ui_actions_built", count=len(serialized))
        return {"ui_actions": serialized, "response_text": response_text}
