# Tasks: UI Actions 协议集成

## 阶段 1：文档和规范（Day 0，当前）

- [x] **T001** 创建 OpenSpec 提案文档
  - 验证：`openspec validate add-ui-actions-protocol --strict` 通过
  - 负责人：AI Team

- [ ] **T002** 编写 UI Actions 协议规范文档
  - 输出：`specs/ui-actions-api/spec.md`（正式规范）
  - 输出：TypeScript 类型定义文件（供前端使用）
  - 验证：前端负责人 review 通过
  - 负责人：AI Team

- [ ] **T003** 编写前端实现指南文档
  - 输出：`design.md`（ActionDispatcher 设计）
  - 输出：代码示例（Mapbox GL + Ant Design）
  - 验证：前端负责人确认可实施
  - 负责人：AI Team

---

## 阶段 2：Python 后端完善（Day 0.5，可并行）

- [ ] **T004** 补充 UI Actions 单元测试
  - 文件：`tests/ui/test_actions_serialization.py`
  - 覆盖：所有 5 种标准动作的序列化/反序列化
  - 验证：`pytest tests/ui/ -v` 通过
  - 负责人：AI Team

- [ ] **T005** 补充意图处理器集成测试
  - 文件：`tests/api/test_intent_ui_actions.py`
  - 覆盖：救援/侦察意图返回正确的 `ui_actions`
  - 验证：`pytest tests/api/test_intent_ui_actions.py -v` 通过
  - 负责人：AI Team

- [ ] **T006** 补充 API 文档（Swagger/OpenAPI）
  - 文件：`src/emergency_agents/api/main.py`（修改 FastAPI docstring）
  - 输出：`POST /intent/process` 响应体包含 `ui_actions` 字段说明
  - 验证：访问 `http://localhost:8008/docs` 可看到完整字段定义
  - 负责人：AI Team

---

## 阶段 3：前端实现（Day 1-2，关键路径）

### Day 1：核心框架 + 基础动作

- [ ] **T007** 创建 TypeScript 类型定义
  - 文件：`emergency-rescue-brain/src/types/ui-actions.ts`
  - 内容：UIAction 接口 + 5 种 Payload 接口
  - 验证：TypeScript 编译通过，无类型错误
  - 负责人：Frontend Team

- [ ] **T008** 实现 ActionDispatcher 核心类
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：解析 `ui_actions` 数组，路由到对应 handler
  - 验证：单元测试（5 种动作的 dispatch 逻辑）
  - 负责人：Frontend Team

- [ ] **T009** 实现 camera_flyto 动作处理
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：调用 Mapbox `map.flyTo()`
  - 验证：手动测试（地图飞行到指定坐标）
  - 负责人：Frontend Team

- [ ] **T010** 实现 show_toast 动作处理
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：调用 Ant Design `message.info/warning/error()`
  - 验证：手动测试（顶部显示提示）
  - 负责人：Frontend Team

- [ ] **T011** 实现 open_panel 动作处理（基础版）
  - 文件：`emergency-rescue-brain/src/components/RescuePlanPanel.tsx`
  - 功能：打开侧边栏 Drawer，显示方案 JSON 数据
  - 验证：手动测试（侧边栏打开，显示文本）
  - 负责人：Frontend Team

### Day 2：风险警告 + 地图高亮

- [ ] **T012** 实现 show_risk_warning 动作处理
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：调用 Ant Design `Modal.warning()`
  - 验证：手动测试（弹出警告弹窗）
  - 负责人：Frontend Team

- [ ] **T013** 实现风险区域地图高亮
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：根据 `risk_zones` 调用后端 API 获取几何数据，在地图上绘制红色多边形
  - 验证：手动测试（地图上显示红色区域）
  - 依赖：**需要后端提供 `/api/risk-zones/:id` 接口**
  - 负责人：Frontend Team

- [ ] **T014** 实现 focus_entity 动作处理
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：聚焦到实体坐标，闪烁实体图标
  - 验证：手动测试（地图聚焦，图标闪烁）
  - 负责人：Frontend Team

- [ ] **T015** 优化面板内容展示
  - 文件：`emergency-rescue-brain/src/components/RescuePlanPanel.tsx`
  - 功能：美化救援方案显示（任务列表、资源列表、路径警告）
  - 验证：UI 设计师 review
  - 负责人：Frontend Team

---

## 阶段 4：Java 中间件集成（Day 2-3，可并行）

- [ ] **T016** 修改 Java 意图处理代理接口
  - 文件：`emergency-web-api/src/main/java/com/cykj/controller/IntentController.java`
  - 功能：调用 Python `/intent/process` 后，透传 `ui_actions` 字段到响应体
  - 验证：集成测试（Java 响应包含 `ui_actions`）
  - 负责人：Java Team

