# 侦察方案数据库存储配置指南

## 一、数据库表创建

### 1. 执行SQL创建表

```bash
# 方式1：使用psql命令行
psql -h 192.168.31.40 -U postgres -d emergency_agent -f sql/create_recon_plans_table.sql

# 方式2：使用DBeaver等GUI工具
# 打开 sql/create_recon_plans_table.sql 文件并执行
```

### 2. 验证表是否创建成功

```bash
psql -h 192.168.31.40 -U postgres -d emergency_agent -c "\d recon_plans"
```

预期输出：显示表结构、字段、索引等信息

## 二、配置验证

### 1. 检查PostgreSQL连接

确认 `config/dev.env` 中已有数据库配置：

```bash
# PostgreSQL连接配置
POSTGRES_DSN=postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent
```

### 2. 测试数据库连接

```bash
# 使用psql测试连接
psql -h 192.168.31.40 -U postgres -d emergency_agent -c "SELECT 1"

# 或使用Python测试
python3 -c "
from psycopg_pool import AsyncConnectionPool
import asyncio
async def test():
    pool = AsyncConnectionPool(conninfo='postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent')
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT 1')
            print('数据库连接成功')
asyncio.run(test())
"
```

## 三、功能说明

### 1. 自动存储流程

当调用 `/ai/recon/batch-weather-plan` 接口时，系统会自动：

1. **生成侦察方案**（使用GLM-4.6 LLM，并行生成3个章节）
2. **保存到PostgreSQL数据库**（永久存储，用于审计和历史查询）
3. **返回纯文本方案** + `plan_id`（UUID格式）

### 2. 数据库字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `plan_id` | UUID | 方案唯一标识（主键） |
| `incident_id` | UUID | 关联事件ID（可选） |
| `plan_type` | VARCHAR | 方案类型（recon/rescue/evacuation） |
| `plan_subtype` | VARCHAR | 子类型（batch_weather/priority） |
| `plan_title` | VARCHAR | 方案标题 |
| `plan_content` | TEXT | 纯文本内容（无Markdown格式符号） |
| `plan_data` | JSONB | 完整的结构化数据（包括设备、目标点等） |
| `disaster_type` | VARCHAR | 灾害类型 |
| `disaster_location` | JSONB | 灾害位置（经纬度） |
| `severity` | VARCHAR | 严重程度（critical/high/medium/low） |
| `device_count` | INTEGER | 设备数量 |
| `target_count` | INTEGER | 目标点数量 |
| `llm_model` | VARCHAR | 使用的LLM模型 |
| `status` | VARCHAR | 状态（draft/approved/executed） |

### 3. API返回格式

```json
{
  "code": 200,
  "data": "侦察方案文本内容（无Markdown格式符号）",
  "plan_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## 四、数据查询

### 1. 查询最近的侦察方案

```sql
SELECT
    plan_id,
    plan_title,
    disaster_type,
    severity,
    device_count,
    target_count,
    status,
    created_at
FROM recon_plans
WHERE NOT is_deleted
ORDER BY created_at DESC
LIMIT 10;
```

### 2. 查询特定灾害类型的方案

```sql
SELECT * FROM recon_plans
WHERE disaster_type = 'earthquake'
  AND NOT is_deleted
ORDER BY created_at DESC;
```

### 3. 查看完整的JSON数据

```sql
SELECT plan_data::text
FROM recon_plans
WHERE plan_id = '550e8400-e29b-41d4-a716-446655440000';
```

## 五、故障降级

### 1. 数据库保存失败

如果数据库保存失败，系统会：
- ✅ 继续返回侦察方案
- ⚠️ 跳过数据库持久化，不影响响应
- 📝 记录警告日志：\"数据库保存失败（不影响业务）\"

**核心设计：数据库存储失败不会阻塞业务流程！**

## 六、性能和优化

### 1. 并行LLM调用优化

系统使用 `ThreadPoolExecutor` 并行生成3个章节（空中、地面、水上），相比串行执行：
- **串行执行**: 3 × 30秒 = 90秒
- **并行执行**: max(30秒, 30秒, 30秒) = ~30秒
- **性能提升**: 约3倍

### 2. Token使用优化

- **max_tokens**: 从4000增加到16000（避免输出截断）
- **温度设置**: temperature=0.3（平衡创造性和稳定性）
- **超时设置**: 300秒（避免长任务超时）

### 3. 数据库查询优化

使用索引加速常见查询：
```sql
-- 按事件ID查询
CREATE INDEX idx_recon_plans_incident_id ON recon_plans(incident_id) WHERE NOT is_deleted;

-- 按创建时间查询
CREATE INDEX idx_recon_plans_created_at ON recon_plans(created_at DESC) WHERE NOT is_deleted;
```

## 七、常见问题

### Q1: 为什么不使用Redis缓存？

A: 根据业务需求，当前版本只需要数据库持久化存储。Redis缓存可以在未来需要时轻松集成（代码已预留）。

### Q2: 如何查看某个方案的完整JSON数据？

```sql
SELECT plan_data::text
FROM recon_plans
WHERE plan_id = 'your-plan-id';
```

### Q3: 数据库字段 `incident_id` 为何可选？

A: 方案可以独立生成（测试、预案等），也可以关联到具体事件。NULL值表示独立方案。

### Q4: 如何修改LLM超时时间？

修改 `grouped_markdown_generator.py` 中的 `timeout` 参数：
```python
response = self.llm_client.chat.completions.create(
    ...
    timeout=600  # 改为10分钟
)
```

## 八、监控和调试

### 1. 查看PostgreSQL慢查询

```sql
SELECT * FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

### 2. 查看应用日志

```bash
# 实时查看侦察方案相关日志
tail -f temp/server.log | grep -i "recon_plans\|batch-weather"

# 查看数据库保存日志
tail -f temp/server.log | grep "侦察方案已保存到数据库"

# 查看错误日志
tail -f temp/server.log | grep -i "error\|warning"
```

### 3. 测试API接口

```bash
# 测试侦察方案生成
curl -X POST http://localhost:8008/ai/recon/batch-weather-plan \
  -H "Content-Type: application/json" \
  -d '{
    "disaster_type": "earthquake",
    "epicenter": {"lon": 103.8, "lat": 31.66},
    "severity": "critical"
  }' | python3 -m json.tool

# 查看返回的plan_id
```

### 4. 验证数据库记录

```bash
# 查看最新生成的方案
psql -h 192.168.31.40 -U postgres -d emergency_agent -c "
SELECT plan_id, plan_title, disaster_type, severity, created_at
FROM recon_plans
WHERE NOT is_deleted
ORDER BY created_at DESC
LIMIT 5;"
```

---

**完成时间**: 2025-01-04
**版本**: v1.0
**作者**: Claude Code
