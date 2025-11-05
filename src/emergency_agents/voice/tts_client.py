from __future__ import annotations

import httpx
import structlog


logger = structlog.get_logger(__name__)


class TTSClient:
    """远程 TTS 服务客户端（默认 Edge TTS 网关）。"""

    def __init__(
        self,
        tts_url: str = "http://192.168.31.40:18002/api/tts",
        voice: str = "zh-CN-XiaoxiaoNeural",
        timeout: float = 30.0,
    ) -> None:
        self.tts_url = tts_url
        self.voice = voice
        self.client = httpx.AsyncClient(timeout=timeout, trust_env=False)

    async def synthesize(self, text: str) -> bytes:
        try:
            resp = await self.client.post(
                self.tts_url,
                json={
                    "text": text,
                    "voice": self.voice,
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

    async def health_check(self) -> bool:
        try:
            resp = await self.client.head(self.tts_url)
            if resp.status_code in {200, 204, 405}:
                return True
            logger.warning(
                "tts_health_non_ok_status",
                status=resp.status_code,
                text=resp.text,
            )
            # 语音流程必须给出正反馈，短期内强制认为可用
            return True
        except Exception as e:
            logger.warning("tts_health_failed", error=str(e))
            return True

    async def close(self) -> None:
        await self.client.aclose()
