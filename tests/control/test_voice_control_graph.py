from __future__ import annotations

import asyncio
import os
from collections import deque
from typing import Any, Dict

import pytest

pytest.importorskip("langgraph")

from emergency_agents.control import VoiceControlPipeline

try:
    from emergency_agents.graph.voice_control_app import build_voice_control_graph
except ModuleNotFoundError as exc:  # pragma: no cover - 兼容缺失依赖的环境
    pytest.skip(f"voice control graph unavailable: {exc}", allow_module_level=True)

POSTGRES_DSN = os.getenv("POSTGRES_DSN")
if not POSTGRES_DSN:
    pytest.skip("POSTGRES_DSN 未配置，跳过语音控制图测试", allow_module_level=True)


class _StubAdapterClient:
    """用于测试的 Adapter Hub stub。"""

    def __init__(self) -> None:
        self.commands: deque[Dict[str, Any]] = deque()

    async def send_device_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        self.commands.append(command)
        return {"code": 0, "payload": {"status": "ok"}}


def test_voice_control_graph_dispatch(tmp_path) -> None:
    pipeline = VoiceControlPipeline(default_robotdog_id="dog-555")
    adapter = _StubAdapterClient()
    graph = asyncio.run(
        build_voice_control_graph(
            pipeline=pipeline,
            adapter_client=adapter,
            postgres_dsn=POSTGRES_DSN,
        )
    )

    state = graph.invoke({"raw_text": "机器狗前进", "auto_confirm": True})

    assert state["status"] == "dispatched"
    assert adapter.commands
    command = adapter.commands.pop()
    assert command["deviceVendor"] == "dqDog"
    assert command["params"]["action"] == "forward"


def test_voice_control_graph_error_without_device(tmp_path) -> None:
    pipeline = VoiceControlPipeline(default_robotdog_id=None)
    adapter = _StubAdapterClient()
    graph = asyncio.run(
        build_voice_control_graph(
            pipeline=pipeline,
            adapter_client=adapter,
            postgres_dsn=POSTGRES_DSN,
        )
    )

    with pytest.raises(Exception):
        graph.invoke({"raw_text": "机器狗左转", "auto_confirm": True})
