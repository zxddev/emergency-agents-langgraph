from __future__ import annotations

import httpx
import structlog


logger = structlog.get_logger(__name__)


class TTSClient:
    """远程 TTS 服务客户端（默认 Edge TTS 网关）。"""

    def __init__(self, tts_url: str = "http://192.168.31.40:18002/api/tts") -> None:
        self.tts_url = tts_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def synthesize(self, text: str) -> bytes:
        try:
            resp = await self.client.post(
                self.tts_url,
                json={
                    "text": text,
                    "voice": "zh-CN-XiaoxiaoNeural",
                    "format": "pcm",
                    "sample_rate": 16000,
                },
            )
            if resp.status_code == 200:
                audio = resp.content
                logger.info("tts_synthesis_complete", text_length=len(text), audio_size=len(audio))
                return audio
            logger.error("tts_synthesis_failed", status=resp.status_code, text=resp.text)
            return b""
        except Exception as e:
            logger.error("tts_call_failed", error=str(e))
            return b""

    async def close(self) -> None:
        await self.client.aclose()
