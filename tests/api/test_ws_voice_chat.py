from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("prometheus_fastapi_instrumentator")

from emergency_agents.api.main import app


client = TestClient(app)


def test_ws_voice_chat_handshake_and_ping() -> None:
    with client.websocket_connect("/ws/voice/chat") as ws:
        # 连接成功消息
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert "session_id" in msg

        # 发送 ping
        ws.send_text(json.dumps({"type": "ping"}))
        pong = ws.receive_json()
        assert pong["type"] == "pong"
