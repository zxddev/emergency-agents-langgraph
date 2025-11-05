# AI应急大脑 - Docker部署指南（内网环境）

## 📋 目录

- [快速开始](#快速开始)
- [文件说明](#文件说明)
- [构建镜像](#构建镜像)
- [部署方式](#部署方式)
- [配置说明](#配置说明)
- [监控与维护](#监控与维护)
- [故障排查](#故障排查)

---

## 🚀 快速开始

### 前置要求

- Docker >= 20.10
- Docker Compose >= 1.29（可选，用于编排部署）
- 已配置好的 `config/env.internal` 文件
- 内网服务可访问（PostgreSQL、Neo4j、Qdrant、Redis等）

### 三步部署

```bash
# 1. 构建镜像
./build.sh

# 2. 测试运行（可选）
./run.sh

# 3. 生产部署
docker-compose -f docker-compose.internal.yml up -d
```

---

## 📦 文件说明

### 核心文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 多阶段构建配置（Python 3.11 Slim + CPU版PyTorch） |
| `.dockerignore` | 排除不必要文件，减小镜像体积 |
| `docker-compose.internal.yml` | 内网环境编排配置 |
| `build.sh` | 镜像构建脚本 |
| `run.sh` | 本地测试运行脚本 |
| `deploy-internal.sh` | 内网部署脚本（支持本地/远程/导出） |
| `config/env.internal` | 内网环境变量配置 |

### 镜像特性

- **基础镜像**: `python:3.11-slim`（体积小、安全性高）
- **多阶段构建**: 分离编译期和运行期依赖，减小最终镜像
- **CPU版PyTorch**: 使用 `torch==2.4.1+cpu` 减少镜像体积（从2GB降至500MB）
- **非root用户**: 使用UID 1000的 `emergency` 用户运行（安全最佳实践）
- **健康检查**: 内置健康探针，自动检测服务状态

---

## 🔨 构建镜像

### 基础构建

```bash
# 构建最新版本
./build.sh

# 构建指定版本
./build.sh v1.0.0

# 手动构建
docker build -t emergency-agents-langgraph:latest .
```

### 构建过程说明

```
[Stage 1: Builder] - 编译期
├── 安装编译依赖（gcc、libpq-dev等）
├── 安装CPU版PyTorch
└── 安装Python依赖到 /root/.local

[Stage 2: Production] - 运行期
├── 仅安装运行时依赖（libpq5、libopus0等）
├── 复制Python依赖（无编译工具）
├── 创建非root用户
└── 复制应用代码
```

### 预期镜像大小

- **总大小**: ~800MB - 1.2GB
- **Python基础镜像**: ~180MB
- **依赖包**: ~500MB
- **应用代码**: ~20MB

---

## 🚀 部署方式

### 方式1：本地测试运行

适用于开发环境快速验证：

```bash
# 启动测试容器
./run.sh

# 查看日志
docker logs -f emergency-agents-test

# 停止容器
docker stop emergency-agents-test
docker rm emergency-agents-test
```

**特点**：
- 容器名称：`emergency-agents-test`
- 端口映射：`8008:8008`
- 数据卷：挂载本地 `temp/` 和 `logs/`
- 重启策略：`unless-stopped`

### 方式2：Docker Compose部署（推荐）

适用于生产环境：

```bash
# 启动服务
docker-compose -f docker-compose.internal.yml up -d

# 查看状态
docker-compose -f docker-compose.internal.yml ps

# 查看日志
docker-compose -f docker-compose.internal.yml logs -f

# 重启服务
docker-compose -f docker-compose.internal.yml restart

# 停止服务
docker-compose -f docker-compose.internal.yml down
```

**特点**：
- 容器名称：`emergency-agents-internal`
- 数据持久化：使用Docker Volume
- 资源限制：2核CPU、4GB内存
- 日志轮转：最多10个文件，每个50MB

### 方式3：自动化部署脚本

适用于多环境部署：

```bash
# 本地部署
./deploy-internal.sh
# 选择 1

# 远程部署（通过SSH）
DEPLOY_SERVER=192.168.31.40 DEPLOY_USER=msq ./deploy-internal.sh
# 选择 2

# 导出镜像（手动传输）
./deploy-internal.sh
# 选择 3
```

### 方式4：手动导出/导入镜像

适用于无法直接访问内网服务器的场景：

```bash
# 在构建机器上导出
docker save emergency-agents-langgraph:latest | gzip > emergency-agents.tar.gz

# 传输到目标服务器
scp emergency-agents.tar.gz user@192.168.31.40:/tmp/

# 在目标服务器上导入
ssh user@192.168.31.40
docker load -i /tmp/emergency-agents.tar.gz

# 传输配置文件
scp -r config docker-compose.internal.yml user@192.168.31.40:~/emergency-agents/

# 启动服务
cd ~/emergency-agents
docker-compose -f docker-compose.internal.yml up -d
```

---

## ⚙️ 配置说明

### 环境变量配置（env.internal）

关键配置项：

```bash
# 数据库连接（必须）
QDRANT_URL=http://192.168.31.40:6333
NEO4J_URI=bolt://192.168.31.40:7687
POSTGRES_DSN=postgresql://postgres:postgres123@192.168.31.40:5432/emergency_agent
REDIS_URL=redis://192.168.31.40:6379/0

# LLM服务（必须）
OPENAI_BASE_URL=http://192.168.31.40:8000/v1
OPENAI_API_KEY=your-api-key
LLM_MODEL=glm-4-flash

# 语音服务（可选）
DASHSCOPE_API_KEY=sk-xxx
VOICE_TTS_URL=http://192.168.31.40:18002/api/tts

# 其他服务（可选）
ADAPTER_HUB_BASE_URL=http://192.168.31.40:18090
WEB_API_BASE_URL=http://127.0.0.1:28080/web-api
```

### Docker Compose配置调整

#### 修改端口映射

编辑 `docker-compose.internal.yml`：

```yaml
ports:
  - "18008:8008"  # 改为其他端口
```

#### 调整资源限制

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # 增加CPU
      memory: 8G       # 增加内存
```

#### 添加依赖服务

如果PostgreSQL/Redis等服务在同一docker-compose中：

```yaml
services:
  emergency-agents:
    depends_on:
      - postgres
      - redis
      - neo4j
```

---

## 📊 监控与维护

### 健康检查

```bash
# 手动健康检查
curl http://localhost:8008/healthz

# 查看Docker健康状态
docker ps | grep emergency-agents

# 详细健康检查
docker inspect emergency-agents-internal | grep -A 10 "Health"
```

### 日志管理

```bash
# 实时日志
docker-compose -f docker-compose.internal.yml logs -f

# 查看最近100行
docker logs emergency-agents-internal --tail 100

# 查看特定时间段日志
docker logs emergency-agents-internal --since 2024-01-01T00:00:00

# 导出日志
docker logs emergency-agents-internal > emergency-agents.log
```

### Prometheus监控

访问 `http://localhost:8008/metrics` 获取监控指标：

关键指标：
- `http_requests_total` - 请求总数
- `http_request_duration_seconds` - 请求延迟
- `process_cpu_seconds_total` - CPU使用
- `process_resident_memory_bytes` - 内存使用

### 数据备份

备份持久化数据（Docker Volume）：

```bash
# 备份temp目录（包含SQLite checkpoint）
docker run --rm -v emergency-temp:/data -v $(pwd):/backup \
    alpine tar czf /backup/emergency-temp-backup.tar.gz -C /data .

# 备份logs目录
docker run --rm -v emergency-logs:/data -v $(pwd):/backup \
    alpine tar czf /backup/emergency-logs-backup.tar.gz -C /data .
```

### 更新升级

```bash
# 1. 构建新镜像
./build.sh v1.1.0

# 2. 停止旧服务
docker-compose -f docker-compose.internal.yml down

# 3. 更新镜像标签（编辑docker-compose.internal.yml）
# image: emergency-agents-langgraph:v1.1.0

# 4. 启动新服务
docker-compose -f docker-compose.internal.yml up -d

# 5. 验证升级
curl http://localhost:8008/healthz
docker-compose -f docker-compose.internal.yml logs --tail 50
```

---

## 🔧 故障排查

### 容器无法启动

**症状**：`docker-compose up -d` 后容器立即退出

**排查步骤**：

```bash
# 1. 查看容器日志
docker logs emergency-agents-internal

# 2. 检查配置文件
cat config/env.internal | grep -v '^#' | grep -v '^$'

# 3. 手动运行容器（前台模式）
docker run --rm -it \
    --env-file config/env.internal \
    emergency-agents-langgraph:latest \
    bash

# 4. 容器内测试依赖连接
python3 -c "
from emergency_agents.config import AppConfig
config = AppConfig.load_from_env()
print(f'PostgreSQL: {config.postgres_dsn}')
print(f'Neo4j: {config.neo4j_uri}')
print(f'Qdrant: {config.qdrant_url}')
"
```

### 健康检查失败

**症状**：容器运行但健康检查一直失败

**排查步骤**：

```bash
# 1. 进入容器检查
docker exec -it emergency-agents-internal bash

# 2. 容器内测试健康端点
curl http://localhost:8008/healthz

# 3. 检查服务进程
ps aux | grep uvicorn

# 4. 检查端口监听
netstat -tuln | grep 8008

# 5. 查看Python错误
tail -f /app/logs/emergency-agents.log
```

### 连接外部服务失败

**症状**：日志显示无法连接PostgreSQL/Neo4j/Qdrant

**排查步骤**：

```bash
# 1. 容器内测试网络连通性
docker exec -it emergency-agents-internal bash

# 测试PostgreSQL
apt-get update && apt-get install -y postgresql-client
psql "$POSTGRES_DSN" -c "SELECT 1"

# 测试Neo4j
apt-get install -y curl
curl http://192.168.31.40:7474

# 测试Qdrant
curl http://192.168.31.40:6333/collections

# 测试Redis
apt-get install -y redis-tools
redis-cli -h 192.168.31.40 ping
```

### 内存溢出

**症状**：容器被OOM Killer杀掉

**解决方案**：

```yaml
# 增加内存限制
deploy:
  resources:
    limits:
      memory: 8G  # 从4G增加到8G
```

### 性能问题

**症状**：API响应慢、CPU占用高

**排查步骤**：

```bash
# 1. 查看资源使用
docker stats emergency-agents-internal

# 2. 分析慢查询（如果启用了日志）
grep "duration_ms" /app/logs/emergency-agents.log | sort -t: -k2 -n | tail -20

# 3. 检查LLM调用延迟
grep "llm_call" /app/logs/emergency-agents.log

# 4. Prometheus指标分析
curl http://localhost:8008/metrics | grep http_request_duration
```

---

## 🔐 安全最佳实践

### 1. 使用非root用户

✅ 已配置，容器内使用 UID 1000 的 `emergency` 用户

### 2. 限制资源使用

✅ 已配置 CPU 和内存限制

### 3. 只读文件系统（可选）

如需增强安全性，可添加：

```yaml
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
  - /app/temp
```

### 4. 网络隔离

使用自定义网络，避免暴露不必要的端口：

```yaml
networks:
  emergency-net:
    driver: bridge
    internal: false  # 设为true完全隔离外网
```

### 5. 定期更新基础镜像

```bash
# 定期重新构建以获取安全更新
./build.sh latest
```

---

## 📝 常见问题

### Q1: 如何查看实时日志？

```bash
docker-compose -f docker-compose.internal.yml logs -f
```

### Q2: 如何重启服务？

```bash
docker-compose -f docker-compose.internal.yml restart
```

### Q3: 如何进入容器调试？

```bash
docker exec -it emergency-agents-internal bash
```

### Q4: 如何修改环境变量？

1. 编辑 `config/env.internal`
2. 重启服务：`docker-compose -f docker-compose.internal.yml restart`

### Q5: 如何清理旧镜像？

```bash
# 查看镜像
docker images | grep emergency-agents

# 删除旧镜像
docker rmi emergency-agents-langgraph:old-tag

# 清理未使用的镜像
docker image prune -a
```

### Q6: 如何切换到外网环境？

```bash
# 使用外网配置文件
docker run -d --env-file config/env.external ...

# 或修改docker-compose.yml中的env_file
```

---

## 📚 参考资料

- [Docker官方文档](https://docs.docker.com/)
- [Docker Compose文档](https://docs.docker.com/compose/)
- [项目主文档](./CLAUDE.md)
- [API规范](./API_SPECIFICATION.md)
- [快速开始](./QUICK-START.md)

---

**部署完成后，访问 http://localhost:8008/healthz 验证服务状态！**
