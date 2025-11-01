# AI-前端三端交互实录

> 依据真实代码梳理 `emergency-agents-langgraph`（AI 后端）、`emergency-web-api`（Java 中转）与 `emergency-rescue-brain`（前端）之间的 HTTP / STOMP / 语音链路，纠正旧手册中的失真描述。

## 1. 三个项目的职责边界

| 模块 | 关键位置 | 角色概述 |
| ---- | -------- | -------- |
| LangGraph（Python） | `src/emergency_agents/...` | 负责意图识别、救援/侦察方案生成，并通过 `OrchestratorClient` 将结构化 payload POST 给 Java（`publish_rescue_scenario`、`publish_incident_entities` 等）。 |
| Java Web-API | `src/main/java/com/cykj/webapi/...` | 统一 REST/STOMP 出口：校验请求、落库并按照平台协议向 `/topic/**`、`/user/**` 推送消息，同时代理语音 ASR 到 Python。 |
| 前端 | `src/api`, `src/services`, `src/view` | 所有 HTTP 都打到 `/web-api/**`，STOMP 连接 `SockJS('/web-api/ws/real-time')`，将收到的实体/场景消息转成 `eventBus` 事件驱动 Mars3D。Redux 仅保留实体缓存，UI 展示已改为基于事件流。 |

Vite 代理确认：`vite.config.js:82-118` 将 `/api` 重写为 `/web-api/api`，`/web-api` 直接透传，`/ws` 代理到 `/web-api/ws`。前端任何手写 URL 都需走这两条路径，否则绕过 Java。

## 2. HTTP 链路（前端 → Java → Python）

1. **实体与图层查询**
   - 前端：`src/api/entities.js`, `src/api/layers.js`，封装 `fetchEntities`、`getEntitiesByIds` 等。
   - Java：`EntityController`（`/api/v1/entities/**`，`EntityController.java:37-177`）、`LayerController`（`/api/v1/layers/**`，`LayerController.java:31-125`）。
   - LangGraph：并不直接暴露实体查询，而是通过 `OrchestratorClient` 写入 Java；entities 的落库 & 推送见下节。

2. **救援/侦察方案推送**
   - LangGraph：`RescueTaskGenerationHandler.handle` 在生成方案后调用 `orchestrator.publish_rescue_scenario(...)`（`rescue_task_generation.py:640-699`）。
   - Java 接口：`RescueScenarioController.publish` → `RescueScenarioService.publish` → `TaskCommandService.publishTaskScenarioMessage`（`TaskCommandService.java:288-302`）。最终通过 `SimpMessagingTemplate` 广播 `/topic/scenario.task.triggered`。

3. **Python 反向调用**
   - Java `PlanService` 仍用直连 URL 调 LangGraph 多灾种规划（`PlanService.java:603-647`），使用 `http://localhost:8008/ai/plan/multi-hazard`。
   - `PythonServiceProperties`（`python.service.*` 配置，`PythonServiceProperties.java:10-36`）统一描述此连接。

4. **REST 响应约定**
   - Java 所有接口返回 `ApiResponse`（`ApiResponse.java:14-90`）。
   - 前端统一通过 `parseApiResponse` / `parsePaginatedResponse` 解包（`src/api/apiResponse.js:21-70`）。

❗ 与旧文档差异：过去描述的 `extra.module_next`、`scope=event` 已不存在；现有 payload 中 `extra = { action: "refresh", module: "task" }`（`TaskCommandService.java:288-302`）。

## 3. STOMP 消息流

Java `WebSocketConfig`（`WebSocketConfig.java:20-118`）暴露 `/ws/real-time`，应用前缀 `/app`，广播前缀 `/topic`，点对点 `/queue`。前端所有 STOMP 连接使用 `SockJS('${base}/web-api/ws/real-time')`（`EntityWebSocketClient.js:11-22`、`VoiceChatStomp.jsx:60-97`）。

| 主题/目的地 | 生产者 | Payload 关键字段 | 前端处理 |
| ----------- | ------ | ---------------- | -------- |
| `/topic/map.entity.create`<br>`/topic/map.entity.update`<br>`/topic/map.entity.delete` | `EntityServiceImpl.broadcast*`（`EntityServiceImpl.java:309-358`） | `id`, `layerCode`, `type`, `geometry`, `properties`, `visibleOnMap`, `dynamic`, `updatedAt` | `useEntityStream` → `normalizeEntityPayload` → Redux `upsertEntity/removeEntity` & `eventBus.emit(MAP_EVENTS.UPSERT_LAYER_ENTITY)`（`useEntityStream.js:12-86`）。 |
| `/topic/scenario.task.triggered` | `TaskCommandService.publishTaskScenarioMessage` | `title`, `content`, `dateTime`, `scope`, `isPop`, `entityIds`, `extra.action=refresh`, `extra.module=task` | `ai-broadcast.jsx` 检查 `scope` 是否包含当前角色，调用 `emitScenarioMessage`、`eventBus.emit(ACTION_EVENTS.REFRESH_MODULE)`，并拉取 `entityIds`（`ai-broadcast.jsx:266-318`）。 |
| `/topic/scenario.disaster.triggered`<br>`/topic/scenario.prompt.triggered` | 同上（灾情播报 / 提示） | 同结构，`scenarioType` 区分池 | `ai-broadcast.jsx` 的同一回调，根据 `scenarioType` 分支。 |
| `/topic/realtime.location` | 仿真/指挥车实时推送（`RealtimeLocationSimulator.java:357-514` / `SimulationOrchestrator.java:240`） | `id`, `layerCode`, `geometry.coordinates`, `properties.speed/battery/state` | `EntityWebSocketClient` 把 `scenarioType` 设置为 `realtime`，前端调用 `handleEntityItem` 更新实时点位。 |
| `/topic/system.connected` | `EmergencyEventController.handleWebSocketConnect` | `sessionId` | 仅记录连接（前端默认忽略）。 |
| `/user/queue/voice/stt`<br>`/user/queue/voice/response`<br>`/user/queue/voice/tts` | 语音 ASR Handler（见下一节） | `text`, `audio` base64 | `VoiceChatStomp.jsx` 直接显示字幕/播放音频。 |

