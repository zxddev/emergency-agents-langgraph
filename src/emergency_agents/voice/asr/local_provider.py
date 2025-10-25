# Copyright 2025 msq
from __future__ import annotations

"""本地 FunASR 提供方实现（WebSocket）。

摘要：通过 WebSocket 使用本地 FunASR，遵循 start/end 协议进行流式识别。
"""

import asyncio
import json
import os
import ssl
import time
from typing import Any

import structlog
import websockets

from .base import ASRConfig, ASRProvider, ASRResult

logger = structlog.get_logger(__name__)


class LocalFunASRProvider(ASRProvider):
    """本地 FunASR 提供方。"""

    def __init__(self, asr_ws_url: str | None = None) -> None:
        self._url = asr_ws_url or os.getenv("VOICE_ASR_WS_URL", "wss://127.0.0.1:10097")
        self._hotwords_json = os.getenv("FUNASR_HOTWORDS_JSON", "{}")
        self._chunk_cfg = self._parse_chunk_size(os.getenv("FUNASR_CHUNK_SIZE", "5,10,5"))
        logger.info("local_funasr_initialized", url=self._url, chunk=self._chunk_cfg)
        if not self._url:
            logger.error("local_funasr_url_missing", env_var="VOICE_ASR_WS_URL")

    @staticmethod
    def _parse_chunk_size(csv: str) -> list[int]:
        try:
            return [int(x.strip()) for x in csv.split(",") if x.strip()]
        except Exception:
            return [5, 10, 5]

    @property
    def name(self) -> str:  # noqa: D401
        return "local"

    async def recognize(self, audio_data: bytes, config: ASRConfig | None = None) -> ASRResult:
        """使用本地 FunASR 进行识别。

        Args:
            audio_data: 原始音频二进制。
            config: 识别配置。

        Returns:
            ASRResult: 识别结果。
        """

        cfg = config or ASRConfig()
        start_ts = time.time()

        ssl_ctx = None
        if self._url.startswith("wss://"):
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        logger.info("local_asr_connect", url=self._url, size=len(audio_data))

        async with websockets.connect(
            self._url,
            open_timeout=10,
            ping_interval=None,
            subprotocols=["binary"],
            additional_headers={"User-Agent": "EA-LocalASR/1.0"},
            user_agent_header="EA-LocalASR/1.0",
            max_size=None,
            ssl=ssl_ctx,
        ) as ws:
            start_msg: dict[str, Any] = {
                "mode": "2pass",
                "wav_name": "audio_stream",
                "is_speaking": True,
                "wav_format": cfg.format,
                "audio_fs": cfg.sample_rate,
                "chunk_size": self._chunk_cfg,
                "hotwords": self._hotwords_json,
                "itn": True,
            }
            await ws.send(json.dumps(start_msg))

            # 200ms 分块发送
            chunk_bytes = 6400
            for i in range(0, len(audio_data), chunk_bytes):
                await ws.send(audio_data[i : i + chunk_bytes])
                await asyncio.sleep(0.005)

            # 结束帧
            await ws.send(json.dumps({"is_speaking": False}))

            final_text = ""
            try:
                async for message in ws:
                    try:
                        obj = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    text = obj.get("text", "")
                    mode = obj.get("mode", "")
                    is_final = bool(obj.get("is_final", False))
                    if text:
                        final_text = text
                    if mode == "2pass-offline" or (not mode and is_final):
                        break
            except Exception:
                # 服务器可能主动关闭
                pass

        latency_ms = int((time.time() - start_ts) * 1000)
        return ASRResult(
            text=final_text,
            confidence=1.0,
            is_final=True,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={"url": self._url},
        )

    async def health_check(self) -> bool:
        """轻量健康检查：尝试握手并发送 ping。"""

        ssl_ctx = None
        if self._url.startswith("wss://"):
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            async with websockets.connect(self._url, open_timeout=5, ssl=ssl_ctx) as ws:
                await ws.send(json.dumps({"type": "ping"}))
                await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.warning("local_asr_unhealthy", error=str(e))
            return False

