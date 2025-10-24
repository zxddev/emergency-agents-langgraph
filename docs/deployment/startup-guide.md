# 🚀 应急大脑系统启动指南

> **完整的从零到运行指南** - 适用于新开发者快速上手

---

## 📋 目录

1. [前置条件](#前置条件)
2. [快速启动（推荐）](#快速启动推荐)
3. [详细配置说明](#详细配置说明)
4. [数据库初始化](#数据库初始化)
5. [服务启动与验证](#服务启动与验证)
6. [故障排查](#故障排查)
7. [两种部署模式对比](#两种部署模式对比)

---

## 前置条件

### 必需软件

- **Python 3.12+** （推荐 3.12.3）
  ```bash
  python3 --version  # 验证版本
  ```

- **Git**（用于克隆和版本管理）
  ```bash
  git --version
  ```

### 网络要求

选择以下**任一模式**：

**模式A：使用远程服务**（推荐，快速启动）
- 需要访问 `8.147.130.215`（Qdrant、Neo4j、PostgreSQL）
- 需要访问智谱 AI API：`https://open.bigmodel.cn`

**模式B：完全本地开发**
- 安装 Docker 和 Docker Compose
- 至少 8GB 可用内存
- 至少 20GB 可用磁盘空间

---

## 快速启动（推荐）

### 第一步：克隆项目（如尚未完成）

```bash
git clone https://github.com/zxddev/emergency-agents-langgraph.git
cd emergency-agents-langgraph
```

### 第二步：创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 第三步：配置环境变量

```bash
# 复制配置模板
cp config/.env.example config/dev.local.env

# 编辑配置文件（使用你喜欢的编辑器）
vim config/dev.local.env
# 或者: nano config/dev.local.env
```

**最小必需配置**（模式A - 远程服务）：
```bash
# 必需：智谱 AI API Key
OPENAI_API_KEY=your_zhipu_api_key_here  # 从 https://open.bigmodel.cn 获取

# 数据库配置（默认已配置远程服务，无需修改）
QDRANT_URL=http://8.147.130.215:6333
NEO4J_URI=bolt://8.147.130.215:7687
POSTGRES_DSN=postgresql://rescue:rescue_password@8.147.130.215:19532/rescue_system

# ASR 可选（如不需要语音识别可跳过）
# ASR_PRIMARY_PROVIDER=aliyun
# DASHSCOPE_API_KEY=your_dashscope_key
```

### 第四步：环境检查

```bash
./scripts/check-env.sh
```

如果检查通过，继续下一步；如有错误，按提示修复。

### 第五步：初始化数据库

```bash
./scripts/init-db.sh
```

这将自动：
- 验证 PostgreSQL 连接并应用 schema（如需要）
- 初始化 Neo4j 知识图谱（灾害关系、装备推荐）
- 验证 Qdrant 可达性

### 第六步：启动服务

```bash
./scripts/dev-run.sh
```

服务将在后台启动，日志输出到 `temp/server.log`。

### 第七步：验证服务

```bash
# 运行健康检查
./scripts/health-check.sh

# 或者手动测试
curl http://localhost:8008/healthz
# 预期输出: {"status":"ok"}
```

### 查看日志

```bash
# 实时查看日志
tail -f temp/server.log

# 如需停止服务
kill $(cat temp/uvicorn.pid)
```

---

## 详细配置说明

### LLM 配置

#### 选项A：智谱 AI（推荐）

```bash
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_API_KEY=your_zhipu_api_key_here
LLM_MODEL=glm-4-flash  # 或 glm-4-plus（更强但更贵）
EMBEDDING_MODEL=embedding-3
EMBEDDING_DIM=2048
```

**获取 API Key**：
1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn)
2. 注册/登录账号
3. 在控制台创建 API Key
4. 复制 Key 到配置文件

#### 选项B：本地 vLLM（需要 GPU）

```bash
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=dummy
LLM_MODEL=qwen2.5-7b-instruct
EMBEDDING_MODEL=bge-large-zh-v1.5
EMBEDDING_DIM=1024
```

**启动本地 vLLM**：
```bash
# 启动聊天模型（需要 GPU）
docker run -d --gpus all \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-7B-Instruct

# 启动 Embedding 模型
docker run -d --gpus all \
  -p 8001:8000 \
  vllm/vllm-openai:latest \
  --model BAAI/bge-large-zh-v1.5 --task embed
```

### ASR 语音识别配置（可选）

系统支持**自动故障转移**：主 Provider 故障时自动切换到备用 Provider。

#### 双 Provider 模式（推荐，高可用）

```bash
# 主 Provider：阿里云（在线，高准确率）
ASR_PRIMARY_PROVIDER=aliyun
DASHSCOPE_API_KEY=your_dashscope_key

# 备用 Provider：本地 FunASR（离线，网络故障时使用）
ASR_FALLBACK_PROVIDER=local
VOICE_ASR_WS_URL=wss://127.0.0.1:10097

# 健康检查间隔（秒）
HEALTH_CHECK_INTERVAL=30
```

#### 单 Provider 模式

**仅使用阿里云**：
```bash
ASR_PRIMARY_PROVIDER=aliyun
DASHSCOPE_API_KEY=your_dashscope_key
ASR_FALLBACK_PROVIDER=  # 留空禁用备用
```

**仅使用本地 FunASR**：
```bash
ASR_PRIMARY_PROVIDER=local
VOICE_ASR_WS_URL=wss://127.0.0.1:10097
ASR_FALLBACK_PROVIDER=  # 留空禁用备用
```

**本地 FunASR 部署**：参考 [docs/modules/asr/quick-reference.md](../modules/asr/quick-reference.md)

### 数据库配置

#### 选项A：远程服务（默认）

```bash
# 无需修改，使用默认配置
QDRANT_URL=http://8.147.130.215:6333
NEO4J_URI=bolt://8.147.130.215:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=example-neo4j
POSTGRES_DSN=postgresql://rescue:rescue_password@8.147.130.215:19532/rescue_system
```

#### 选项B：本地 Docker

1. **启动本地服务**：
   ```bash
   # 设置环境变量
   export POSTGRES_PASSWORD=your_pg_password
   export NEO4J_AUTH=neo4j/your_neo4j_password
   
   # 启动所有服务
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **修改配置**：
   ```bash
   QDRANT_URL=http://localhost:6333
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_neo4j_password
   POSTGRES_DSN=postgresql://rescue:your_pg_password@localhost:5432/rescue_system
   ```

---

## 数据库初始化

### 自动初始化（推荐）

```bash
./scripts/init-db.sh
```

### 手动初始化（如自动脚本失败）

#### 1. PostgreSQL

```bash
# 方式A：使用 psql 客户端
psql "${POSTGRES_DSN}" -f sql/operational.sql

# 方式B：使用 pgAdmin 或其他 GUI 工具
# 导入 sql/operational.sql 文件
```

**验证初始化**：
```bash
psql "${POSTGRES_DSN}" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='operational'"
# 预期：27+ 个表
```

#### 2. Neo4j 知识图谱

```bash
# 激活虚拟环境
source .venv/bin/activate
export PYTHONPATH=src

# 运行初始化脚本
python -m emergency_agents.graph.kg_seed
```

**验证初始化**：
```bash
# 使用 Neo4j Browser 访问 http://localhost:7474
# 运行 Cypher 查询：
MATCH (n) RETURN count(n)
# 预期：20+ 个节点
```

#### 3. Qdrant

无需手动初始化，集合将在首次使用时自动创建。

---

## 服务启动与验证

### 启动服务

```bash
./scripts/dev-run.sh
```

**脚本功能**：
- 加载环境变量
- 在后台启动 Uvicorn
- 记录 PID 到 `temp/uvicorn.pid`
- 日志输出到 `temp/server.log`

**自定义端口**：
```bash
PORT=9000 ./scripts/dev-run.sh
```

**禁用热重载**（生产环境）：
```bash
RELOAD=0 ./scripts/dev-run.sh
```

### 验证服务

```bash
# 方式A：使用健康检查脚本
./scripts/health-check.sh

# 方式B：手动测试各端点
curl http://localhost:8008/healthz
curl http://localhost:8008/docs  # Swagger UI
```

### 测试核心功能

```bash
# 1. 测试记忆管理
curl -X POST "http://localhost:8008/memory/add" \
  -H "Content-Type: application/json" \
  -d '{"content":"测试记忆","user_id":"test_user"}'

# 2. 测试 RAG 索引
curl -X POST "http://localhost:8008/rag/index" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "规范",
    "docs": [{"id":"test1","text":"测试文档内容"}]
  }'

# 3. 测试知识图谱推荐
curl -X POST "http://localhost:8008/kg/recommend" \
  -H "Content-Type: application/json" \
  -d '{"hazard":"火灾","top_k":5}'
```

### 查看和管理日志

```bash
# 实时查看日志
tail -f temp/server.log

# 查看最近50行
tail -n 50 temp/server.log

# 搜索错误
grep ERROR temp/server.log

# 清空日志（如文件过大）
> temp/server.log
```

### 停止服务

```bash
# 方式A：使用 PID 文件
kill $(cat temp/uvicorn.pid)

# 方式B：查找进程并杀死
ps aux | grep uvicorn
kill <PID>

# 方式C：强制杀死所有 Uvicorn 进程（谨慎使用）
pkill -f "uvicorn emergency_agents.api.main:app"
```

---

## 故障排查

### 问题1：API Key 无效

**症状**：
```
ERROR: Invalid API key
```

**解决**：
1. 确认 API Key 已正确复制（无多余空格）
2. 验证 Key 有效期和额度
3. 测试 API 连通性：
   ```bash
   curl -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"hi"}]}'
   ```

### 问题2：数据库连接失败

**症状**：
```
ERROR: Connection refused (8.147.130.215:6333)
```

**解决**：

**检查网络**：
```bash
# 测试 Qdrant
curl http://8.147.130.215:6333

# 测试 Neo4j（需要 nc 工具）
nc -zv 8.147.130.215 7687

# 测试 PostgreSQL
psql "${POSTGRES_DSN}" -c "SELECT 1"
```

**切换到本地 Docker**：
```bash
# 启动本地服务
docker-compose -f docker-compose.dev.yml up -d

# 修改 config/dev.local.env 为本地地址
# QDRANT_URL=http://localhost:6333
# NEO4J_URI=bolt://localhost:7687
# POSTGRES_DSN=postgresql://rescue:password@localhost:5432/rescue_system
```

### 问题3：端口被占用

**症状**：
```
ERROR: Address already in use: 8008
```

**解决**：
```bash
# 查找占用端口的进程
lsof -i:8008
# 或
netstat -tuln | grep 8008

# 杀死进程
kill <PID>

# 或使用不同端口
PORT=9000 ./scripts/dev-run.sh
```

### 问题4：虚拟环境依赖缺失

**症状**：
```
ModuleNotFoundError: No module named 'fastapi'
```

**解决**：
```bash
# 确认虚拟环境已激活
source .venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt

# 验证关键包
python -c "import fastapi, langgraph, neo4j; print('OK')"
```

### 问题5：ASR 识别失败

**症状**：
```
ERROR: ASR provider not available
```

**解决**：

**检查配置**：
```bash
# 查看配置
grep ASR config/dev.local.env

# 确保至少配置了一个 Provider
```

**测试阿里云**：
```bash
curl -X POST "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription" \
  -H "Authorization: Bearer YOUR_DASHSCOPE_KEY"
```

**测试本地 FunASR**：
```bash
# 检查 WebSocket 服务
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  ${VOICE_ASR_WS_URL}
```

### 问题6：日志中出现大量警告

**症状**：
```
WARNING: No active exception to reraise
```

**解决**：
- 这些警告通常不影响功能，可以忽略
- 如需清理日志，重启服务：
  ```bash
  kill $(cat temp/uvicorn.pid)
  > temp/server.log
  ./scripts/dev-run.sh
  ```

---

## 两种部署模式对比

| 维度 | 模式A：远程服务 | 模式B：本地 Docker |
|------|----------------|-------------------|
| **网络要求** | 需访问 8.147.130.215 | 仅需本地网络 |
| **资源要求** | 低（仅需运行 Python） | 高（需 8GB+ 内存） |
| **启动速度** | 快（< 1分钟） | 慢（首次需拉取镜像） |
| **数据隔离** | 共享数据库 | 完全隔离 |
| **适用场景** | 快速开发、团队协作 | 离线开发、完整测试 |
| **配置复杂度** | 低 | 中等 |

**推荐选择**：
- 新手开发者：**模式A**（远程服务）
- 离线环境：**模式B**（本地 Docker）
- 生产部署：参考 [docs/deployment/sop.md](./sop.md)

---

## 常用命令速查

```bash
# 环境管理
source .venv/bin/activate       # 激活虚拟环境
deactivate                       # 退出虚拟环境

# 检查与初始化
./scripts/check-env.sh           # 环境检查
./scripts/init-db.sh             # 数据库初始化
./scripts/health-check.sh        # 健康检查

# 服务管理
./scripts/dev-run.sh             # 启动服务
kill $(cat temp/uvicorn.pid)     # 停止服务
tail -f temp/server.log          # 查看日志

# 数据库操作
psql "${POSTGRES_DSN}" -c "..."  # 执行 SQL
python -m emergency_agents.graph.kg_seed  # 初始化 Neo4j

# API 测试
curl http://localhost:8008/healthz         # 健康检查
curl http://localhost:8008/docs            # Swagger UI
```

---

## 下一步

✅ 服务启动成功后，继续：

1. **阅读开发指南**：[docs/开发指导/开发指导.md](../开发指导/开发指导.md)
2. **查看行动计划**：[docs/行动计划/ACTION-PLAN-DAY1.md](../行动计划/ACTION-PLAN-DAY1.md)
3. **了解 ASR 模块**：[docs/modules/asr/quick-reference.md](../modules/asr/quick-reference.md)
4. **学习 LangGraph**：[docs/LangGraph最佳实践/最佳实践.md](../LangGraph最佳实践/最佳实践.md)

---

**文档版本**：v1.0  
**更新时间**：2025-10-24  
**维护者**：AI 应急大脑团队  
**状态**：✅ 已验证
