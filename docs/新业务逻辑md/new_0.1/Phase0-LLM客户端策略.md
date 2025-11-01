# Phase 0 LLM 客户端策略

## 1. 目标
- 为不同子图/业务节点提供独立的模型 Key 或本地模型客户端；
- 删除统一并发限流依赖，改由 Key 分组实现资源隔离；
- 通过工厂模式集中管理 `LLMEndpointManager`，避免重复代码与隐式状态。

## 2. 核心实现
- 新增 `emergency_agents.llm.factory.LLMClientFactory`：
  - `get_sync(scope)` / `get_async(scope)` 面向业务作用域返回 `FailoverLLMClient`；
  - 内部缓存 `LLMEndpointManager`，保证同一作用域复用连接；
  - 作用域 → 端点映射来自 `AppConfig.llm_endpoint_groups`，若不存在则回落至 `llm_endpoints`。
- `LLMEndpointManager` 新增 `from_endpoints()`，允许直接注入端点列表，`from_config()` 改为调用该工厂方法。
- 默认并发阈值改为 `LLM_MAX_CONCURRENCY=50`（可通过环境变量覆盖），避免过高配置导致资源耗尽。
- `AppConfig` 新增字段：
  - `llm_endpoint_groups`：`dict[str, tuple[LLMEndpointConfig, ...]]`；
  - `llm_max_concurrency`：整型并发上限（默认 1000）。
  - 支持环境变量 `LLM_ENDPOINT_GROUPS`（JSON，对象，每个作用域对应端点数组）。

## 3. API 主流程调整
- `api/main.py` 初始化 `LLMClientFactory` 并派生：
  - `_llm_client_rescue = factory.get_sync("rescue")`
  - `_intent_llm_client = factory.get_sync("intent")`
  - `_llm_client_default = factory.get_sync("default")`（保留备用）
- 意图编排图 `build_intent_orchestrator_graph` 现在使用 `intent` 作用域的客户端；
- `IntentHandlerRegistry`、战术救援等流程从 `rescue` 作用域获取模型 Key；
- 仍保留 `get_openai_client()` 以兼容旧调用（如 `reports.py`），默认走 default 作用域。

## 4. 环境变量示例
```env
LLM_ENDPOINTS=[
  {"name":"glm-key-a","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"<primary-key>","priority":150}
]
LLM_ENDPOINT_GROUPS={
  "default":[{"name":"default-primary","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"<primary-key>","priority":140}],
  "rescue":[{"name":"rescue-primary","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"<rescue-key>","priority":150}],
  "intent":[{"name":"intent-primary","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"<intent-key>","priority":150}],
  "strategic":[{"name":"strategic-primary","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"<strategic-key>","priority":145}]
}
LLM_MAX_CONCURRENCY=50
```
- 若未配置 `LLM_ENDPOINT_GROUPS`，所有作用域回落到 `default`。

## 5. 影响面
- **已改造模块**：`api/main.py`、`llm/endpoint_manager.py`、`llm/client.py`（保持兼容）、`config.py`。
- **待适配模块**：后续子图（战术侦察、战略层、风险预测）在创建时需显式声明作用域，统一使用工厂取客户端。
- **测试**：现有测试需注入作用域名称或默认即可；若出现未配置作用域导致的回落，可通过新增 fixture 明确 scope。

## 6. 验证
- 单元测试：`tests/llm/test_llm_factory.py` 通过 `monkeypatch` 校验作用域→端点映射与缓存逻辑；
- FastAPI 启动日志新增 `llm_scope_manager_initialized`，可快速核对 scope 与端点列表；
- 集成测试复用原有 `intent_process` 场景，验证未显式声明作用域时回落至 `default`。

## 7. 下一步
1. 为侦察、战略、SITREP 等新子图在配置中预留作用域名称；
2. 将 `reports.py`、`agents/*` 中残余的 `get_openai_client` 替换为工厂调用，减少隐式全局状态；
3. 结合监控指标，按作用域记录 `llm_call_total`, `llm_latency_seconds`，便于定位 Key 级别问题。
