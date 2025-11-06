# 侦察任务Python端测试指南

## 测试目标

验证侦察任务完整流程（Java后端API暂时用TODO占位）：
- ✅ 意图识别：正确识别SCOUT_TASK_SIMPLE意图
- ✅ 坐标提取：支持多种格式（103.8,31.6 / (103.8,31.6) / 东经103度48分北纬31度36分等）
- ✅ 数据库查询：查询is_selected=1的设备列表
- ✅ LLM设备选择：基于产品功能详情分析生成1-3条专业理由（传感器、续航、防护等级等）
- ✅ 用户确认：返回格式"已选择XX（理由1；理由2；...）执行侦察任务..."
- ✅ 状态更新：成功返回dispatch_id和状态

## 前置准备

### 1. 执行测试数据SQL

```bash
# 连接到PostgreSQL数据库
psql -h 8.147.130.215 -p 19532 -U postgres -d emergency_agent

# 执行测试数据脚本
\i /home/msq/gitCode/new_1/emergency-agents-langgraph/sql/test_data_scout_devices.sql

# 验证数据插入成功（应该看到3个设备）
SELECT d.id, d.name, d.device_type, d.weather_capability, c.is_selected
FROM operational.device d
JOIN operational.car_device_select c ON d.id = c.device_id
WHERE c.is_selected = 1;
```

预期输出：
```
  id  |        name        | device_type | weather_capability | is_selected
------+--------------------+-------------+--------------------+-------------
 9001 | 大疆 Mavic 3E      | UAV         | 全天候             |           1
 9002 | 大疆 Matrice 30T   | UAV         | 全天候             |           1
 9003 | 道通 EVO Max 4T    | UAV         | 晴天               |           1
```

### 2. 确认环境配置

检查 `config/dev.env` 文件：

```bash
# PostgreSQL连接（用于设备查询）
POSTGRES_DSN=postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent

# LLM服务（用于意图识别和设备选择）
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_API_KEY=你的API密钥
LLM_MODEL=glm-4-flash

# Web API地址（当前暂不使用，用TODO占位）
WEB_API_BASE_URL=http://localhost:28080/web-api
```

### 3. 启动服务

```bash
cd /home/msq/gitCode/new_1/emergency-agents-langgraph

# 后台启动服务
./scripts/dev-run.sh

# 查看启动日志
tail -f temp/server.log

# 健康检查
curl http://localhost:8008/healthz
```

## 测试用例

### 测试用例1：标准格式坐标

**输入**：
```bash
curl -X POST http://localhost:8008/api/v1/intent/handle \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-scout-001",
    "user_id": "commander-01",
    "channel": "text",
    "raw_text": "到103.8、31.6侦察现场态势"
  }'
```

**预期流程**：
1. 意图识别：SCOUT_TASK_SIMPLE
2. 坐标提取：lng=103.8, lat=31.6
3. 槽位验证：通过（coordinates有效）
4. 路由决策：进入scout_dispatch分支
5. 查询设备：返回3个设备
6. LLM选择：选择其中1个设备，生成3条理由
7. **中断等待用户确认**

**预期响应**（第一次调用）：
```json
{
  "status": "interrupted",
  "message": "已选择 大疆 Mavic 3E（配备4/3英寸CMOS传感器，可获取2000万像素高清影像，满足现场细节识别需求；43分钟最大续航时间，足以完成中长距离侦察任务；IP55防护等级，支持雨天等恶劣环境作业）执行侦察任务，目标位置：纬度31.600000°、经度103.800000°，任务：侦察现场态势。是否确认派遣？",
  "thread_id": "test-scout-001",
  "next_action": "await_confirmation"
}
```

**说明**：理由数量为1-3条，基于产品功能详情分析生成，包含传感器配置、续航时间、防护等级等专业参数，听起来像真实产品规格分析。

**用户确认**：
```bash
curl -X POST http://localhost:8008/api/v1/intent/handle \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-scout-001",
    "user_id": "commander-01",
    "channel": "text",
    "raw_text": "确认",
    "resume": true
  }'
```

**预期响应**（确认后）：
```json
{
  "status": "completed",
  "scout_result": {
    "status": "dispatched",
    "device_name": "大疆 Mavic 3E",
    "dispatch_id": "simple-scout-xxxxx-xxxx-xxxx"
  },
  "timeline": [
    {"event": "scout_dispatched", "device_name": "大疆 Mavic 3E", "dispatch_id": "simple-scout-xxxxx"}
  ]
}
```

**关键日志验证**：
```bash
tail -f temp/server.log | grep -E "scout_fetch_devices|scout_llm_selection|scout_awaiting_confirmation|scout_dispatch_simulated_success"
```

预期看到：
```
scout_fetch_devices_start
scout_fetch_devices_success device_count=3
scout_llm_selection_request
scout_llm_selection_success device_name="大疆 Mavic 3E"
scout_awaiting_confirmation device_name="大疆 Mavic 3E"
scout_dispatch_api_call_skipped_for_testing reason="java_backend_not_ready"
scout_dispatch_simulated_success device_name="大疆 Mavic 3E"
```

