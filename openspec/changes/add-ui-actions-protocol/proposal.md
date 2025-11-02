# Proposal: 添加前端 UI Actions 协议以实现战术救援/侦察交互

## Change ID
`add-ui-actions-protocol`

## Status
**Proposed** - 等待审批

## Priority
**P0** - 峰会演示核心功能，最快速度实现前端与 AI 大脑的交互

## Owner
AI Emergency Brain Team

## Created
2025-11-02

---

## 问题陈述

### 用户需求
"我现在要最快速度的完成和前端的交互，战术救援和战术侦察，还有风险提醒"

### 当前状态
- ✅ **Python 后端已完成**：`RescueTacticalGraph` 和 `ScoutTacticalGraph` 已实现完整的 LangGraph 状态机
- ✅ **UI Actions 协议已定义**：`src/emergency_agents/ui/actions.py` 提供了 5 种标准动作类型
- ✅ **意图处理器已返回动作队列**：`POST /intent/process` 接口返回 `ui_actions` 字段

### 核心瓶颈
- ❌ **前端缺少 Action Dispatcher**：无法解析和执行 `ui_actions` 队列
- ❌ **前端缺少协议文档**：不知道如何正确消费 Python 返回的动作数据
- ❌ **Java 中间件未集成**：需要透传 `ui_actions` 字段到前端

---

## 解决方案概述

### 核心变更
1. **正式化 UI Actions 协议规范**
   - 定义 5 种标准动作类型的完整数据结构（camera_flyto, open_panel, show_toast, show_risk_warning, focus_entity）
   - 定义 3 种侦察子图扩展动作（preview_route, open_scout_panel, show_risk_hints）
   - 提供 TypeScript 类型定义和 JSON 示例

2. **明确 API 接口契约**
   - `POST /intent/process` 响应体中的 `ui_actions` 字段结构
   - Java 中间件需透传的字段清单
   - 错误处理和降级策略

3. **提供前端实现指南**
   - Action Dispatcher 核心代码示例（TypeScript + React）
   - 每种动作类型的地图/UI 组件实现参考（Mapbox GL + Ant Design）
   - 3 天 MVP 实施计划

### 实施路径（3 天 MVP）
- **Day 1**: Action Dispatcher + 相机控制 + Toast 提示 + 基础面板
- **Day 2**: 风险警告可视化 + 地图高亮
- **Day 3**: Java 中间件集成 + 全链路联调

---

## 影响范围

### 新增能力
- ✅ 前端可以响应 AI 大脑的 UI 指令（相机飞行、打开面板、显示提示）
- ✅ 地图可以自动高亮风险区域
- ✅ 用户可以看到实时的救援/侦察方案

### 修改的系统
1. **emergency-rescue-brain (前端)**
   - 新增 `ActionDispatcher` 类
   - 新增 UI Actions 处理逻辑
   - 修改地图组件支持动作触发

2. **emergency-web-api (Java 中间件)**
   - 修改 `/intent/process` 代理接口
   - 透传 `ui_actions` 字段

3. **emergency-agents-langgraph (AI 大脑)**
   - **无代码修改**（协议已实现）
   - 仅新增文档和测试

### 不影响的功能
- ✅ 现有 Python 后端逻辑 100% 保持不变
- ✅ 现有意图识别流程 100% 保持不变
- ✅ 现有 LangGraph 状态机 100% 保持不变

---

## 技术决策

### 为什么选择这个协议设计
1. **已在生产验证**：协议代码已在 `src/emergency_agents/ui/actions.py` 运行，非新增设计
2. **强类型安全**：使用 Python `@dataclass` 和 TypeScript `interface` 确保类型一致性
3. **向后兼容**：`raw_action` 类型支持未来扩展动作类型
4. **前端无关**：协议与前端框架解耦，支持 React/Vue/任意框架

### 为什么不使用 WebSocket
1. **简化集成**：HTTP 接口更容易接入，无需维护连接状态
2. **已有基建**：Java 中间件已提供 HTTP 代理，无需新增 WebSocket 网关
3. **满足需求**：当前场景下 HTTP 轮询（或单次调用）已足够

### 为什么是 3 天 MVP
1. **Day 1 可验证**：每天都有可演示的进展
2. **Day 2 有效果**：风险警告是峰会演示的核心亮点
3. **Day 3 可上线**：全链路联调后可直接用于演示

---

## 风险和缓解

### 风险 1：前端团队不熟悉协议
**缓解**：
- 提供完整的 TypeScript 类型定义
- 提供 ActionDispatcher 示例代码
- 提供每种动作的 Mapbox GL + Ant Design 实现参考

### 风险 2：Java 中间件遗漏字段
**缓解**：
- 明确列出需要透传的字段清单（`ui_actions`, `intent`, `result`）
- 提供集成测试用例

### 风险 3：3 天时间不够
**缓解**：
- Day 1 可独立验证（相机控制 + Toast）
- Day 2 可独立验证（风险警告）
- Day 3 仅做联调，无核心开发

---

## 成功标准

### MVP 验收标准
- [ ] 前端可以解析 `ui_actions` 字段并执行 5 种标准动作
- [ ] 地图可以根据 `camera_flyto` 动作飞行到指定坐标
- [ ] 地图可以根据 `show_risk_warning` 动作高亮风险区域
- [ ] 用户输入"生成救援方案"后可以看到侧边栏打开并显示方案详情
- [ ] 所有动作都有 console.log 追踪日志（用于调试）

### 完整版验收标准（峰会前）
- [ ] 支持所有 5 种标准动作 + 3 种侦察扩展动作
- [ ] Java 中间件成功透传所有字段
- [ ] 前端有错误处理（未知动作类型 / API 失败 / 网络超时）
- [ ] 有端到端测试用例（Cypress / Playwright）

---

## 后续工作

### 不包含在此变更中（需要后续 Proposal）
1. **WebSocket 实时推送**（当前使用 HTTP 轮询）
2. **战略层集成**（当前仅支持战术层）
3. **动作撤销/重做**（当前仅支持单向执行）
4. **动作队列优化**（当前顺序执行，未来可并行）

---

## 依赖关系

### 前置依赖（已完成）
- ✅ `src/emergency_agents/ui/actions.py` - UI Actions 协议实现
- ✅ `src/emergency_agents/graph/rescue_tactical_app.py` - 救援战术图
- ✅ `src/emergency_agents/graph/scout_tactical_app.py` - 侦察战术图
- ✅ `POST /intent/process` - 意图处理接口

### 后续依赖（需要此变更完成后）
- emergency-rescue-brain 前端实现 ActionDispatcher
- emergency-web-api Java 中间件透传字段

---

## 参考文档

1. **原始需求文档**：`docs/新业务逻辑md/new_0.1/前端集成OpenSpec提案-战术救援侦察UI Actions协议.md`
2. **协议实现代码**：`src/emergency_agents/ui/actions.py`
3. **救援处理器代码**：`src/emergency_agents/intent/handlers/rescue_task_generation.py`
4. **侦察处理器代码**：`src/emergency_agents/intent/handlers/scout_task_generation.py`

---

## 审批记录

- **提案创建**：2025-11-02
- **等待审批**：前端负责人、Java 负责人、AI 负责人
