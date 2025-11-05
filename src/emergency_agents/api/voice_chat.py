from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any, Callable, Optional, List, Dict, Mapping

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from emergency_agents.config import AppConfig
from emergency_agents.voice.asr.service import ASRService
from emergency_agents.voice.health.checker import HealthChecker
from emergency_agents.voice.intent_handler import IntentHandler
from emergency_agents.voice.tts_client import TTSClient
from emergency_agents.voice.vad_detector import VADDetector
from emergency_agents.api.intent_processor import (
    process_intent_core,
    Mem0Metrics,
)
from emergency_agents.memory.conversation_manager import ConversationManager, MessageRecord
from emergency_agents.intent.registry import IntentHandlerRegistry
from emergency_agents.memory.mem0_facade import MemoryFacade
from emergency_agents.context.service import ContextService


logger = structlog.get_logger(__name__)


class VoiceChatSession:
    def __init__(self, session_id: str, websocket: WebSocket) -> None:
        # 会话标识
        self.session_id: str = session_id
        # WebSocket 对象引用
        self.websocket: WebSocket = websocket
        # 前端可能发送的 OPUS/PCM 音频缓存（统一在 16k PCM 处理）
        self.opus_packets: list[bytes] = []
        self.raw_chunks: list[bytes] = []
        # 是否处于录音态（收到 start 进入，收到 stop 退出）
        self.is_recording: bool = False
        # 累计收到的字节数（排查链路问题用）
        self.bytes_received_total: int = 0
        # 业务侧透传的会话/用户信息，来自前端 init 消息
        self.thread_id: Optional[str] = None
        self.user_id: Optional[str] = None

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
    def __init__(
        self,
        config: AppConfig | None = None,
        asr_service: ASRService | None = None,
        tts_client: TTSClient | None = None,
        intent_handler: IntentHandler | None = None,
    ) -> None:
        self._config = config or AppConfig.load_from_env()
        self.sessions: dict[str, VoiceChatSession] = {}
        self.health_checker = HealthChecker(check_interval=30)
        self.asr_service = asr_service or ASRService()
        self.tts_client = tts_client or TTSClient(
            tts_url=self._config.tts_api_url,
            voice=self._config.tts_voice,
        )
        self.intent_handler = intent_handler or IntentHandler(self._config)
        self.vad_detector = VADDetector()
        self.health_checker.register_service("voice_asr", self._check_asr_health)
        self.health_checker.register_service("voice_tts", self.tts_client.health_check)

        logger.info(
            "voice_chat_handler_initialized",
            vad_enabled=True,
        )

        # 统一意图管线依赖（启动后由 main.py 注入）
        self._conv_manager: Optional[ConversationManager] = None
        self._intent_registry: Optional[IntentHandlerRegistry] = None
        self._intent_graph: Any | None = None
        self._voice_control_graph: Any | None = None
        self._dialogue_graph: Any | None = None
        self._mem: Optional[MemoryFacade] = None
        self._build_history: Optional[Callable[[List[MessageRecord]], List[Dict[str, Any]]]] = None
        self._mem0_metrics_factory: Optional[Callable[[], Mem0Metrics]] = None
        self._context_service: Optional[ContextService] = None

    def set_intent_pipeline(
        self,
        *,
        manager: ConversationManager,
        registry: IntentHandlerRegistry,
        orchestrator_graph: Any,
        voice_control_graph: Any,
        dialogue_graph: Any,
        mem: MemoryFacade,
        build_history: Callable[[List[MessageRecord]], List[Dict[str, Any]]],
        mem0_metrics_factory: Callable[[], Mem0Metrics],
        context_service: Optional[ContextService] = None,
    ) -> None:
        """注入统一意图处理依赖，用于语音路径走编排图与子图。"""
        self._conv_manager = manager
        self._intent_registry = registry
        self._intent_graph = orchestrator_graph
        self._voice_control_graph = voice_control_graph
        self._dialogue_graph = dialogue_graph
        self._mem = mem
        self._build_history = build_history
        self._mem0_metrics_factory = mem0_metrics_factory
        self._context_service = context_service
        logger.info("voice_chat_intent_pipeline_ready")

    async def start_background_tasks(self) -> None:
        await self.asr_service.start_health_check()
        await self.health_checker.start()
        logger.info("voice_chat_background_tasks_started")

    async def stop_background_tasks(self) -> None:
        await self.asr_service.stop_health_check()
        await self.tts_client.close()
        await self.health_checker.stop()
        logger.info("voice_chat_background_tasks_stopped")

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = f"voice_{id(websocket)}"
        session = VoiceChatSession(session_id, websocket)
        self.sessions[session_id] = session
        logger.info("voice_chat_connected", session_id=session_id)

        try:
            # 握手成功回执
            await session.send_json({
                "type": "connected",
                "session_id": session_id,
                "message": "语音对话已连接",
            })

            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=300.0)
                    # Starlette 在断开时会返回 {"type": "websocket.disconnect", "code": 1000/1001/...}
                    msg_type = message.get("type") if isinstance(message, dict) else None
                    if msg_type == "websocket.disconnect":
                        logger.info(
                            "websocket_client_disconnected",
                            session_id=session.session_id,
                            code=message.get("code"),
                        )
                        break

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
            # 确保清理不再抛出异常，避免 ASGI 层报错导致连接异常关闭
            await self._cleanup_session(session_id)

    async def _cleanup_session(self, session_id: str) -> None:
        """清理会话资源，防止断开后继续收发导致报错。

        - 从内存移除会话
        - 停止录音并清空缓冲
        - 重置 VAD 会话状态
        - 尝试关闭 WebSocket（忽略已关闭异常）
        """
        session = self.sessions.pop(session_id, None)
        if not session:
            return

        try:
            session.is_recording = False
            session.opus_packets.clear()
            session.raw_chunks.clear()
        except Exception:
            # 缓冲清理失败不影响后续流程
            pass

        try:
            self.vad_detector.reset_session(session_id)
        except Exception as e:
            logger.warning("vad_session_reset_failed", session_id=session_id, error=str(e))

        try:
            await session.websocket.close()
        except Exception as e:
            # 连接可能已关闭，此处不再上报为错误，避免噪声
            logger.debug("websocket_close_ignored", session_id=session_id, error=str(e))

        logger.info(
            "voice_chat_session_closed",
            session_id=session_id,
            bytes_total=session.bytes_received_total,
        )

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
                    # 聚合当前缓存并后台处理，避免阻塞
                    audio_payload = b"".join(session.raw_chunks) if session.raw_chunks else b""
                    if not audio_payload and session.opus_packets:
                        try:
                            import opuslib
                            pcm_frames = []
                            decoder = opuslib.Decoder(16000, 1)
                            for opus_packet in session.opus_packets:
                                try:
                                    pcm_frame = decoder.decode(opus_packet, 960)
                                    pcm_frames.append(pcm_frame)
                                except Exception:
                                    continue
                            audio_payload = b"".join(pcm_frames)
                        except Exception as e:
                            logger.error("opus_decode_error_on_stop", session_id=session.session_id, error=str(e))
                    if audio_payload:
                        asyncio.create_task(self._process_audio_payload(session.session_id, audio_payload))
                    session.opus_packets.clear()
                    session.raw_chunks.clear()
                    self.vad_detector.reset_session(session.session_id)
            elif msg_type == "init":
                # 记录线程与用户信息，方便后续日志关联；同时返回确认
                session.thread_id = data.get("thread_id") or session.thread_id
                session.user_id = data.get("user_id") or session.user_id
                logger.info(
                    "realtime_init",
                    session_id=session.session_id,
                    thread_id=session.thread_id,
                    user_id=session.user_id,
                )
                await session.send_json({
                    "type": "init_ack",
                    "thread_id": session.thread_id,
                    "user_id": session.user_id,
                })
            elif msg_type == "ping":
                await session.send_json({"type": "pong"})
            elif msg_type == "text":
                # 文本走统一意图编排 + 可选 TTS
                user_text = data.get("text") or ""
                if not isinstance(user_text, str):
                    user_text = str(user_text)
                if not user_text:
                    return
                await self._process_intent_and_respond(session, user_text)
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
                # 二次确认：过短语音直接丢弃，避免无效调用
                if len(session.opus_packets) < 15 and len(session.raw_chunks) == 0:
                    logger.info("speech_too_short", session_id=session.session_id)
                    session.opus_packets.clear()
                    session.raw_chunks.clear()
                    self.vad_detector.reset_session(session.session_id)
                    return

                await session.send_json({"type": "vad", "is_speaking": False, "finalized": True})

                # 将当前音频数据打包后丢给后台任务，避免阻塞 receive 循环
                audio_payload = b"".join(session.raw_chunks) if session.raw_chunks else b""
                if not audio_payload and session.opus_packets:
                    try:
                        import opuslib
                        pcm_frames = []
                        decoder = opuslib.Decoder(16000, 1)
                        for opus_packet in session.opus_packets:
                            try:
                                pcm_frame = decoder.decode(opus_packet, 960)
                                pcm_frames.append(pcm_frame)
                            except Exception:
                                continue
                        audio_payload = b"".join(pcm_frames)
                    except Exception as e:
                        logger.error("opus_decode_error_on_finalize", session_id=session.session_id, error=str(e))

                if audio_payload:
                    asyncio.create_task(self._process_audio_payload(session.session_id, audio_payload))

                # 立即清空缓冲、复位 VAD，继续接收后续流
                session.opus_packets.clear()
                session.raw_chunks.clear()
                self.vad_detector.reset_session(session.session_id)
        except Exception as e:
            logger.error("handle_audio_failed", session_id=session.session_id, error=str(e))

    async def _process_audio_payload(self, session_id: str, audio_data: bytes) -> None:
        """后台执行完整的 ASR → LLM → TTS 流程，避免阻塞主循环。

        参数:
        - session_id: 会话标识，用于在发送阶段获取会话与安全检查
        - audio_data: 已合并好的 16k PCM 数据
        """
        session = self.sessions.get(session_id)
        if session is None:
            return
        try:
            try:
                asr_result = await self.asr_service.recognize(audio_data)
            except Exception as asr_error:
                logger.error(
                    "asr_call_failed",
                    session_id=session_id,
                    error=str(asr_error),
                    provider_status=self.asr_service.provider_status,
                    voice_asr_url=os.getenv("VOICE_ASR_WS_URL", ""),
                )
                await session.send_json({"type": "error", "message": f"ASR失败: {asr_error}"})
                return

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

            # 意图编排 + 可选 TTS
            await self._process_intent_and_respond(session, text)
        except Exception as e:
            logger.error("process_audio_failed", session_id=session_id, error=str(e))
            try:
                await session.send_json({"type": "error", "message": f"处理音频失败: {e}"})
            except Exception:
                pass


    async def _check_asr_health(self) -> bool:
        try:
            status = self.asr_service.provider_status
            return bool(status) and any(status.values())
        except Exception as e:
            logger.warning("asr_health_check_failed", error=str(e))
            return False

    async def _process_intent_and_respond(self, session: VoiceChatSession, user_text: str) -> None:
        """统一意图处理：调用意图编排图，发送 LLM 与 TTS 响应。"""
        # 若未注入统一管线，安全回退到旧的 IntentHandler，避免中断现有会话
        if not (
            self._conv_manager
            and self._intent_registry
            and self._intent_graph is not None
            and self._voice_control_graph is not None
            and self._dialogue_graph is not None
            and self._mem
            and self._build_history
            and self._mem0_metrics_factory
        ):
            logger.warning("intent_pipeline_not_ready_fallback")
            intent_type, response_text = await self.intent_handler.understand_and_respond(user_text)
            await session.send_json({"type": "llm", "text": response_text, "intent": intent_type})
            try:
                tts_audio = await self.tts_client.synthesize(response_text)
                if tts_audio:
                    audio_base64 = base64.b64encode(tts_audio).decode()
                    await session.send_json({"type": "tts", "audio": audio_base64, "format": "pcm"})
            except Exception as tts_err:
                logger.error("tts_call_failed", error=str(tts_err))
            return

        user_id = session.user_id or "voice_user"
        thread_id = session.thread_id or f"voice-{session.session_id}"

        try:
            result = await process_intent_core(
                user_id=user_id,
                thread_id=thread_id,
                message=user_text,
                metadata={},
                manager=self._conv_manager,
                registry=self._intent_registry,
                orchestrator_graph=self._intent_graph,
                voice_control_graph=self._voice_control_graph,
                dialogue_graph=self._dialogue_graph,
                mem=self._mem,
                build_history=self._build_history,  # type: ignore[arg-type]
                mem0_metrics=self._mem0_metrics_factory(),
                channel="voice",
                context_service=self._context_service,
            )

            # 兼容现有前端协议：返还 llm 文本 + intent 类型
            intent_type = str(result.intent.get("intent_type") or "").strip()
            response_text = None
            if isinstance(result.result, Mapping):
                response_text = (
                    result.result.get("response_text")
                    or result.result.get("response")
                )
            if not response_text:
                response_text = "处理完成。"

            await session.send_json({"type": "llm", "text": response_text, "intent": intent_type})

            # TTS 合成（失败不影响连接）
            try:
                tts_audio = await self.tts_client.synthesize(response_text)
                if tts_audio:
                    audio_base64 = base64.b64encode(tts_audio).decode()
                    await session.send_json({"type": "tts", "audio": audio_base64, "format": "pcm"})
            except Exception as tts_err:
                logger.error("tts_call_failed", error=str(tts_err))
        except Exception as exc:
            logger.error("intent_pipeline_failed", error=str(exc), session_id=session.session_id)
            await session.send_json({"type": "error", "message": f"意图处理失败: {exc}"})


_voice_config = AppConfig.load_from_env()
voice_chat_handler = VoiceChatHandler(config=_voice_config)


async def handle_voice_chat(websocket: WebSocket) -> None:
    # 单一入口，转交给处理器，保持路由层简洁
    await voice_chat_handler.handle_connection(websocket)
