# GLM-4.6 模型 API Key 配置说明

## 🔍 当前使用的API Key

### glm-4.6 模型使用的 Key

**API Key**: `854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8`

**Key名称**: `LLM_KEY_PRIMARY` (主通道Key)

**Base URL**: `https://open.bigmodel.cn/api/paas/v4`

---

## 📋 配置加载流程

### 1. 启动脚本加载顺序

**文件**: `scripts/dev-run.sh`

```bash
# 第19-20行
source config/llm_keys.env    # 先加载Key定义
source config/dev.env          # 再加载配置（使用Key变量）
```

---

### 2. Key定义文件

**文件**: `config/llm_keys.env` (第11行)

```bash
LLM_KEY_PRIMARY=854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8
```

**说明**: 这是主通道Key，用于实时意图识别、方案生成等核心功能

---

### 3. 配置引用

**文件**: `config/dev.env` (第21行)

```bash
OPENAI_API_KEY=${LLM_KEY_PRIMARY}
```

**说明**: 使用Shell变量展开，将 `LLM_KEY_PRIMARY` 的值赋给 `OPENAI_API_KEY`

---

### 4. 代码使用

**文件**: `src/emergency_agents/api/reports.py` (第382-388行)

```python
llm_client = get_openai_client(cfg)  # 使用 cfg.openai_api_key

completion = llm_client.chat.completions.create(
    model="glm-4.6",  # 硬编码使用 glm-4.6 模型
    # ...
)
```

**文件**: `src/emergency_agents/config.py` (第107行)

```python
openai_api_key = os.getenv("OPENAI_API_KEY", "dummy")
```

---

## 🔑 所有可用的API Key

**文件**: `config/llm_keys.env`

| Key名称 | 值 | 用途 |
|---------|-----|------|
| `LLM_KEY_PRIMARY` | `854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8` | **主通道** - 实时意图、方案生成、报告生成 |
| `LLM_KEY_SECONDARY` | `b33ffec2c17644bea471bf4071a55a25.9svQ5VbP36wrAdMF` | **第二通道** - 熔断备用 |
| `LLM_KEY_TERTIARY` | `9c63e91657be424995b84bcd49646ef5.0pr9fRxzz2TLIZ8t` | **第三通道** - 进一步分摊限流 |
| `LLM_KEY_LEGACY` | `3116c00e0d32439e90c86a2bc12167ac.58CvdyQCLJyrKf5S` | **兜底通道** - 全部不可用时使用 |
| `LLM_KEY_RECON` | `9c63e91657be424995b84bcd49646ef5.0pr9fRxzz2TLIZ8t` | **侦察通道** - 同TERTIARY |
| `MEM0_OPENAI_KEY` | `55be5042f7e44535a62e24721b28d039.27obcTHfO2ULZiQl` | **Mem0专用** - 避免与主流程抢额度 |

---

## 🎯 救援评估报告API具体使用情况

### 当前配置

```
报告生成接口: POST /reports/rescue-assessment
模型: glm-4.6
API Key: 854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8 (LLM_KEY_PRIMARY)
Base URL: https://open.bigmodel.cn/api/paas/v4
```

### 调用链路

```
1. 用户请求 → POST /reports/rescue-assessment

2. reports.py:382
   llm_client = get_openai_client(cfg)

3. llm/client.py:83-86
   cfg = AppConfig.load_from_env()
   manager = LLMEndpointManager.from_config(cfg)

4. config.py:107
   openai_api_key = os.getenv("OPENAI_API_KEY")
   # 此时 OPENAI_API_KEY = "854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8"

5. reports.py:387-388
   completion = llm_client.chat.completions.create(
       model="glm-4.6",  # 硬编码模型名
       ...
   )
```

---

## 🔄 故障转移机制

### LLM Endpoint Manager

**配置**: `config/dev.env` (第35行)

```bash
LLM_ENDPOINTS=[
  {"name":"glm-key-a","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"${LLM_KEY_PRIMARY}","priority":150},
  {"name":"glm-key-b","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"${LLM_KEY_SECONDARY}","priority":140},
  {"name":"glm-key-c","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"${LLM_KEY_TERTIARY}","priority":130},
  {"name":"glm-key-legacy","base_url":"https://open.bigmodel.cn/api/paas/v4","api_key":"${LLM_KEY_LEGACY}","priority":120},
  {"name":"intranet-gateway","base_url":"http://192.168.31.40/v1","api_key":"${LLM_KEY_PRIMARY}","priority":90}
]
```

### 优先级顺序