### 测试用例2：括号格式坐标

**输入**：
```bash
curl -X POST http://localhost:8008/api/v1/intent/handle \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-scout-002",
    "user_id": "commander-01",
    "channel": "text",
    "raw_text": "侦察(103.8, 31.6)位置"
  }'
```

**预期**：应正确提取coordinates并进入确认流程。

### 测试用例3：度分秒格式坐标

**输入**：
```bash
curl -X POST http://localhost:8008/api/v1/intent/handle \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-scout-003",
    "user_id": "commander-01",
    "channel": "text",
    "raw_text": "去东经103度48分、北纬31度36分侦察"
  }'
```

**预期**：LLM应将度分秒转换为十进制（103.8, 31.6）。

### 测试用例4：缺少坐标（错误场景）

**输入**：
```bash
curl -X POST http://localhost:8008/api/v1/intent/handle \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-scout-004",
    "user_id": "commander-01",
    "channel": "text",
    "raw_text": "侦察现场态势"
  }'
```

**预期响应**：
```json
{
  "status": "validation_failed",
  "message": "请提供侦察目标的位置信息，例如：'到东经103.8度、北纬31.6度侦察'",
  "missing_fields": ["coordinates"]
}
```

## 验证检查清单

### 功能验证
- [ ] 意图识别正确（SCOUT_TASK_SIMPLE）
- [ ] 坐标提取支持多种格式
- [ ] 数据库查询返回3个设备
- [ ] LLM选择1个设备并生成1-3条专业理由（基于产品功能详情分析）
- [ ] 理由包含专业参数（传感器配置、续航时间、防护等级、避障系统、图传距离等）
- [ ] 理由听起来可信且专业，像是分析真实产品规格书得出
- [ ] 确认消息格式正确（理由在括号内，用分号分隔）
- [ ] 用户确认后状态更新正确
- [ ] 返回有效的dispatch_id

### 日志验证
- [ ] scout_fetch_devices_success 记录设备数量
- [ ] scout_llm_selection_success 记录选中设备
- [ ] scout_awaiting_confirmation 记录等待确认
- [ ] scout_dispatch_api_call_skipped_for_testing **警告日志**（TODO占位）
- [ ] scout_dispatch_simulated_success 记录模拟成功

### 错误处理验证
- [ ] 缺少坐标时返回友好提示（无技术术语）
- [ ] 数据库连接失败时有明确日志
- [ ] LLM调用失败时有异常处理

## 已知限制（TODO占位部分）

1. **Java后端API调用已注释**
   - 位置：`router.py:357-358`
   - 状态：用 `logger.warning` 记录跳过原因
   - 恢复方法：取消注释第358行即可

2. **实际设备派遣不会执行**
   - 测试阶段只验证Python流程逻辑
   - 不会真正调用 `/api/v1/scout/scenario` 接口
   - 前端不会收到侦察任务通知

## 故障排查

### 问题1：设备查询返回空列表

**症状**：日志显示 `scout_fetch_devices_success device_count=0`

**原因**：数据库没有is_selected=1的设备

**解决**：重新执行测试数据SQL脚本

### 问题2：LLM选择失败

**症状**：日志显示 `scout_llm_selection_failed`

**原因**：LLM API调用失败或返回格式错误

**检查**：
```bash
# 测试LLM连接
curl -X POST "$OPENAI_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"hi"}]}'
```

### 问题3：坐标提取失败

**症状**：validation_status="invalid"

**原因**：LLM未能识别坐标格式

**检查**：查看 `llm_intent_response` 日志，确认LLM返回的JSON格式

## 测试通过标准

所有测试用例通过且满足：
1. 标准格式、括号格式、度分秒格式坐标都能正确提取
2. 设备查询返回3个设备
3. LLM选择1个设备并生成1-3条专业理由（基于产品功能详情分析）
4. 理由包含专业参数（传感器配置、续航时间、防护等级、避障系统、图传距离等）
5. 理由听起来可信且专业，像是分析真实产品规格书得出的结论
6. 确认消息格式为"已选择XX（理由1；理由2；...）..."
7. 确认后返回dispatch_id
8. 日志中有 `scout_dispatch_api_call_skipped_for_testing` 警告
9. 日志中 `scout_device_selection_success` 记录实际理由数量（reasons_count字段）
10. 缺少坐标时返回友好提示（无"coordinates"等技术术语）

## 恢复Java后端调用

测试完成后，恢复Java API调用只需：

```bash
# 编辑 router.py
vim src/emergency_agents/intent/router.py

# 找到第357-368行，修改为：
logger.info("scout_dispatch_payload_constructed", ...)
_scout_orchestrator.publish_scout_scenario(payload)  # 取消注释
logger.info("scout_dispatch_api_call_success", ...)  # 修改日志名称

# 删除警告日志（359-368行）
```

完成后提交代码并通知Java后端联调。
