# Server Deployment Quickstart（10 分钟上手）

用途：给工程师的“一页纸”。复制粘贴即可部署常见服务。完整细节参见 `Server-Deployment-SOP.md`。

1) 一次性初始化（只需执行一次）
```bash
sudo mkdir -p /data/{projects,models,datasets/{raw,work,eval},docker/compose,caches/{pip,torch,huggingface,gradle,maven/.m2},logs,tmp}

# Docker 全局：根目录+日志轮转（新容器生效）
sudo tee /etc/docker/daemon.json <<'JSON'
{
  "data-root": "/data/docker",
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
sudo systemctl restart docker

# 常用缓存转到 NVMe（重新登录生效）
sudo tee /etc/profile.d/caches.sh <<'SH'
export PIP_CACHE_DIR=/data/caches/pip
export TORCH_HOME=/data/caches/torch
export HF_HOME=/data/caches/huggingface
export TRANSFORMERS_CACHE=/data/caches/huggingface
export HF_DATASETS_CACHE=/data/caches/huggingface/datasets
export GRADLE_USER_HOME=/data/caches/gradle
SH
sudo chmod 0644 /etc/profile.d/caches.sh
```

2) 新服务脚手架（每个服务 1 次）
```bash
STACK=python   # 或 java / llm / fe / db
SVC=myapp
mkdir -p /data/projects/$STACK/$SVC/{app,conf,data/{raw,work,eval},models,logs,tmp}
cd /data/projects/$STACK/$SVC
```

3) 最小 Compose 模板（按需三选一，保存为 `compose.yaml`）

- Python API（FastAPI，开发版，启动时安装依赖）
```yaml
version: "3.9"
services:
  api:
    image: python:3.11-slim
    working_dir: /app
    command: bash -lc "pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000"
    volumes:
      - ./app:/app
      - ./conf:/conf:ro
      - ./data:/data
      - ./models:/models:ro
      - ./logs:/logs
      - /data/models:/shared-models:ro
      - /data/datasets:/shared-datasets:ro
    env_file: ["./conf/.env"]
    ports: ["8000:8000"]
    restart: unless-stopped
```

- Java（Spring Boot JAR）
```yaml
version: "3.9"
services:
  app:
    image: eclipse-temurin:17-jre
    working_dir: /srv
    command: ["java","-jar","app.jar"]
    volumes:
      - ./app/app.jar:/srv/app.jar:ro
      - ./conf:/conf:ro
      - ./logs:/logs
    environment:
      - JAVA_TOOL_OPTIONS=-XX:+UseContainerSupport -Xms256m -Xmx2g
    ports: ["8080:8080"]
    restart: unless-stopped
```

- LLM（vLLM，GPU）
```yaml
version: "3.9"
services:
  vllm:
    image: vllm/vllm-openai:latest
    gpus: all
    volumes:
      - /data/models/huggingface/<org>/<model>:/models/<model>:ro
      - ./logs:/logs
      - ./conf:/conf:ro
      - ./data:/data
    command: ["--model","/models/<model>","--port","8001"]
    ports: ["8001:8001"]
    restart: unless-stopped
```

4) 启动与常用命令
```bash
docker compose up -d          # 启动
docker compose logs -f        # 查看日志
docker compose ps             # 查看状态
docker compose down           # 停止并移除
```

5) 标准挂载（建议保持）
- 代码/构建物：`./app`
- 配置：`./conf`（`.env` 放这里）
- 数据：`./data`（服务私有） + `/data/datasets`（组织共享只读）
- 模型：`./models`（私有） + `/data/models`（共享只读）
- 日志：`./logs`

6) 快速自检（通过即可上线）
```bash
docker info --format '{{.DockerRootDir}}'   # 期望 /data/docker
env | egrep 'PIP_CACHE_DIR|HF_HOME'        # 缓存在 /data/caches
ls -1 data ; ls -1 models                  # 目录存在
docker compose ps                          # 容器 healthy / running
```

7) 常见问题
- GPU 看不到：确认已安装 NVIDIA 驱动和 Container Toolkit；Compose 用 `gpus: all`
- 启动慢：Python 开发模板会 `pip install`，生产建议自建镜像（见 SOP 中 Dockerfile 示例）
- 日志过大：已启用 json-file 轮转；应用侧日志写入 `./logs`

8) 推荐：固定镜像版本
- 开发可用 `:latest`，生产请固定 tag 或 digest，便于回滚

更多：详见同目录 `Server-Deployment-SOP.md`（含数据库/缓存/健康检查/备份/监控等完整示例）。

