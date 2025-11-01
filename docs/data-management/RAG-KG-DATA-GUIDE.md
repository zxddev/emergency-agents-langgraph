# RAG与知识图谱数据管理指南

本文档说明应急救援系统中RAG（检索增强生成）和知识图谱的数据存储位置、格式和管理方法。

## 📊 数据架构概览

系统使用**三重存储架构**实现智能决策：

```
┌─────────────────────────────────────────────────────────┐
│                   应急救援AI系统                          │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Neo4j      │  │   Qdrant     │  │  PostgreSQL  │  │
│  │  知识图谱     │  │  向量存储     │  │  关系数据库   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│       ▲                  ▲                  ▲            │
│       │                  │                  │            │
│  灾害关系推理         历史案例检索        装备资源管理    │
│  级联风险预测         RAG问答            审计日志        │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

| 数据类型 | 存储系统 | 服务器地址 | 用途 |
|---------|---------|-----------|------|
| 灾害关系图谱 | Neo4j | `bolt://192.168.20.100:7687` | 级联灾害预测、风险分析 |
| 历史案例向量 | Qdrant | `http://192.168.20.100:6333` | RAG检索、案例参考 |
| 装备资源信息 | PostgreSQL | `8.147.130.215:19532` | 装备推荐、资源调度 |

---

## 🗄️ 一、Neo4j 知识图谱数据

### 1.1 数据位置

**源代码定义**：`src/emergency_agents/graph/kg_seed.py`

这个Python文件包含了知识图谱的初始化种子数据，使用Cypher语句定义节点和关系。

### 1.2 数据结构

#### 节点类型 (Nodes)

1. **灾害节点** (Disaster)
   ```cypher
   (:Disaster {
       name: 'earthquake',      # 英文标识
       display_name: '地震'     # 中文显示名
   })
   ```

   当前包含的灾害类型：
   - 地震 (earthquake)
   - 洪水 (flood)
   - 山体滑坡 (landslide)
   - 化工泄露 (chemical_leak)
   - 火灾 (fire)

2. **设施节点** (Facility)
   ```cypher
   (:Facility {
       name: 'reservoir',
       display_name: '水库',
       type: 'water'
   })
   ```

   当前包含的设施：
   - 水库 (reservoir) - 水利设施
   - 化工厂 (chemical_plant) - 工业设施
   - 山区 (mountain_area) - 地质设施

#### 关系类型 (Relationships)

**TRIGGERS 关系**：表示一种灾害触发另一种灾害的级联效应

```cypher
(earthquake:Disaster)-[:TRIGGERS {
    probability: 0.75,              # 触发概率 (0-1)
    delay_hours: 2,                 # 延迟时间（小时）
    condition: 'magnitude>7.0',     # 触发条件
    severity_factor: 1.5            # 严重程度系数
}]->(flood:Disaster)
```

**当前定义的级联关系**：

| 主灾害 | 次生灾害 | 概率 | 延迟 | 触发条件 |
|-------|---------|------|------|---------|
| 地震 | 洪水 | 75% | 2小时 | 震级>7.0 且靠近水库 |
| 地震 | 山体滑坡 | 85% | 1小时 | 震级>6.5 且靠近山区 |
| 地震 | 化工泄露 | 60% | 3小时 | 震级>7.0 且靠近化工厂 |

### 1.3 初始化知识图谱

#### 方式一：Python代码执行

```python
from emergency_agents.graph.kg_seed import seed_kg
from emergency_agents.config import AppConfig

cfg = AppConfig.load_from_env()
seed_kg(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)
```

#### 方式二：命令行执行

```bash
cd /home/msq/gitCode/new_1/emergency-agents-langgraph
source .venv/bin/activate
set -a && source config/dev.env && set +a
export PYTHONPATH=src

python -c "from emergency_agents.graph.kg_seed import seed_kg; \
from emergency_agents.config import AppConfig; \
cfg = AppConfig.load_from_env(); \
seed_kg(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)"
```

### 1.4 查询知识图谱

