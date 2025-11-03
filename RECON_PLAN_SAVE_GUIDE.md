# 侦察方案保存到草稿表 - API使用指南

## 概述

本指南说明如何将 `/ai/recon/batch-weather-plan` 生成的侦察方案保存到 `incident_snapshots` 草稿表。

## 数据流程

```
1. 前端调用生成API → 获取侦察方案
   POST /ai/recon/batch-weather-plan

2. 前端调用保存API → 保存到草稿表
   POST /ai/recon/save-plan

3. 后续查询历史方案
   GET /ai/recon/list-plans/{incident_id}
   GET /ai/recon/get-plan/{snapshot_id}
```

## API端点说明

### 1. 保存侦察方案

**端点**: `POST /ai/recon/save-plan`

**功能**:
- 将生成的侦察方案保存到 `incident_snapshots` 表
- 快照类型: `reconnaissance_plan`
- 支持关联到指定事件ID
- 记录创建者和创建时间

**请求参数**:
```json
{
  "incident_id": "事件UUID",
  "plan_data": {侦察方案完整数据},
  "created_by": "用户ID或用户名（可选）"
}
```

**响应**:
```json
{
  "success": true,
  "snapshot_id": "生成的快照UUID",
  "incident_id": "关联的事件UUID",
  "message": "侦察方案已成功保存到草稿表"
}
```

### 2. 查询事件的所有方案

**端点**: `GET /ai/recon/list-plans/{incident_id}?limit=10`

**功能**:
- 获取指定事件的所有侦察方案快照
- 按时间倒序排列（最新的在前）
- 支持限制返回数量

**响应**:
```json
[
  {
    "snapshot_id": "快照UUID",
    "incident_id": "事件UUID",
    "snapshot_type": "reconnaissance_plan",
    "payload": {完整的方案数据},
    "generated_at": "2025-11-04T03:00:00",
    "created_by": "user123",
    "created_at": "2025-11-04T03:00:00"
  }
]
```

### 3. 获取单个方案详情

**端点**: `GET /ai/recon/get-plan/{snapshot_id}`

**功能**:
- 根据快照ID获取完整的侦察方案数据
- 用于查看、编辑、审核特定版本

**响应**:
```json
{
  "snapshot_id": "快照UUID",
  "incident_id": "事件UUID",
  "snapshot_type": "reconnaissance_plan",
  "payload": {完整的方案数据},
  "generated_at": "2025-11-04T03:00:00",
  "created_by": "user123",
  "created_at": "2025-11-04T03:00:00"
}
```

## 完整使用示例

### 步骤1: 生成侦察方案

```bash
# 调用生成API
PLAN_RESPONSE=$(curl -s -X POST http://localhost:8008/ai/recon/batch-weather-plan \
  -H "Content-Type: application/json" \
  -d '{
    "disaster_type": "flood",
    "epicenter": {"lon": 103.8, "lat": 31.66},
    "severity": "critical"
  }')

echo "$PLAN_RESPONSE" | python3 -m json.tool > plan.json
```

### 步骤2: 保存到草稿表

```bash
# 方式1: 直接使用返回数据
curl -X POST http://localhost:8008/ai/recon/save-plan \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"550e8400-e29b-41d4-a716-446655440000\",
    \"plan_data\": $(cat plan.json),
    \"created_by\": \"operator001\"
  }"
```

**响应示例**:
```json
{
  "success": true,
  "snapshot_id": "7c9e6679-7425-40de-944b-e07fc1249ce1",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "侦察方案已成功保存到草稿表"
}
```

### 步骤3: 查询已保存的方案

```bash
# 查询事件的所有方案（最新10个）
curl -s http://localhost:8008/ai/recon/list-plans/550e8400-e29b-41d4-a716-446655440000?limit=10 \
  | python3 -m json.tool

# 获取特定方案详情
curl -s http://localhost:8008/ai/recon/get-plan/7c9e6679-7425-40de-944b-e07fc1249ce1 \
  | python3 -m json.tool
```

## 数据库表结构

```sql
-- incident_snapshots 表结构
CREATE TABLE operational.incident_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    snapshot_type varchar(100) NOT NULL,  -- 值为 'reconnaissance_plan'
    payload jsonb NOT NULL,  -- 完整的侦察方案JSON
    generated_at timestamp with time zone NOT NULL DEFAULT now(),
    created_by varchar(100),
    created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- 索引
CREATE INDEX idx_incident_snapshots_incident ON incident_snapshots(incident_id);
CREATE INDEX idx_incident_snapshots_type ON incident_snapshots(snapshot_type);
CREATE INDEX idx_incident_snapshots_generated ON incident_snapshots(generated_at);
```

## Payload 数据结构

保存的 `payload` 字段包含完整的侦察方案数据：