1. **优先级150** - glm-key-a (LLM_KEY_PRIMARY) ← **当前使用**
2. 优先级140 - glm-key-b (LLM_KEY_SECONDARY)
3. 优先级130 - glm-key-c (LLM_KEY_TERTIARY)
4. 优先级120 - glm-key-legacy (LLM_KEY_LEGACY)
5. 优先级90 - intranet-gateway (内网网关)

**故障转移**: 当主Key失败时，自动切换到次优先级Key

---

## 🔧 如何修改API Key

### 方式1：修改主Key（推荐）

**文件**: `config/llm_keys.env`

```bash
# 修改第11行
LLM_KEY_PRIMARY=新的API_KEY
```

**影响范围**: 所有使用 PRIMARY Key 的服务

**重启服务**: 必须

---

### 方式2：为报告API指定专用Key

**文件**: `config/llm_keys.env` (新增)

```bash
LLM_KEY_REPORTS=新的专用KEY
```

**文件**: `config/dev.env` (新增)

```bash
REPORTS_API_KEY=${LLM_KEY_REPORTS}
```

**文件**: `src/emergency_agents/api/reports.py` (修改)

```python
# 第382行修改为：
from openai import OpenAI

llm_client = OpenAI(
    base_url="https://open.bigmodel.cn/api/paas/v4",
    api_key=os.getenv("REPORTS_API_KEY")
)
```

**优点**:
- 独立配置，不影响其他服务
- 可以使用不同的限额配置
- 便于成本核算

---

### 方式3：临时测试（不推荐生产使用）

```bash
# 临时设置环境变量
export OPENAI_API_KEY="临时测试KEY"

# 启动服务
./scripts/dev-run.sh
```

---

## 📊 Key使用监控

### 查看当前使用的Key

```bash
# 查看环境变量
echo $OPENAI_API_KEY

# 查看实际加载的配置
grep OPENAI_API_KEY config/dev.env

# 查看Key定义
grep LLM_KEY_PRIMARY config/llm_keys.env
```

### 智谱AI控制台

1. 登录 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 进入"控制台" → "API Keys"
3. 查看 `854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8` 的使用情况：
   - 调用次数
   - Token消耗
   - 余额/配额
   - 错误率

---

## ⚠️ 安全注意事项

### 1. Key保护

- ✅ `config/llm_keys.env` 已加入 `.gitignore`
- ✅ 不会提交到Git仓库
- ⚠️ 不要在日志中打印完整Key
- ⚠️ 不要在公开文档中暴露Key

### 2. Key轮换

建议定期（如每季度）轮换API Key：

```bash
# 1. 在智谱AI控制台生成新Key
# 2. 更新 llm_keys.env
# 3. 重启服务
# 4. 验证服务正常
# 5. 删除旧Key
```

### 3. 最小权限原则

- 生产环境使用独立Key
- 开发/测试环境共享Key
- 限制单个Key的调用速率
- 设置消费预警

---

## 🧪 验证配置

### 测试API Key是否有效

```bash
# 方法1：使用curl直接测试
curl -X POST https://open.bigmodel.cn/api/paas/v4/chat/completions \
  -H "Authorization: Bearer 854f678ad24645b89b4bc27b94d29b58.Ne5Ep2W60GDPT7B8" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4.6",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 方法2：调用报告API测试
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/rescue_assessment_minimal_input.json

# 方法3：查看服务日志
tail -f temp/server.log | grep -i "openai\|glm"
```

---

## 📝 常见问题

### Q1: 如何确认当前使用的Key？

```bash
# 查看启动脚本加载的环境变量
source config/llm_keys.env
source config/dev.env
echo "当前使用的Key: $OPENAI_API_KEY"
```

### Q2: Key失效怎么办？

1. 检查智谱AI控制台，确认Key是否过期
2. 检查余额/配额是否充足
3. 更换到备用Key（LLM_KEY_SECONDARY）
4. 查看服务日志的错误信息

### Q3: 如何切换到其他Key？

```bash
# 修改 config/dev.env 第21行
# 从:
OPENAI_API_KEY=${LLM_KEY_PRIMARY}

# 改为:
OPENAI_API_KEY=${LLM_KEY_SECONDARY}

# 重启服务
pkill -f uvicorn
./scripts/dev-run.sh
```

### Q4: 为什么日志中看不到完整Key？

为了安全，日志中只显示Key的前8位和后4位：

```
使用Key: 854f678a...7B8
```

---

## 📅 维护记录

| 日期 | 操作 | 操作人 |
|------|------|--------|
| 2025-11-03 | 确认救援评估API使用 LLM_KEY_PRIMARY | Claude Code |
| 2025-11-03 | 创建本配置说明文档 | Claude Code |

---

**文档版本**: v1.0
**最后更新**: 2025-11-03
**维护者**: AI应急大脑项目组