#### 连接Neo4j

```bash
cypher-shell -a bolt://192.168.20.100:7687 \
  -u neo4j -p neo4jzmkj123456
```

#### 常用查询

**查看所有灾害节点**：
```cypher
MATCH (d:Disaster)
RETURN d.name, d.display_name;
```

**查看所有级联关系**：
```cypher
MATCH (d1:Disaster)-[r:TRIGGERS]->(d2:Disaster)
RETURN
  d1.display_name AS 主灾害,
  r.probability AS 触发概率,
  r.delay_hours AS 延迟小时,
  r.condition AS 触发条件,
  d2.display_name AS 次生灾害
ORDER BY r.probability DESC;
```

**查询特定灾害的级联路径**：
```cypher
MATCH path = (start:Disaster {name: 'earthquake'})-[:TRIGGERS*1..3]->(end:Disaster)
RETURN path;
```

### 1.5 扩展知识图谱

要添加新的灾害类型或关系，编辑 `kg_seed.py` 文件：

```python
# 添加新的灾害节点
"MERGE (:Disaster {name:'tsunami', display_name:'海啸'})",

# 添加新的级联关系
"""
MATCH (eq:Disaster {name:'earthquake'}), (ts:Disaster {name:'tsunami'})
MERGE (eq)-[:TRIGGERS {
    probability: 0.90,
    delay_hours: 0.5,
    condition: 'magnitude>8.0 AND coastal_area',
    severity_factor: 2.0
}]->(ts)
""",
```

---

## 🔍 二、Qdrant 向量数据库（RAG）

### 2.1 数据位置

**索引工具**：`src/emergency_agents/rag/cli.py`
**核心管道**：`src/emergency_agents/rag/pipe.py`

### 2.2 数据格式

#### JSONL 文件格式

每行一个JSON对象（不是JSON数组），包含以下字段：

```json
{
  "id": "case_202409_wenchuan_earthquake",
  "text": "2008年汶川地震救援案例：四川省消防救援总队出动320人...",
  "meta": {
    "source": "应急管理部案例库",
    "year": 2025,
    "disaster_type": "earthquake",
    "location": "阿坝州汶川县",
    "tags": ["地震救援", "破拆救援", "医疗保障"]
  },
  "domain": "案例"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `id` | string | ✅ | 案例唯一标识符 |
| `text` | string | ✅ | 用于向量检索的正文内容 |
| `meta` | object | ✅ | 元数据（来源、年份、标签等） |
| `domain` | string | ⚠️ | 数据域（案例/规范/地理/装备），CLI自动分组时需要 |

#### Domain 分类

系统按 `domain` 字段将数据分类到不同的Qdrant集合：

- `案例` → `rag_案例` 集合
- `规范` → `rag_规范` 集合
- `地理` → `rag_地理` 集合
- `装备` → `rag_装备` 集合

### 2.3 索引数据到 Qdrant

#### 准备数据文件

创建 `data/rescue_cases.jsonl`：

```jsonl
{"id":"case_001","text":"2008年汶川地震后，四川省消防救援总队出动320人，使用翼龙-2H无人机进行3D建模侦察，液压破拆工具打开楼板，野战医院提供24小时手术支持...","meta":{"source":"应急管理部","year":2025,"disaster_type":"earthquake","location":"汶川县"},"domain":"案例"}
{"id":"case_002","text":"2024年积石山地震救援，低温环境下使用保温帐篷和发电机组，派遣医疗队进行现场救治，成功转移被困群众150人...","meta":{"source":"案例库","year":2024,"disaster_type":"earthquake","location":"积石山"},"domain":"案例"}
```

#### 方式一：使用CLI工具（推荐）

```bash
cd /home/msq/gitCode/new_1/emergency-agents-langgraph
source .venv/bin/activate
set -a && source config/dev.env && set +a
export PYTHONPATH=src

# 如果文件中包含 domain 字段，自动分组索引
python -m emergency_agents.rag.cli data/rescue_cases.jsonl

