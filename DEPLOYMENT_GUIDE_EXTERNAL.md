# AI应急大脑 - 外网生产环境部署指南

## 📦 打包完成信息

- **构建时间**: 2025-11-06
- **环境类型**: 外网生产环境（APP_ENV=external）
- **镜像名称**: emergency-agents-langgraph:latest
- **镜像大小**: 1.68GB（未压缩）
- **压缩包**: emergency-agents-external-20251106-0954.tar.gz
- **压缩包大小**: 488M

## 📋 已创建的文件

### 构建脚本
- `build-external.sh` - 外网环境构建脚本（不使用代理）
- `build-with-proxy.sh` - 使用代理的构建脚本
- `check-build.sh` - 构建状态检查脚本
- `export-image.sh` - 镜像导出脚本

### 运行脚本
- `run-external.sh` - 外网环境测试运行脚本

### 配置文件
- `docker-compose.external.yml` - 外网环境编排配置
- `config/env.external` - 外网环境变量配置

### 日志文件
- `build-external.log` - 构建日志
- `build.pid` - 构建进程PID

## 🚀 部署步骤

### 方式1：本地测试（推荐先测试）

```bash
# 1. 测试运行
./run-external.sh

# 2. 查看日志
docker logs -f emergency-agents-test-external

# 3. 健康检查
curl http://localhost:8008/healthz

# 4. 停止测试
docker stop emergency-agents-test-external
docker rm emergency-agents-test-external
```

### 方式2：使用Docker Compose部署生产环境

```bash
# 1. 启动服务
docker-compose -f docker-compose.external.yml up -d

# 2. 查看状态
docker-compose -f docker-compose.external.yml ps

# 3. 查看日志
docker-compose -f docker-compose.external.yml logs -f

# 4. 重启服务
docker-compose -f docker-compose.external.yml restart

# 5. 停止服务
docker-compose -f docker-compose.external.yml down
```

### 方式3：部署到远程服务器

#### Step 1: 传输镜像到服务器

```bash
# 方式A: 使用scp传输
scp emergency-agents-external-20251106-0954.tar.gz user@server:/tmp/

# 方式B: 使用rsync传输（更快，支持断点续传）
rsync -avz --progress emergency-agents-external-20251106-0954.tar.gz user@server:/tmp/
```

#### Step 2: 在服务器上加载镜像

```bash
# 登录服务器
ssh user@server

# 加载镜像
docker load -i /tmp/emergency-agents-external-20251106-0954.tar.gz

# 验证镜像
docker images | grep emergency-agents-langgraph
```

#### Step 3: 传输配置文件

```bash
# 在本地机器执行
scp -r config docker-compose.external.yml user@server:~/emergency-agents/
```

#### Step 4: 启动服务

```bash
# 在服务器上执行
cd ~/emergency-agents
docker-compose -f docker-compose.external.yml up -d

# 查看状态
docker-compose -f docker-compose.external.yml ps

# 健康检查
curl http://localhost:8008/healthz
```

## ⚙️ 配置说明

### 环境变量（config/env.external）

关键配置项：

```bash
# 数据库连接
QDRANT_URL=http://8.147.130.215:6333
NEO4J_URI=bolt://8.147.130.215:7687
POSTGRES_DSN=postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent
REDIS_URL=redis://8.147.130.215:16379/0

# LLM服务
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-flash

# 语音服务
DASHSCOPE_API_KEY=sk-xxx
```

### Docker Compose配置（docker-compose.external.yml）

```yaml
services:
  emergency-agents:
    image: emergency-agents-langgraph:latest
    container_name: emergency-agents-external
    restart: unless-stopped

    # 环境配置
    env_file:
      - ./config/env.external
    environment:
      APP_ENV: external  # 指定使用外网环境

    # 端口映射
    ports:
      - "8008:8008"

    # 资源限制（生产环境）
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
```

## 🔍 验证部署

### 1. 健康检查

```bash
curl http://localhost:8008/healthz

# 预期输出
{
  "status": "healthy",
  "timestamp": "2025-11-06T09:54:00Z",
  "dependencies": {
    "postgres": "connected",
    "neo4j": "connected",
    "qdrant": "connected",
    "redis": "connected"
  }
}
```

### 2. 查看日志

```bash
# 实时日志
docker-compose -f docker-compose.external.yml logs -f

# 最近100行
docker logs emergency-agents-external --tail 100

# 查看错误日志
docker logs emergency-agents-external 2>&1 | grep -i error
```

### 3. 性能监控

```bash
# Prometheus指标
curl http://localhost:8008/metrics

# Docker资源使用
docker stats emergency-agents-external
```

