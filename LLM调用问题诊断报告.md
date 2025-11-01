# LLM调用问题诊断报告

## 问题现象
WebSocket语音输入后，系统没有正常返回LLM响应，表现为长时间等待后失败。

---

## 关键发现：代码正常，API限流问题

**✅ 代码层面没有问题**：
- LLM调用代码已正常执行（有 `llm_call_starting` 日志）
- 输入数据正常（`input_preview: '帮我看一下汶川地震的实际情况。'`）
- 空白输入过滤已修复并工作正常

**❌ 智谱AI API限流问题**：
```
Error code: 429 - {'error': {'code': '1302', 'message': '您当前使用该API的并发数过高，请降低并发，或联系客服增加限额。'}}
```

---

## 如何查看日志

### 方法1：查看完整日志文件
```bash
tail -100 /home/msq/gitCode/new_1/emergency-agents-langgraph/temp/server.log
```

### 方法2：过滤关键日志（推荐）
```bash
# 查看意图处理流程
tail -200 temp/server.log | grep -E "intent_processing_start|unified_intent_start|llm_call_starting|llm_call_completed|llm_endpoint_failure"

# 查看API错误
tail -200 temp/server.log | grep -E "429|1302|error"

# 实时监控日志
tail -f temp/server.log | grep --color -E "llm_call_starting|llm_endpoint_failure|429"
```

### 方法3：查看特定时间段日志
```bash
# 查看最近的LLM调用失败
grep "llm_endpoint_failure" temp/server.log | tail -10

# 查看endpoint状态变化
grep "llm_endpoint" temp/server.log | tail -20
```

---

## 关键日志时间线（11:28-11:29）

```
11:28:57 [info] intent_processing_start
         ↓
11:28:58 [info] mem0_disabled (Mem0已禁用，正常)
         ↓
11:28:58 [info] unified_intent_start (统一意图识别开始)
         input_preview='帮我看一下汶川地震的实际情况。'
         llm_model='glm-4.5-air'
         ↓
11:28:58 [info] llm_call_starting (LLM调用正常发起 ✅)
         model='glm-4.5-air'
         temperature=0
         messages_count=1
         ↓
11:29:41 [warning] llm_endpoint_failure (第1次失败 - 43秒后)
         error="Error code: 429 - code='1302' message='并发数过高'"
         failure_count=1
         latency_ms=43321
         ↓
11:29:43 [warning] llm_endpoint_failure (第2次重试失败 - 2秒后)
         error="Error code: 429 - code='1302' message='并发数过高'"
         failure_count=2
         marked_unavailable=True ← endpoint被熔断
         recovery_at=1761708643 (60秒后恢复)
         ↓
11:29:43 [warning] llm_all_endpoints_unavailable
         fallback=primary (只有1个endpoint)
```

---

## 根本原因

### 1. API配额限制
智谱AI GLM-4.5-air API返回429错误：
- **错误代码**: 1302
- **错误信息**: "您当前使用该API的并发数过高，请降低并发，或联系客服增加限额"
- **影响**: 请求被拒绝，无法获得响应

### 2. 可能的触发原因
- 同一API Key在多处使用（开发环境、测试、生产）
- 短时间内大量请求（健康检查、并发测试等）
- API账户免费配额的并发限制（通常为1-2个并发）

### 3. 熔断机制正常工作
```python
failure_threshold=2  # 连续2次失败触发熔断
recovery_seconds=60  # 60秒后重试
```
- 第1次失败：记录但继续重试
- 第2次失败：endpoint标记为unavailable
- 60秒后：自动进入半开状态，允许试探性请求

---

## 配置信息

### 当前LLM配置（config/dev.env）
```bash
LLM_MODEL=glm-4.5-air
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_API_KEY=4c41ca86303d47768bc647d2f8c650a0.UT20LSESEeOkaehD

# Endpoint配置
LLM_ENDPOINTS=[
  {
    "name":"glm-official",
    "base_url":"https://open.bigmodel.cn/api/paas/v4",
    "api_key":"4c41ca86303d47768bc647d2f8c650a0.UT20LSESEeOkaehD",
    "priority":120
  },
  {
    "name":"intranet-gateway",
    "base_url":"http://8.147.130.215/v1",
    "api_key":"4c41ca86303d47768bc647d2f8c650a0.UT20LSESEeOkaehD",
    "priority":90
  }
]

LLM_FAILURE_THRESHOLD=2
LLM_RECOVERY_SECONDS=60
```