# 或者手动指定 domain
python -m emergency_agents.rag.cli data/rescue_cases.jsonl --domain 案例
```

#### 方式二：Python代码调用

```python
from emergency_agents.rag.pipe import RagPipeline
from emergency_agents.config import AppConfig

cfg = AppConfig.load_from_env()

# 初始化RAG Pipeline（必须传递所有参数）
pipeline = RagPipeline(
    qdrant_url=cfg.qdrant_url,
    qdrant_api_key=cfg.qdrant_api_key,  # ✅ 认证必需
    embedding_model=cfg.embedding_model,
    embedding_dim=cfg.embedding_dim,
    openai_base_url=cfg.openai_base_url,
    openai_api_key=cfg.openai_api_key,
    llm_model=cfg.llm_model  # ✅ 必需参数
)

# 准备文档数据
docs = [
    {
        "id": "case_001",
        "text": "案例详细内容...",
        "meta": {
            "source": "应急管理部",
            "year": 2025,
            "disaster_type": "earthquake"
        }
    }
]

# 索引文档
pipeline.index_documents(domain="案例", docs=docs)
```

### 2.4 验证索引

#### 检查集合是否创建

```bash
curl -H "api-key: qdrantzmkj123456" \
  http://192.168.20.100:6333/collections | python3 -m json.tool
```

**期望输出**：
```json
{
  "result": {
    "collections": [
      {"name": "rag_案例"}
    ]
  },
  "status": "ok"
}
```

#### 查看集合详情

```bash
curl -H "api-key: qdrantzmkj123456" \
  http://192.168.20.100:6333/collections/rag_案例 | python3 -m json.tool
```

#### 测试检索

```bash
curl -X POST http://127.0.0.1:8008/intent/process \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "test",
    "thread_id": "test-001",
    "message": "查询汶川地震救援案例"
  }' | python3 -m json.tool
```

### 2.5 故障排查

#### 常见错误

**错误1：401 Unauthorized**
```
Unexpected Response: 401 (Unauthorized)
Raw response content: b'Must provide an API key'
```

**解决方案**：确保 `config/dev.env` 中配置了 `QDRANT_API_KEY=qdrantzmkj123456`

---

**错误2：404 Not Found**
```
Collection `rag_案例` doesn't exist!
```

**解决方案**：数据尚未索引，需要运行 CLI 工具索引数据

---

**错误3：维度不匹配**
```
ValueError: Qdrant collection 'rag_案例' dim=1024 != EMBEDDING_DIM=2048
```

**解决方案**：删除旧集合后重新索引
```bash
curl -X DELETE -H "api-key: qdrantzmkj123456" \
  http://192.168.20.100:6333/collections/rag_案例
```

---

## 🔧 三、PostgreSQL 装备数据

### 3.1 数据位置

**SQL补丁**：`sql/patches/20250128_equipment_2025.sql`

这个文件包含2025年的装备数据库表结构和初始数据。

### 3.2 执行SQL补丁

```bash
# 连接到PostgreSQL
psql "postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent"

# 执行补丁
\i sql/patches/20250128_equipment_2025.sql
```

---

## 📋 四、完整的数据初始化流程

### 4.1 快速启动检查清单

```bash
# 1. 检查配置文件
cat config/dev.env | grep -E "QDRANT|NEO4J|POSTGRES"

# 2. 初始化Neo4j知识图谱
python -c "from emergency_agents.graph.kg_seed import seed_kg; \
from emergency_agents.config import AppConfig; \
cfg = AppConfig.load_from_env(); \
seed_kg(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)"

# 3. 准备RAG案例数据
cat > /tmp/test_case.jsonl << 'EOF'
{"id":"test_001","text":"测试案例：这是一个地震救援案例，用于验证RAG系统是否正常工作。","meta":{"source":"测试","year":2025},"domain":"案例"}
EOF

# 4. 索引RAG数据
source .venv/bin/activate
set -a && source config/dev.env && set +a
export PYTHONPATH=src
python -m emergency_agents.rag.cli /tmp/test_case.jsonl

