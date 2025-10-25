from __future__ import annotations

import time
from collections import deque

import numpy as np
import opuslib
import structlog
import torch


logger = structlog.get_logger(__name__)


class VADDetector:
    """语音活动检测器（Silero VAD）

    - 支持两种输入：裸 Opus 帧（process_opus_packet）与原始 PCM 块（process_pcm_chunk）
    - 采样率：16kHz，单声道，int16 LE
    - 滑动窗口去抖动与双阈值判断，静默 1s 认为一句话结束
    """

    def __init__(self, model_dir: str = "models/silero-vad") -> None:
        # 加载 Silero VAD 模型（优先本地，失败则尝试线上仓）
        try:
            self.model, _ = torch.hub.load(
                repo_or_dir=model_dir,
                source="local",
                model="silero_vad",
                force_reload=False,
            )
            logger.info("silero_vad_loaded", model_dir=model_dir)
        except Exception as e:
            logger.warning("vad_load_from_local_failed, trying online", error=str(e))
            self.model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
            )
            logger.info("silero_vad_loaded_online")

        # Opus 解码器（16kHz, mono）
        self.decoder = opuslib.Decoder(16000, 1)

        # 判定阈值与窗口配置
        self.vad_threshold = 0.5
        self.vad_threshold_low = 0.2
        self.silence_threshold_ms = 1000
        self.frame_window_threshold = 3

        # 会话状态表
        self.session_states: dict[str, VADSessionState] = {}

    def get_or_create_state(self, session_id: str) -> "VADSessionState":
        if session_id not in self.session_states:
            self.session_states[session_id] = VADSessionState()
        return self.session_states[session_id]

    def process_opus_packet(self, session_id: str, opus_packet: bytes) -> tuple[bool, bool]:
        """处理一帧 Opus 包，返回 (是否在说话, 是否说话结束)"""
        state = self.get_or_create_state(session_id)
        try:
            # Opus → PCM（每帧 960 采样点 ≈ 60ms @ 16kHz）
            pcm_frame = self.decoder.decode(opus_packet, 960)
            state.client_audio_buffer.extend(pcm_frame)

            client_have_voice = False

            # 每次消费 512 采样点（=1024 字节）
            while len(state.client_audio_buffer) >= 512 * 2:
                chunk = state.client_audio_buffer[: 512 * 2]
                state.client_audio_buffer = state.client_audio_buffer[512 * 2 :]

                audio_int16 = np.frombuffer(chunk, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                audio_tensor = torch.from_numpy(audio_float32)

                with torch.no_grad():
                    speech_prob = self.model(audio_tensor, 16000).item()

                if speech_prob >= self.vad_threshold:
                    is_voice = True
                elif speech_prob <= self.vad_threshold_low:
                    is_voice = False
                else:
                    is_voice = state.last_is_voice

                state.last_is_voice = is_voice

                state.client_voice_window.append(is_voice)
                client_have_voice = (
                    state.client_voice_window.count(True) >= self.frame_window_threshold
                )

                if state.client_have_voice and not client_have_voice:
                    stop_duration = time.time() * 1000 - state.last_activity_time
                    if stop_duration >= self.silence_threshold_ms:
                        state.client_voice_stop = True
                        logger.info(
                            "speech_ended_by_silence",
                            session_id=session_id,
                            silence_ms=stop_duration,
                        )

                if client_have_voice:
                    state.client_have_voice = True
                    state.last_activity_time = time.time() * 1000

            return client_have_voice, state.client_voice_stop

        except opuslib.OpusError as e:
            logger.error("opus_decode_error", session_id=session_id, error=str(e))
            return False, False

    def process_pcm_chunk(self, session_id: str, pcm_chunk: bytes) -> tuple[bool, bool]:
        """处理原始 PCM 数据块（16kHz, mono, int16 LE），返回 (是否在说话, 是否说话结束)"""
        state = self.get_or_create_state(session_id)
        try:
            state.client_audio_buffer.extend(pcm_chunk)
            client_have_voice = False

            while len(state.client_audio_buffer) >= 512 * 2:
                chunk = state.client_audio_buffer[: 512 * 2]
                state.client_audio_buffer = state.client_audio_buffer[512 * 2 :]

                audio_int16 = np.frombuffer(chunk, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                audio_tensor = torch.from_numpy(audio_float32)

                with torch.no_grad():
                    speech_prob = self.model(audio_tensor, 16000).item()

                if speech_prob >= self.vad_threshold:
                    is_voice = True
                elif speech_prob <= self.vad_threshold_low:
                    is_voice = False
                else:
                    is_voice = state.last_is_voice

                state.last_is_voice = is_voice

                state.client_voice_window.append(is_voice)
                client_have_voice = (
                    state.client_voice_window.count(True) >= self.frame_window_threshold
                )

                if state.client_have_voice and not client_have_voice:
                    stop_duration = time.time() * 1000 - state.last_activity_time
                    if stop_duration >= self.silence_threshold_ms:
                        state.client_voice_stop = True
                        logger.info(
                            "speech_ended_by_silence",
                            session_id=session_id,
                            silence_ms=stop_duration,
                        )

                if client_have_voice:
                    state.client_have_voice = True
                    state.last_activity_time = time.time() * 1000

            return client_have_voice, state.client_voice_stop

        except Exception as e:
            logger.error("vad_process_failed", session_id=session_id, error=str(e))
            return False, False

    def reset_session(self, session_id: str) -> None:
        if session_id in self.session_states:
            state = self.session_states[session_id]
            state.client_audio_buffer = bytearray()
            state.client_have_voice = False
            state.client_voice_stop = False
            state.client_voice_window.clear()
            state.last_is_voice = False
            state.last_activity_time = time.time() * 1000
            logger.info("vad_session_reset", session_id=session_id)


class VADSessionState:
    def __init__(self) -> None:
        self.client_audio_buffer = bytearray()
        self.client_have_voice = False
        self.last_activity_time = time.time() * 1000
        self.client_voice_stop = False
        self.client_voice_window: deque[bool] = deque(maxlen=5)
        self.last_is_voice = False