## 🛠️ 故障排查

### 问题1: 服务无法启动

**症状**: 容器启动后立即退出

**排查步骤**:

```bash
# 1. 查看容器日志
docker logs emergency-agents-external

# 2. 检查配置文件
cat config/env.external | grep -v '^#' | grep -v '^$'

# 3. 手动运行容器（前台模式）
docker run --rm -it \
    --env-file config/env.external \
    -e APP_ENV=external \
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

### 问题2: 健康检查失败

**症状**: 容器运行但健康检查一直失败

**排查步骤**:

```bash
# 1. 进入容器检查
docker exec -it emergency-agents-external bash

# 2. 容器内测试健康端点
curl http://localhost:8008/healthz

# 3. 检查服务进程
ps aux | grep uvicorn

# 4. 检查端口监听
netstat -tuln | grep 8008

# 5. 查看Python错误
tail -f /app/logs/emergency-agents.log
```

### 问题3: 连接外部服务失败

**症状**: 日志显示无法连接 PostgreSQL/Neo4j/Qdrant

**排查步骤**:

```bash
# 1. 容器内测试网络连通性
docker exec -it emergency-agents-external bash

# 测试 PostgreSQL
apt-get update && apt-get install -y postgresql-client
psql "$POSTGRES_DSN" -c "SELECT 1"

# 测试 Neo4j
curl http://8.147.130.215:7474

# 测试 Qdrant
curl http://8.147.130.215:6333/collections

# 测试 Redis
apt-get install -y redis-tools
redis-cli -h 8.147.130.215 -p 16379 ping
```

## 🔄 更新升级

### 升级新版本

```bash
# 1. 停止旧服务
docker-compose -f docker-compose.external.yml down

# 2. 加载新镜像
docker load -i /tmp/emergency-agents-external-NEW_DATE.tar.gz

# 3. 备份数据卷（可选）
docker run --rm -v emergency-temp-external:/data -v $(pwd):/backup \
    alpine tar czf /backup/emergency-temp-backup-$(date +%Y%m%d).tar.gz -C /data .

# 4. 启动新服务
docker-compose -f docker-compose.external.yml up -d

# 5. 验证升级
curl http://localhost:8008/healthz
docker-compose -f docker-compose.external.yml logs --tail 50
```

### 回滚到旧版本

```bash
# 1. 停止当前服务
docker-compose -f docker-compose.external.yml down

# 2. 查看历史镜像
docker images | grep emergency-agents-langgraph

# 3. 修改docker-compose.yml指定旧版本镜像ID
# image: emergency-agents-langgraph:<OLD_IMAGE_ID>

# 4. 启动旧版本
docker-compose -f docker-compose.external.yml up -d
```

## 📊 监控指标

### Prometheus指标

关键指标说明：

```
# HTTP请求
http_requests_total                    # 请求总数
http_request_duration_seconds          # 请求延迟

# 系统资源
process_cpu_seconds_total              # CPU使用时间
process_resident_memory_bytes          # 内存使用

# 业务指标
llm_request_duration_seconds           # LLM调用延迟
db_query_duration_seconds              # 数据库查询延迟
```

### 日志查询

```bash
# 查看LLM调用
docker logs emergency-agents-external | grep "llm_call"

# 查看慢查询
docker logs emergency-agents-external | grep "slow_query"

# 查看错误
docker logs emergency-agents-external | grep -i "error\|exception"

# 统计请求数
docker logs emergency-agents-external | grep "http_request" | wc -l
```

## 🔐 安全建议

### 1. 网络安全

```bash
# 仅暴露必要端口
ports:
  - "127.0.0.1:8008:8008"  # 仅本地访问

# 使用防火墙
ufw allow 8008/tcp
ufw enable
```

### 2. 数据安全

```bash
# 定期备份数据卷
docker run --rm -v emergency-temp-external:/data -v /backup:/backup \
    alpine tar czf /backup/emergency-$(date +%Y%m%d).tar.gz -C /data .

# 设置备份定时任务
0 2 * * * /path/to/backup.sh
```

### 3. 日志轮转

```yaml
# 在docker-compose.yml中配置
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "20"
```

## 📞 技术支持

- **项目文档**: /home/msq/gitCode/new_1/emergency-agents-langgraph/CLAUDE.md
- **API文档**: /home/msq/gitCode/new_1/emergency-agents-langgraph/API_SPECIFICATION.md
- **快速开始**: /home/msq/gitCode/new_1/emergency-agents-langgraph/QUICK-START.md

---

**部署完成后，访问 http://localhost:8008/healthz 验证服务状态！**
