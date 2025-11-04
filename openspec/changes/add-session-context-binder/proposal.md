# Proposal: add-session-context-binder

Intent: 将“多轮上下文记忆 + 槽位缺失结构化澄清”以最小改动落地到现有 LangGraph 应用，保持强类型与不兜底原则。

Goals
- 结构化澄清（ClarifyRequest）：当 `video-analysis` 缺少 `device_name` 时，以 options+default_index 方式发起中断/交互；API 无中断时也能返回 `needs_input` + `ui_actions`。
- 会话记忆（Session Context）：记录每个 `thread_id` 最近一次使用的设备，后续澄清选项中置顶展示；成功执行后写回。严格不自动猜测，仅排序与默认值。

Non-Goals
- 不引入另一对话栈（如 Rasa）；不改变既有 API 语义。
- 不开启“自动填充并跳过澄清”的冒进逻辑，先以“排序+默认项”保守上线。

Risks
- 新增同步 DB 查询阻塞事件循环：本变更避免新增同步调用，统一通过 `AsyncConnectionPool` 的服务注入（ContextService）。
- 记忆表未创建：SQL 由运维执行；未创建仅影响选项排序，不影响澄清本身。

