# Copyright 2025 msq
from __future__ import annotations

"""阿里云百炼 fun-asr 提供方实现。

摘要：基于 DashScope SDK 的实时识别实现，适用于 16k 单声道 PCM/WAV。
"""

import asyncio
import os
import time
from typing import Optional

import structlog

from .base import ASRConfig, ASRProvider, ASRResult

logger = structlog.get_logger(__name__)


class _AliyunASRCallback:  # 轻量内部回调桥接，避免直接依赖SDK类型暴露
    """回调桥接：以事件完成机制等待最终文本。"""

    def __init__(self, timeout_seconds: float) -> None:
        self.final_text: str = ""
        self.error: Optional[Exception] = None
        self._done: asyncio.Event = asyncio.Event()
        self._timeout_seconds = timeout_seconds

    # DashScope RecognitionCallback 约定的方法名
    def on_open(self) -> None:  # noqa: D401
        logger.debug("aliyun_asr_open")

    def on_close(self) -> None:  # noqa: D401
        logger.debug("aliyun_asr_close")
        if not self._done.is_set():
            self._done.set()

    def on_complete(self) -> None:  # noqa: D401
        logger.debug("aliyun_asr_complete")
        self._done.set()

    def on_error(self, result) -> None:  # noqa: D401
        msg = getattr(result, "message", "unknown_error")
        req_id = getattr(result, "request_id", "")
        logger.error("aliyun_asr_error", message=msg, request_id=req_id)
        self.error = Exception(f"request_id={req_id}, message={msg}")
        self._done.set()

    def on_event(self, result) -> None:  # noqa: D401
        try:
            sentence = result.get_sentence()  # type: ignore[attr-defined]
        except Exception:  # SDK 兼容
            sentence = None
        if sentence and "text" in sentence:
            text = sentence["text"] or ""
            if text:
                self.final_text = text
            logger.debug("aliyun_asr_text", text=text)

    async def wait(self) -> None:
        await asyncio.wait_for(self._done.wait(), timeout=self._timeout_seconds)
        if self.error:
            raise self.error


class AliyunASRProvider(ASRProvider):
    """阿里云百炼 fun-asr 提供方。"""

    def __init__(self, api_key: str | None = None, model: str = "fun-asr-realtime") -> None:
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self._api_key:
            raise ValueError("DASHSCOPE_API_KEY is required")
        self._model = model
        timeout_raw = os.getenv("ALIYUN_ASR_TIMEOUT_SECONDS", "60")
        try:
            self._timeout_seconds = max(30.0, float(timeout_raw))
        except ValueError:
            self._timeout_seconds = 60.0

        # 延迟导入，避免在未使用时引入依赖
        import dashscope  # type: ignore

        dashscope.api_key = self._api_key
        self._dashscope = dashscope
        logger.info(
            "aliyun_asr_initialized",
            model=model,
            timeout_seconds=self._timeout_seconds,
        )

    @property
    def name(self) -> str:  # noqa: D401
        return "aliyun"

    @property
    def priority(self) -> int:  # noqa: D401
        return 100

    async def recognize(self, audio_data: bytes, config: ASRConfig | None = None) -> ASRResult:
        """使用阿里云 fun-asr 进行识别。

        Args:
            audio_data: 原始音频二进制。
            config: 识别配置。

        Returns:
            ASRResult: 识别结果。
        """

        cfg = config or ASRConfig()
        start_ts = time.time()

        from dashscope.audio.asr import Recognition  # type: ignore

        callback = _AliyunASRCallback(timeout_seconds=self._timeout_seconds)
        recognition = Recognition(
            model=self._model,
            format=cfg.format,
            sample_rate=cfg.sample_rate,
            callback=callback,
            semantic_punctuation_enabled=False,
            punctuation_prediction_enabled=cfg.enable_punctuation,
        )

        logger.info("aliyun_asr_start", size=len(audio_data), fmt=cfg.format, sr=cfg.sample_rate)

        # 启动与发送需配合异步节流以避免内部缓冲溢出
        recognition.start()
        try:
            chunk = 6400  # 约 200ms @ 16k/16bit/mono
            for i in range(0, len(audio_data), chunk):
                recognition.send_audio_frame(audio_data[i : i + chunk])
                await asyncio.sleep(0.005)

            # SDK 的 stop 同步阻塞，放到线程池执行
            await asyncio.get_event_loop().run_in_executor(None, recognition.stop)
            await callback.wait()
        except Exception:
            # 确保连接关闭
            try:
                await asyncio.get_event_loop().run_in_executor(None, recognition.stop)
            except Exception:  # 忽略二次关闭错误
                pass
            raise

        latency_ms = int((time.time() - start_ts) * 1000)
        result = ASRResult(
            text=callback.final_text,
            confidence=1.0,
            is_final=True,
            provider=self.name,
            latency_ms=latency_ms,
            metadata={
                "model": self._model,
            },
        )
        logger.info("aliyun_asr_done", latency_ms=latency_ms, text_preview=result.text[:50])
        return result

    async def health_check(self) -> bool:
        """执行轻量健康检查：静音识别是否成功返回。"""

        try:
            silent = b"\x00" * (16000 * 2)  # 1s @ 16k/16bit/mono
            health_timeout = self._timeout_seconds + 10.0
            _ = await asyncio.wait_for(self.recognize(silent, ASRConfig()), timeout=health_timeout)
            return True
        except Exception as e:
            logger.warning("aliyun_asr_unhealthy", error=str(e))
            return False