### 问题分析
- 配置了2个endpoint（glm-official优先级更高）
- 但两个endpoint使用**相同的API Key**
- 如果主endpoint限流，备用endpoint也会失败（共享配额）

---

## 建议解决方案

### 方案1：申请提高并发配额（推荐）
联系智谱AI客服：
1. 说明使用场景（应急救援语音对话系统）
2. 申请提高并发数限制（建议至少5-10个并发）
3. 如果是付费账户，考虑升级套餐

### 方案2：降低并发请求
```bash
# 临时关闭其他使用相同API Key的服务
# 检查是否有后台测试、健康检查等在同时调用

# 停止不必要的服务
ps aux | grep pytest  # 检查是否有测试在运行
ps aux | grep uvicorn  # 检查是否有多个服务实例
```

### 方案3：使用不同的API Key
为不同环境配置不同的API Key：
```bash
# 开发环境
OPENAI_API_KEY=dev_key_xxx

# 测试环境
OPENAI_API_KEY=test_key_xxx

# 生产环境
OPENAI_API_KEY=prod_key_xxx
```

### 方案4：添加请求队列和限流
在代码中添加本地限流：
```python
# 在 endpoint_manager.py 中添加
import asyncio
from asyncio import Semaphore

class LLMEndpointManager:
    def __init__(self, ..., max_concurrent=1):
        self._semaphore = Semaphore(max_concurrent)

    async def call_async(self, ...):
        async with self._semaphore:
            # 原有逻辑
```

### 方案5：切换到其他模型
如果主模型持续限流，考虑：
- GLM-4-Flash（更快，配额可能不同）
- GLM-4-Plus（更强，付费账户配额更高）
- 本地部署的开源模型（无限流问题）

---

## 验证方法

### 1. 检查API配额状态
```bash
curl -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" \
  -H "Authorization: Bearer 4c41ca86303d47768bc647d2f8c650a0.UT20LSESEeOkaehD" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4.5-air",
    "messages": [{"role": "user", "content": "测试"}],
    "temperature": 0
  }'
```

如果返回429，说明确实是配额问题。

### 2. 等待60秒后重试
endpoint熔断60秒后会自动恢复，可以测试：
```bash
# 等待60秒
sleep 60

# 重新测试
curl http://localhost:8008/healthz
```

### 3. 查看endpoint恢复日志
```bash
# 监控endpoint恢复
tail -f temp/server.log | grep -E "half_open|recovery_at|llm_endpoint_success"
```

---

## 当前系统状态

### ✅ 已修复的问题
1. API Key已更新
2. ASR空白输入过滤已实现
3. Mem0已临时禁用（避免Neo4j依赖）
4. LLM超时配置已优化（60秒详细配置）

### ❌ 待解决的问题
1. **API并发限流** - 核心阻塞问题
2. Neo4j认证（如需重新启用Mem0）

### 📊 服务状态
- 服务运行：✅ localhost:8008
- 健康检查：✅ {"status":"ok"}
- ASR服务：✅ 阿里云主Provider健康
- LLM Endpoint：⚠️ 因429错误被熔断

---

## 相关文件位置

```
配置文件：
  config/dev.env                               # 环境配置

代码文件：
  src/emergency_agents/llm/endpoint_manager.py # LLM端点管理
  src/emergency_agents/intent/unified_intent.py # 统一意图识别
  src/emergency_agents/api/voice_chat.py        # 语音WebSocket

日志文件：
  temp/server.log                               # 运行日志
  temp/uvicorn.pid                              # 进程ID

测试脚本：
  tests/intent/test_unified_intent_integration.py
```

---

## 联系智谱AI客服

**官方渠道**：
- 官网：https://open.bigmodel.cn
- 工单系统：控制台 → 工单中心
- 企业微信/钉钉：在线客服

**需要提供信息**：
- API Key: `4c41ca86303d47768bc647d2f8c650a0.UT20LSESEeOkaehD`
- 错误代码: `1302`
- 使用场景: 应急救援AI对话系统
- 预计并发: 5-10个请求