订阅管理：`EntityWebSocketClient` 不再使用旧的 Redux selectors，而是 `setHandlers` → 直接驱动 `eventBus`，Redux 只作缓存与补拉（`useEntityStream.js:12-108`）。旧文档提及的“Redux 触发 UI”已过时。

## 4. 实体与场景数据映射

1. **实体标准形态**
   - Java `basePayload`（`EntityServiceImpl.java:394-410`）定义推送字段。
   - 前端 `normalizeEntityPayload`（`useEntityStream.js:12-39`）仅保留 `layerCode/type/geometry/properties/...`。`layerName` 等额外字段会被忽略。
   - Redux 之后把实体 ID 映射回图层，方便补拉（`entitiesSlice.js:55-110`）。

2. **场景消息**
   - Java 构造内容：`title`、`content`、`scope`（固定 `["commander","scout","coordinator","common"]`）、`entityIds`、`extra.module="task"`, `extra.action="refresh"`（`TaskCommandService.java:288-302`）。
   - 前端 `emitScenarioMessage` 负责弹窗 + TTS（`ai-broadcast.jsx:231-262`），`handleEntityList` 用 `/api/v1/entities/by-ids`（`entities.js:71-84`）刷新地图。
   - 旧文档所述 `module_next`、`eventType` 数值校验只适用于历史静态模板，目前 `TaskCommandService` 不再提供该字段，如需图标需自行扩展。

3. **角色过滤**
   - `ai-broadcast.jsx` 只有在 `scope` 包含当前用户角色时才执行 `handleScenarioTask`（`ai-broadcast.jsx:299-307`）。前端登陆信息从 `userDetail` 获取，若角色不匹配则静默。

## 5. 语音链路（asr ↔ agent）

1. **前端采集与推送**
   - 组件：`src/components/voice-chat/VoiceChatStomp.jsx`。
   - 连接：SockJS → `/web-api/ws/real-time`，订阅 `/user/queue/voice/*`。
   - 音频 push：`MediaRecorder` 每段 `ondataavailable` 读成 base64 后 publish 到 `/app/voice/audio`，携带 `{ userId, audio, format }`（`VoiceChatStomp.jsx:174-191`）。

2. **Java WebSocket Handler**
   - `RealtimeAsrWebSocketHandler` 接受音频，转发给实时 ASR 服务，并在识别完成时调用 `agent.asr.process-url`（默认 `http://localhost:8000/api/v1/asr/process`，`RealtimeAsrWebSocketHandler.java:245-307`）。
   - 将 Agent 返回的 `{ message, trace_id, response_type }` 编造成 `{ mode: "AGENT", is_final: true, text, trace_id }` 推回原 WebSocket 会话。
   - 语音播报音频通过 `/user/queue/voice/tts` 下发，前端 `playAudio` 播放。

3. **差异提示**
   - 旧文档描述 “前端直接连接 LangGraph” 已失效；现状是前端→Java（WebSocket）→Python（HTTP）。
   - 开发时需同时检查：媒体权限、Java WebSocket、Python Agent HTTP 接口，缺一不可。

## 6. 与旧手册的关键差异

| 旧文档说法 | 实际代码 | 说明 |
| ---------- | -------- | ---- |
| STOMP payload 含 `module_next`、`eventType` | 现仅包含 `extra.action/module`（`TaskCommandService.java:288-302`） | `eventType/eventLevel` 若需要，需要 Java 从事件模型中补写，目前未实现。 |
| Redux 负责地图刷新 | 现使用 `eventBus` + Mars3D，Redux 仅缓存实体（`useEntityStream.js`） | 调用 `eventBus.emit(MAP_EVENTS.UPSERT_LAYER_ENTITY)` 执行渲染。 |
| 语音链路直通 LangGraph | 现由 Java `RealtimeAsrWebSocketHandler` 转发到 Python Agent（`RealtimeAsrWebSocketHandler.java:245-307`） | 文档需提醒检查 `agent.asr.process-url`。 |

## 7. 调试提示

1. **LangGraph**：检查 `temp/server.log` 是否出现 `rescue_scenario_publish_attempt/success`。
2. **Java**：关注 `web-api.log` 中的 `rescue_scenario_published`、`Broadcasting scenario message`。若 4xx/5xx，返回体遵守 `ApiResponse`。
3. **STOMP**：可用 `@stomp/stompjs` 直接订阅 `/topic/scenario.task.triggered` 验证 payload；连接地址 `ws://<web-api>/web-api/ws/real-time`.
4. **实体缺失**：遇到地图未刷新的情况，手动调用 `GET /web-api/api/v1/entities/by-ids` 验证 entity 是否已落库。
5. **语音**：确认 `/web-api/ws/real-time` 建立，`/user/queue/voice/response` 是否返回文字；若 `Agent处理失败`，排查 Python Agent HTTP。

通过本实录，后续在实现通知、地图实体或语音交互时，可直接定位对应仓库与函数，避免再被旧手册“假字段”“过期 Redux 逻辑”误导。
