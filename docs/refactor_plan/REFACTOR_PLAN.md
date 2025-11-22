# Linus 式代码重构方案：去伪存真 (The Purge & Refactor)

## 1. 核心问题诊断 (Diagnosis)

当前代码库存在严重的**过度设计 (Over-Engineering)** 和**架构宇航员 (Architecture Astronaut)** 倾向。

1.  **图的通货膨胀 (Graph Proliferation)**: `main.py` 中初始化了 7 个不同的 LangGraph 实例。简单的线性逻辑（如意图识别）被强行封装为复杂的图结构，增加了维护成本和延迟，却未带来状态管理的实际价值。
2.  **上帝对象与依赖地狱 (God Object & Dependency Hell)**: `main.py` 充当了全局垃圾场，初始化所有依赖并层层透传。`IntentHandlerRegistry` 构造函数需要 16 个参数，表明抽象层完全泄露。
3.  **代码复制粘贴 (Boilerplate)**: 核心智能体（`situation.py`, `risk_predictor.py` 等）共享几乎完全相同的代码模式（检查幂等性 -> 构造 Prompt -> 调用 LLM -> 解析 JSON -> 记日志），缺乏统一抽象。
4.  **虚假的执行 (Fake Execution)**: `execute_node` 仅记录日志，未与 `vehicle` 模块的物理执行接口真正连接，导致系统停留在"文本生成器"阶段。

---

## 2. 重构行动计划 (Action Plan)

### 第一阶段：屠杀 (The Purge) - 简化架构

**目标**: 删除不必要的图，回归简单函数调用。

1.  **废除 `IntentGraph`**:
    *   **动作**: 删除 `src/emergency_agents/graph/intent_orchestrator_app.py`。
    *   **替代**: 在 `src/emergency_agents/intent/pipeline.py` 中实现一个纯 Python 函数管道：
        ```python
        async def process_intent_pipeline(input: str, context: Context) -> IntentResult:
            intent = await classifier.classify(input)
            intent = await validator.validate(intent)
            return await router.route(intent)
        ```
    *   **理由**: 意图识别是无状态的线性流程，不需要 Checkpoint，也不需要图编排。

2.  **合并救援图谱**:
    *   **动作**: 废除 `SimpleRescueGraph`，将其逻辑合并入主 `RescueGraph`。
    *   **替代**: 在 `RescueGraph` 中通过条件分支处理简易模式与完整模式。
    *   **理由**: "There should be one way to do it." 维护两套相似的图是重复劳动的根源。

### 第二阶段：封装 (Encapsulate) - 清理依赖

**目标**: 将 `main.py` 从 700 行缩减至 100 行，解耦依赖注入。

1.  **引入 `ServiceContainer`**:
    *   **动作**: 创建 `src/emergency_agents/container.py`。
    *   **内容**: 使用单例模式或简单的依赖容器管理 DB Pool, LLM Clients, KG Service 等。
    *   **效果**: `main.py` 不再负责初始化 16 个参数，只需 `container.init()`。

2.  **标准化智能体 (The Agent Node)**:
    *   **动作**: 创建 `src/emergency_agents/agents/base.py` 定义 `LLMAgentNode` 基类。
    *   **功能**: 统一封装以下逻辑：
        *   幂等性检查 (Idempotency Check)
        *   Prompt 渲染 (Jinja2/f-string)
        *   LLM 调用与重试 (Retry Logic)
        *   JSON 解析与容错 (Robust Parsing)
        *   审计日志 (Audit Logging)
    *   **重构**: 将 `situation.py`, `risk_predictor.py` 等重写为继承自该基类的轻量级配置类。

### 第三阶段：连接 (Connect) - 实现闭环

**目标**: 让大脑指挥手脚。

1.  **真实执行层**:
    *   **动作**: 重写 `src/emergency_agents/graph/nodes/execute.py`。
    *   **逻辑**: 解析 `proposals` 中的 Action，通过 `AdapterHubClient` 发送实际指令（如 HTTP 请求调用无人机控制台）。
    *   **接口**: 定义明确的 `ActionExecutor` 接口，支持 Mock（测试用）和 Real（生产用）实现。

---

## 3. 预期收益 (Expected Outcome)

1.  **代码量减少 30%**: 删除冗余的图定义和胶水代码。
2.  **可测试性提升**: 依赖容器化后，单元测试可以轻松 Mock 外部服务。
3.  **开发效率倍增**: 新增智能体只需继承基类并编写 Prompt，无需复制粘贴 100 行样板代码。
4.  **系统真实落地**: 从"聊天机器人"进化为真正的"应急指挥控制系统"。

## 4. 执行顺序

1.  **Refactor `main.py`**: 引入 `ServiceContainer`，止血。
2.  **Standardize Agents**: 提取 `LLMAgentNode`，消除重复。
3.  **Delete `IntentGraph`**: 简化意图识别流程。
4.  **Implement Execution**: 连接物理层接口。