# 5. 验证所有数据源
curl -H "api-key: qdrantzmkj123456" http://192.168.20.100:6333/collections
cypher-shell -a bolt://192.168.20.100:7687 -u neo4j -p neo4jzmkj123456 -c "MATCH (n) RETURN count(n);"
psql "postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent" -c "SELECT 1;"
```

### 4.2 验证系统功能

```bash
# 测试完整救援流程
curl -X POST http://127.0.0.1:8008/intent/process \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "qa",
    "thread_id": "test-rescue-001",
    "message": "水磨镇发生地震，大约300人被困，请生成救援任务。mission_type=rescue，坐标103.85,31.68"
  }' | python3 -m json.tool
```

---

## 🔐 五、认证信息汇总

### 5.1 服务器访问凭据

| 服务 | 地址 | 用户名 | 密码 | 备注 |
|------|------|--------|------|------|
| Neo4j | bolt://192.168.20.100:7687 | neo4j | neo4jzmkj123456 | 知识图谱 |
| Qdrant | http://192.168.20.100:6333 | - | qdrantzmkj123456 | API Key认证 |
| PostgreSQL | 8.147.130.215:19532 | postgres | postgres123 | 关系数据库 |

### 5.2 环境变量配置

在 `config/dev.env` 中确保配置：

```bash
# Neo4j
NEO4J_URI=bolt://192.168.20.100:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jzmkj123456

# Qdrant
QDRANT_URL=http://192.168.20.100:6333
QDRANT_API_KEY=qdrantzmkj123456

# PostgreSQL
POSTGRES_DSN=postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent

# Embedding
EMBEDDING_MODEL=embedding-3
EMBEDDING_DIM=2048
```

---

## 📚 六、参考资料

### 6.1 相关代码文件

- **知识图谱种子数据**：`src/emergency_agents/graph/kg_seed.py`
- **知识图谱服务**：`src/emergency_agents/graph/kg_service.py`
- **RAG管道**：`src/emergency_agents/rag/pipe.py`
- **RAG CLI工具**：`src/emergency_agents/rag/cli.py`
- **配置管理**：`src/emergency_agents/config.py`

### 6.2 API文档

- **装备推荐**：`POST /kg/recommend`
- **案例检索**：`POST /kg/cases/search`
- **RAG索引**：`POST /rag/index`
- **RAG查询**：`POST /rag/query`

### 6.3 外部文档

- [Neo4j Cypher手册](https://neo4j.com/docs/cypher-manual/)
- [Qdrant官方文档](https://qdrant.tech/documentation/)
- [LlamaIndex指南](https://docs.llamaindex.ai/)

---

## 🆘 七、故障处理

### 7.1 数据库连接失败

```bash
# 测试Neo4j连接
cypher-shell -a bolt://192.168.20.100:7687 -u neo4j -p neo4jzmkj123456

# 测试Qdrant连接
curl -H "api-key: qdrantzmkj123456" http://192.168.20.100:6333/collections

# 测试PostgreSQL连接
psql "postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent" -c "SELECT 1;"
```

### 7.2 重置所有数据

```bash
# ⚠️ 警告：此操作将删除所有数据！

# 清空Qdrant集合
curl -X DELETE -H "api-key: qdrantzmkj123456" \
  http://192.168.20.100:6333/collections/rag_案例

# 清空Neo4j数据库
cypher-shell -a bolt://192.168.20.100:7687 -u neo4j -p neo4jzmkj123456 \
  -c "MATCH (n) DETACH DELETE n;"

# 重新初始化
python -c "from emergency_agents.graph.kg_seed import seed_kg; \
from emergency_agents.config import AppConfig; \
cfg = AppConfig.load_from_env(); \
seed_kg(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)"
```

### 7.3 联系支持

如遇问题，请查看日志文件：
- **应用日志**：`temp/uvicorn.log`
- **服务状态**：`curl http://localhost:8008/healthz`

---

**文档版本**：v1.0
**最后更新**：2025-10-28
**维护者**：应急救援系统开发组