```json
{
  "success": true,
  "batches": [
    {
      "device_id": "dog-dv-1",
      "device_name": "医疗救援机器狗",
      "target_ids": ["uuid1", "uuid2", ...],
      "estimated_completion_minutes": 75
    }
  ],
  "detailed_plan": {
    "command_center": {"lon": 103.8, "lat": 31.66},
    "disaster_info": {...},
    "air_recon_section": {
      "section_name": "空中侦察",
      "tasks": [...]
    },
    "ground_recon_section": {...},
    "water_recon_section": {...},
    "data_integration_desc": "整合说明",
    "earliest_start_time": "2025-11-04 03:00:00",
    "latest_end_time": "2025-11-04 10:30:00",
    "total_estimated_hours": 7.5
  },
  "reinforcement_request": null,
  "total_targets": 103,
  "suitable_devices_count": 24,
  "estimated_total_hours": 25.75
}
```

## 前端集成示例

### React/Vue 示例

```javascript
// 1. 生成侦察方案
async function generateReconPlan(disasterInfo) {
  const response = await fetch('http://localhost:8008/ai/recon/batch-weather-plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      disaster_type: disasterInfo.type,
      epicenter: disasterInfo.epicenter,
      severity: disasterInfo.severity
    })
  });

  const planData = await response.json();
  return planData;
}

// 2. 保存侦察方案到草稿表
async function saveReconPlan(incidentId, planData, userId) {
  const response = await fetch('http://localhost:8008/ai/recon/save-plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      incident_id: incidentId,
      plan_data: planData,
      created_by: userId
    })
  });

  const result = await response.json();
  console.log('保存成功:', result.snapshot_id);
  return result;
}

// 3. 查询历史方案
async function loadPlanHistory(incidentId) {
  const response = await fetch(
    `http://localhost:8008/ai/recon/list-plans/${incidentId}?limit=10`
  );

  const plans = await response.json();
  return plans;
}

// 4. 完整流程
async function handleReconPlanWorkflow() {
  // 步骤1: 生成方案
  const planData = await generateReconPlan({
    type: 'flood',
    epicenter: { lon: 103.8, lat: 31.66 },
    severity: 'critical'
  });

  // 步骤2: 用户确认后保存
  if (userConfirmed) {
    const saveResult = await saveReconPlan(
      '550e8400-e29b-41d4-a716-446655440000',
      planData,
      'operator001'
    );

    console.log('方案已保存，快照ID:', saveResult.snapshot_id);
  }

  // 步骤3: 查看历史方案
  const history = await loadPlanHistory('550e8400-e29b-41d4-a716-446655440000');
  console.log('历史方案数量:', history.length);
}
```

## 使用场景

### 1. 草稿保存
- 前端生成方案后，先保存为草稿
- 用户可以查看、修改、审核
- 不影响现有的执行中任务

### 2. 方案版本管理
- 同一事件可以保存多个版本的方案
- 支持对比不同版本的差异
- 追踪方案的演进历史

### 3. 人工审核流程
- 方案生成后保存到草稿表
- 指挥员审核批准
- 审核通过后转为正式执行计划

### 4. 应急回溯
- 事后分析为什么选择了某个方案
- 查看当时的设备配置和目标分布
- 决策追溯和责任判定

## 注意事项

### 1. incident_id 必须存在
- 必须先创建事件记录（events表）
- 使用有效的事件UUID
- 否则会因外键约束失败

### 2. 数据大小限制
- payload 字段为JSONB类型
- PostgreSQL JSONB无固定大小限制
- 但建议单个方案不超过10MB

### 3. 权限控制
- 当前API未做权限验证
- 生产环境需添加用户认证
- 建议记录 created_by 字段

### 4. 性能考虑
- list_plans 支持 limit 参数避免一次性返回过多数据
- 建议前端分页查询
- 使用索引优化查询性能

## 错误处理

### 400 Bad Request
```json
{
  "detail": "无效的incident_id格式: xxx，必须是UUID格式"
}
```

### 404 Not Found
```json
{
  "detail": "未找到快照: xxx"
}
```

### 500 Internal Server Error
```json
{
  "detail": "保存侦察方案失败: 外键约束失败"
}
```

## 测试命令

```bash
# 1. 生成并保存（一键测试）
./test_save_recon_plan.sh

# 2. 查看已保存的方案
curl -s http://localhost:8008/ai/recon/list-plans/{incident_id} | jq

# 3. 验证数据库
PGPASSWORD=postgres123 psql -h 8.147.130.215 -p 19532 -U postgres -d emergency_agent \
  -c "SELECT snapshot_id, incident_id, snapshot_type, created_at FROM operational.incident_snapshots WHERE snapshot_type='reconnaissance_plan' ORDER BY created_at DESC LIMIT 10;"
```

## 相关文档

- **API规范**: `API_SPECIFICATION.md`
- **数据库设计**: `sql/operational.sql`
- **前端集成**: `FRONTEND_API_GUIDE.md`

---

**创建时间**: 2025-11-04
**API版本**: v1.0
**维护者**: msq