- [ ] **T017** 补充 Java 中间件集成测试
  - 文件：`emergency-web-api/src/test/java/IntentProxyTest.java`
  - 覆盖：验证 `ui_actions` 字段正确透传
  - 验证：`mvn test` 通过
  - 负责人：Java Team

---

## 阶段 5：端到端联调（Day 3，关键路径）

- [ ] **T018** 前端接入 Java 中间件
  - 文件：`emergency-rescue-brain/src/api/intent.ts`
  - 功能：调用 Java `/web-api/intent/process` 接口
  - 验证：前端可以收到包含 `ui_actions` 的响应
  - 负责人：Frontend Team

- [ ] **T019** 前端调用 ActionDispatcher
  - 文件：`emergency-rescue-brain/src/pages/CommandCenter.tsx`
  - 功能：用户输入后，解析 `response.ui_actions` 并执行
  - 验证：手动测试（用户输入"生成救援方案"，地图飞行+侧边栏打开）
  - 负责人：Frontend Team

- [ ] **T020** 错误处理和降级
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：未知动作类型 → console.warn
  - 功能：API 失败 → Toast 错误提示
  - 验证：手动测试（模拟错误场景）
  - 负责人：Frontend Team

- [ ] **T021** 端到端测试（全链路）
  - 测试用例：
    1. 用户输入"附近有火灾，生成救援方案"
    2. 验证：地图飞行到事件坐标
    3. 验证：侧边栏打开显示救援方案
    4. 验证：顶部显示 Toast 提示
    5. 验证：地图高亮风险区域（如果有）
  - 负责人：QA Team

---

## 阶段 6：侦察扩展动作（Day 3+，可选）

- [ ] **T022** 实现 preview_route 动作处理
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：在地图上绘制侦察路线（蓝色虚线）
  - 验证：手动测试（地图显示路线）
  - 优先级：P1（次要功能）
  - 负责人：Frontend Team

- [ ] **T023** 实现 open_scout_panel 动作处理
  - 文件：`emergency-rescue-brain/src/components/ScoutPlanPanel.tsx`
  - 功能：打开侦察面板，显示设备分配
  - 验证：手动测试（侧边栏显示设备列表）
  - 优先级：P1（次要功能）
  - 负责人：Frontend Team

- [ ] **T024** 实现 show_risk_hints 动作处理
  - 文件：`emergency-rescue-brain/src/services/ActionDispatcher.ts`
  - 功能：弹出风险提示列表（Ant Design List）
  - 验证：手动测试（弹窗显示提示列表）
  - 优先级：P1（次要功能）
  - 负责人：Frontend Team

---

## 阶段 7：文档和交付（Day 3+）

- [ ] **T025** 编写前端集成文档
  - 输出：`docs/前端集成指南-UI Actions.md`
  - 内容：如何使用 ActionDispatcher、如何扩展新动作类型
  - 验证：新加入前端开发者可以快速上手
  - 负责人：Frontend Team

- [ ] **T026** 录制演示视频
  - 内容：用户输入 → AI 生成方案 → 地图自动飞行 → 侧边栏打开
  - 用途：峰会演示材料
  - 负责人：Product Team

- [ ] **T027** 归档 OpenSpec 提案
  - 命令：`openspec archive add-ui-actions-protocol --yes`
  - 验证：变更已合并到主规范
  - 负责人：AI Team

---

## 依赖关系

### 关键路径（必须顺序执行）
1. T001-T003（文档规范）→ T007-T011（前端 Day 1）→ T018-T021（联调）
2. T004-T006（Python 完善）可与 T007-T015 并行
3. T016-T017（Java 中间件）可与 T007-T015 并行

### 可并行任务
- T004-T006（Python 测试）
- T007-T015（前端实现）
- T016-T017（Java 中间件）

### 可选任务（不阻塞 MVP）
- T022-T024（侦察扩展动作）

---

## 工作量估算

| 团队 | 任务数 | 预估工时 | 实际工时 | 差异 |
|------|--------|---------|---------|------|
| AI Team | 6 | 8h | - | - |
| Frontend Team | 13 | 24h | - | - |
| Java Team | 2 | 4h | - | - |
| QA Team | 1 | 2h | - | - |
| **Total** | **22** | **38h** | - | - |

---

## 验收标准

### MVP 验收（Day 3）
- [ ] 所有 P0 任务（T001-T021）完成
- [ ] 前端可以执行 5 种标准动作
- [ ] 端到端测试通过（T021）
- [ ] 演示视频录制完成（T026）

### 完整版验收（峰会前）
- [ ] 所有任务（包括 P1 任务）完成
- [ ] 支持侦察扩展动作
- [ ] 有完整的前端集成文档
- [ ] OpenSpec 提案已归档
