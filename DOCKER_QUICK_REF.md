# Docker部署 - 快速参考卡片

## 🚀 一键部署

```bash
# 完整流程（3步）
./build.sh && ./run.sh && docker logs -f emergency-agents-test
```

## 📋 常用命令速查

### 构建相关

```bash
./build.sh              # 构建最新版本
./build.sh v1.0.0       # 构建指定版本
docker images           # 查看镜像列表
```

### 运行相关

```bash
# 测试运行
./run.sh
docker logs -f emergency-agents-test

# 生产运行
docker-compose -f docker-compose.internal.yml up -d
docker-compose -f docker-compose.internal.yml logs -f
```

### 状态检查

```bash
curl http://localhost:8008/healthz                      # 健康检查
curl http://localhost:8008/metrics                      # Prometheus指标
docker ps | grep emergency                              # 容器状态
docker stats emergency-agents-internal                  # 资源使用
```

### 日志查看

```bash
docker logs emergency-agents-internal                   # 全部日志
docker logs -f emergency-agents-internal                # 实时日志
docker logs --tail 100 emergency-agents-internal        # 最近100行
docker logs --since 10m emergency-agents-internal       # 最近10分钟
```

### 容器操作

```bash
docker exec -it emergency-agents-internal bash          # 进入容器
docker restart emergency-agents-internal                # 重启容器
docker stop emergency-agents-internal                   # 停止容器
docker rm -f emergency-agents-internal                  # 删除容器
```

### Docker Compose

```bash
docker-compose -f docker-compose.internal.yml up -d     # 启动
docker-compose -f docker-compose.internal.yml ps        # 状态
docker-compose -f docker-compose.internal.yml logs -f   # 日志
docker-compose -f docker-compose.internal.yml restart   # 重启
docker-compose -f docker-compose.internal.yml down      # 停止并删除
```

## 🔧 故障排查速查

### 容器无法启动

```bash
docker logs emergency-agents-internal
docker run --rm -it --env-file config/env.internal emergency-agents-langgraph:latest bash
```

### 健康检查失败

```bash
docker exec -it emergency-agents-internal curl http://localhost:8008/healthz
docker exec -it emergency-agents-internal ps aux | grep uvicorn
```

### 连接数据库失败

```bash
docker exec -it emergency-agents-internal bash
# 容器内测试
psql "$POSTGRES_DSN" -c "SELECT 1"
curl http://192.168.31.40:6333/collections
```

### 性能问题

```bash
docker stats emergency-agents-internal
curl http://localhost:8008/metrics | grep duration
```

## 📦 镜像管理

```bash
# 导出镜像
docker save emergency-agents-langgraph:latest | gzip > emergency-agents.tar.gz

# 导入镜像
docker load -i emergency-agents.tar.gz

# 清理旧镜像
docker image prune -a

# 查看镜像大小
docker images emergency-agents-langgraph
```

## 🔄 更新升级

```bash
# 1. 构建新版本
./build.sh v1.1.0

# 2. 停止旧服务
docker-compose -f docker-compose.internal.yml down

# 3. 编辑docker-compose.internal.yml，修改image标签

# 4. 启动新服务
docker-compose -f docker-compose.internal.yml up -d

# 5. 验证
curl http://localhost:8008/healthz
```

## 📊 监控指标

```bash
# Prometheus指标
curl http://localhost:8008/metrics

# 关键指标
- http_requests_total               # 请求总数
- http_request_duration_seconds     # 请求延迟
- process_cpu_seconds_total         # CPU使用
- process_resident_memory_bytes     # 内存使用
```

## 🔐 安全检查

```bash
# 检查容器运行用户
docker exec emergency-agents-internal whoami  # 应为emergency

# 检查进程
docker top emergency-agents-internal

# 检查网络
docker inspect emergency-agents-internal | grep -A 10 NetworkSettings
```

## 💾 数据备份

```bash
# 备份持久化数据
docker run --rm -v emergency-temp:/data -v $(pwd):/backup \
    alpine tar czf /backup/emergency-temp-backup.tar.gz -C /data .

# 恢复数据
docker run --rm -v emergency-temp:/data -v $(pwd):/backup \
    alpine tar xzf /backup/emergency-temp-backup.tar.gz -C /data
```

## 🌐 部署到远程服务器

```bash
# 方式1：使用部署脚本
DEPLOY_SERVER=192.168.31.40 ./deploy-internal.sh

# 方式2：手动传输
docker save emergency-agents-langgraph:latest | gzip > emergency-agents.tar.gz
scp emergency-agents.tar.gz user@192.168.31.40:/tmp/
ssh user@192.168.31.40 "docker load -i /tmp/emergency-agents.tar.gz"
```

## 📝 配置修改

```bash
# 修改环境变量
vim config/env.internal

# 重启服务使配置生效
docker-compose -f docker-compose.internal.yml restart

# 验证配置
docker exec emergency-agents-internal env | grep POSTGRES
```

## 🚨 紧急操作

```bash
# 立即停止服务
docker stop emergency-agents-internal

# 强制删除容器
docker rm -f emergency-agents-internal

# 回滚到旧版本
docker tag emergency-agents-langgraph:latest emergency-agents-langgraph:backup
docker tag emergency-agents-langgraph:v1.0.0 emergency-agents-langgraph:latest
docker-compose -f docker-compose.internal.yml up -d
```

---

**详细文档**: 查看 [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
