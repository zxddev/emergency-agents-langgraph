from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
import structlog

from emergency_agents.voice.asr.service import ASRService
from emergency_agents.voice.health.checker import HealthChecker
from emergency_agents.voice.intent_handler import IntentHandler
from emergency_agents.voice.tts_client import TTSClient
from emergency_agents.voice.vad_detector import VADDetector


logger = structlog.get_logger(__name__)


class VoiceChatSession:
    def __init__(self, session_id: str, websocket: WebSocket) -> None:
        self.session_id = session_id
        self.websocket = websocket
        self.opus_packets: list[bytes] = []
        self.raw_chunks: list[bytes] = []
        self.is_recording = False
        self.bytes_received_total = 0

    async def send_json(self, data: dict[str, Any]) -> None:
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logger.error("send_json_failed", session_id=self.session_id, error=str(e))

    async def send_bytes(self, data: bytes) -> None:
        try:
            await self.websocket.send_bytes(data)
        except Exception as e:
            logger.error("send_bytes_failed", session_id=self.session_id, error=str(e))


class VoiceChatHandler:
    def __init__(self) -> None:
        self.sessions: dict[str, VoiceChatSession] = {}
        self.health_checker = HealthChecker(check_interval=30)
        self.asr_service = ASRService()
        self.tts_client = TTSClient()
        self.intent_handler = IntentHandler()
        self.vad_detector = VADDetector()

        logger.info(
            "voice_chat_handler_initialized",
            vad_enabled=True,
        )

    async def start_background_tasks(self) -> None:
        await self.health_checker.start()
        logger.info("voice_chat_background_tasks_started")

    async def stop_background_tasks(self) -> None:
        await self.health_checker.stop()
        logger.info("voice_chat_background_tasks_stopped")

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = f"voice_{id(websocket)}"
        session = VoiceChatSession(session_id, websocket)
        self.sessions[session_id] = session
        logger.info("voice_chat_connected", session_id=session_id)

        try:
            await session.send_json({
                "type": "connected",
                "session_id": session_id,
                "message": "语音对话已连接"
            })

            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=300.0)
                    if "text" in message:
                        await self._handle_text_message(session, message["text"])
                    elif "bytes" in message:
                        await self._handle_audio_data(session, message["bytes"]) 
                except asyncio.TimeoutError:
                    logger.info("websocket_timeout", session_id=session.session_id)
                    break
        except WebSocketDisconnect:
            logger.info("voice_chat_disconnected", session_id=session_id)
        except Exception as e:
            logger.error("voice_chat_error", session_id=session_id, error=str(e))
        finally:
            await self._cleanup_session(session_id)

    async def _handle_text_message(self, session: VoiceChatSession, text: str) -> None:
        try:
            data = json.loads(text)
            msg_type = data.get("type")
            if msg_type == "start":
                session.is_recording = True
                session.opus_packets.clear()
                self.vad_detector.reset_session(session.session_id)
                logger.info("recording_started", session_id=session.session_id)
                await session.send_json({"type": "recording_started", "message": "开始录音"})
            elif msg_type == "stop":
                session.is_recording = False
                logger.info("recording_manually_stopped", session_id=session.session_id)
                if len(session.opus_packets) > 0 or len(session.raw_chunks) > 0:
                    await self._process_complete_audio(session)
            elif msg_type == "ping":
                await session.send_json({"type": "pong"})
        except Exception as e:
            logger.error("handle_text_failed", session_id=session.session_id, error=str(e))

    async def _handle_audio_data(self, session: VoiceChatSession, audio_bytes: bytes) -> None:
        if not session.is_recording:
            return
        try:
            # 默认按 PCM 直传处理，避免浏览器 webm/opus 容器不兼容问题
            client_have_voice, client_voice_stop = self.vad_detector.process_pcm_chunk(
                session.session_id, audio_bytes
            )
            session.raw_chunks.append(audio_bytes)
            session.bytes_received_total += len(audio_bytes)

            if client_have_voice:
                await session.send_json({"type": "vad", "is_speaking": True})

            if client_voice_stop:
                if len(session.opus_packets) < 15 and len(session.raw_chunks) == 0:
                    logger.info("speech_too_short", session_id=session.session_id)
                    session.opus_packets.clear()
                    session.raw_chunks.clear()
                    self.vad_detector.reset_session(session.session_id)
                    return
                await session.send_json({"type": "vad", "is_speaking": False, "finalized": True})
                await self._process_complete_audio(session)
                session.opus_packets.clear()
                session.raw_chunks.clear()
                self.vad_detector.reset_session(session.session_id)
        except Exception as e:
            logger.error("handle_audio_failed", session_id=session.session_id, error=str(e))

    async def _process_complete_audio(self, session: VoiceChatSession) -> None:
        try:
            opus_packets = session.opus_packets.copy()
            raw_chunks = session.raw_chunks.copy()

            audio_data = b""
            if raw_chunks:
                audio_data = b"".join(raw_chunks)
            elif opus_packets:
                import opuslib
                pcm_frames = []
                decoder = opuslib.Decoder(16000, 1)
                for opus_packet in opus_packets:
                    try:
                        pcm_frame = decoder.decode(opus_packet, 960)
                        pcm_frames.append(pcm_frame)
                    except Exception:
                        continue
                audio_data = b"".join(pcm_frames)
            else:
                return

            asr_result = await self.asr_service.recognize(audio_data)
            text = asr_result.text

            await session.send_json({
                "type": "stt",
                "text": text,
                "is_final": True,
                "provider": asr_result.provider,
                "latency_ms": asr_result.latency_ms,
            })

            if not text:
                return

            intent_type, response_text = await self.intent_handler.understand_and_respond(text)
            await session.send_json({"type": "llm", "text": response_text, "intent": intent_type})

            tts_audio = await self.tts_client.synthesize(response_text)
            if tts_audio:
                audio_base64 = base64.b64encode(tts_audio).decode()
                await session.send_json({"type": "tts", "audio": audio_base64, "format": "pcm"})
        except Exception as e:
            logger.error("process_audio_failed", session_id=session.session_id, error=str(e))
            await session.send_json({"type": "error", "message": f"处理音频失败: {e}"})


voice_chat_handler = VoiceChatHandler()


async def handle_voice_chat(websocket: WebSocket) -> None:
    await voice_chat_handler.handle_connection(websocket)
