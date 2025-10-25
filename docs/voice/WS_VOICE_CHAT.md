# WebSocket 语音对话实现与迁移说明

## 架构

前端音频流 (Opus/PCM)
→ WebSocket /ws/voice/chat
→ VoiceChatSession（缓存 opus_packets/raw_chunks）
→ VADDetector（Silero VAD，静默检测）
→ ASRService（阿里云/本地自动选择）
→ IntentHandler（LLM 聊天/占位意图）
→ TTSClient（Edge TTS 网关）
→ WebSocket 回传（JSON + base64 音频）

## 主要模块
- emergency_agents/api/voice_chat.py：WebSocket 处理器与会话管理
- emergency_agents/voice/vad_detector.py：VAD 检测，支持 Opus/PCM
- emergency_agents/voice/intent_handler.py：基于 OpenAI 客户端的聊天
- emergency_agents/voice/tts_client.py：远程 TTS 调用
- emergency_agents/voice/health/checker.py：健康检查器

## 路由
- ws: /ws/voice/chat（FastAPI @app.websocket）

## 依赖
- websockets>=12.0（已内置）
- opuslib>=3.0.1
- numpy>=1.24.0
- torch>=2.0.0

## 测试
- tests/api/test_ws_voice_chat.py：握手 + ping/pong 最小测试

## 迁移注意
- 临时文件请放置 temp/
- 测试文件统一放置 tests/
- 文档放置 docs/voice/
- 不做降级与简化，VAD 使用 Silero（torch 依赖较大，属必要成本）
