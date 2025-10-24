# Server Deployment & Directory SOP (Unified, Production-Ready)

Goal: provide a repeatable, secure, and performant baseline for deploying heterogeneous services (Java/Python/FE/DB/Cache/LLM/ASR/TTS) with minimal global settings and maximum per-service isolation.

Principles
- Per-service isolation: each服务完整自包含（代码/配置/数据/日志/模型/临时）
- 全局仅放复用资源：模型与数据集只读复用；容器根目录集中管理
- 稳定路径：对外发布的路径长期稳定；迁移用符号链接兼容
- I/O 热点在 NVMe：重读写全部落在 `/data`（NVMe），系统盘仅承载 OS 与轻量配置
- 可审计与可回滚：固定镜像版本；带健康检查；配置与脚本可追溯

One-time Bootstrap（一次性初始化）
```bash
sudo mkdir -p \
  /data/{projects,models,datasets/{raw,work,eval},docker/compose,venvs,conda/{pkgs,envs},caches/{pip,torch,huggingface,gradle,maven/.m2},logs,tmp,backup,secrets}

# Docker 全局（参考 Docker 官方文档：json-file 轮转配置项需字符串）
sudo tee /etc/docker/daemon.json <<'JSON'
{
  "data-root": "/data/docker",
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
sudo systemctl restart docker

# 全局缓存（将常用缓存强制到 NVMe 上）
sudo tee /etc/profile.d/caches.sh <<'SH'
export PIP_CACHE_DIR=/data/caches/pip
export TORCH_HOME=/data/caches/torch
export HF_HOME=/data/caches/huggingface
export TRANSFORMERS_CACHE=/data/caches/huggingface
export HF_DATASETS_CACHE=/data/caches/huggingface/datasets
export GRADLE_USER_HOME=/data/caches/gradle
SH
sudo chmod 0644 /etc/profile.d/caches.sh

# Maven 本地仓库（用户级）
mkdir -p ~/.m2 && {
  echo '<settings><localRepository>/data/caches/maven/.m2/repository</localRepository></settings>' > ~/.m2/settings.xml;
}

# 可选：/etc/fstab 为 /data 增加 noatime,nodiratime（按需）
```

OS 基线与硬件验收（建议）
- 时区/NTP：设置 `timedatectl set-timezone Asia/Shanghai`，启用 NTP
- GPU 驱动：固定驱动与 CUDA 版本；`nvidia-smi -pm 1`（持久化）
- 交换/SYSCTL：大内存可 `swapoff -a`；必要时仅配小 swap；按需求调节 THP 等
- 安全：最小开放端口；UFW/防火墙；创建最小权限用户/组；umask 027
- 硬件验收命令：`lscpu`、`dmidecode`、`nvidia-smi -q`、`nvme list`、`ipmitool fru/sdr`、`ethtool -m`

Directory Layout（与《Directory-Layout-Plan.md》一致）
```text
/data
  projects/           # 每个项目/服务自包含
    <stack>/          # 如 java / python / llm / fe / db 等
      <svc>/
        app/         # 代码或构建产物
        conf/        # 配置、.env（敏感信息不明文）
        data/{raw,work,eval}
        models/      # 本服务用模型或指向 /data/models 的链接
        logs/        # 服务日志
        tmp/         # 高频临时文件
  models/            # 组织级可复用模型（只读挂载给服务）
  datasets/{raw,work,eval}
  docker/            # docker data-root 与 compose 栈
  venvs/             # Python venv
  conda/{pkgs,envs}  # Conda 缓存与环境
  caches/{pip,torch,huggingface,gradle,maven/.m2}
  logs/ tmp/ backup/ secrets/
```

命名与分区规范
- 分区：`y=YYYY/m=MM/d=DD/` 或 `ds=YYYY-MM-DD/`；流式可加小时
- 版本：`processed`/`eval` 使用 `v1/`、`v2/` 或语义化版本
- `raw` 只追加（WORM）；重跑新建分区，不覆盖

权限与配额
```bash
# 目录使用 setgid 保持组继承，最小可见
sudo chgrp -R <team> /data/projects/<stack>/<svc>
sudo chmod -R 2750 /data/projects/<stack>/<svc>
```

Docker 全局
- data-root=`/data/docker`（已设置）
- 日志：默认 `json-file` 并启用轮转（或改 `local` 驱动）
- Compose：建议 v2（`docker compose`）

服务模板（Compose，带固定镜像/健康检查）

Python API（推荐自建镜像，不在启动时 pip install）
Dockerfile：
```dockerfile
FROM python:3.11-slim@sha256:<pin>
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
```
compose.yaml：
```yaml
version: "3.9"
services:
  fastapi:
    image: registry.local/fastapi:1.0.0
    working_dir: /app
    env_file: ["./conf/.env"]
    volumes:
      - ./conf:/conf:ro
      - ./data:/data
      - ./models:/models:ro
      - ./logs:/logs
      - /data/models:/shared-models:ro
      - /data/datasets:/shared-datasets:ro
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:8000/healthz"]
      interval: 20s
      timeout: 3s
      retries: 5
    ports: ["8000:8000"]
    restart: unless-stopped
```

Java（Spring Boot JAR）
```yaml
version: "3.9"
services:
  spring:
    image: eclipse-temurin:17-jre@sha256:<pin>
    working_dir: /srv
    command: ["java","-jar","app.jar"]
    volumes:
      - ./app/app.jar:/srv/app.jar:ro
      - ./conf:/conf:ro
      - ./logs:/logs
    environment:
      - JAVA_TOOL_OPTIONS=-XX:+UseContainerSupport -Xms256m -Xmx2g
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:8080/actuator/health"]
      interval: 30s
      timeout: 3s
      retries: 5
    ports: ["8080:8080"]
    restart: unless-stopped
```

Frontend（Nginx 静态托管）
```yaml
version: "3.9"
services:
  web:
    image: nginx:1.27-alpine@sha256:<pin>
    volumes:
      - ./app/dist:/usr/share/nginx/html:ro
      - ./conf/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
    healthcheck:
      test: ["CMD","wget","-qO-","http://localhost/healthz"]
      interval: 30s
      timeout: 3s
      retries: 5
    ports: ["80:80"]
    restart: unless-stopped
```

PostgreSQL
```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16.4@sha256:<pin>
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: Asia/Shanghai
    volumes:
      - ./data/db:/var/lib/postgresql/data
      - ./logs:/logs
    healthcheck:
      test: ["CMD-SHELL","pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 3s
      retries: 10
    ports: ["5432:5432"]
    restart: unless-stopped
```

MySQL
```yaml
version: "3.9"
services:
  mysql:
    image: mysql:8.4@sha256:<pin>
    environment:
      MYSQL_DATABASE: app
      MYSQL_USER: app
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      TZ: Asia/Shanghai
    command: ["--default-authentication-plugin=mysql_native_password"]
    volumes:
      - ./data/db:/var/lib/mysql
    healthcheck:
      test: ["CMD","mysqladmin","ping","-h","localhost","-u","root","-p$$MYSQL_ROOT_PASSWORD"]
      interval: 10s
      timeout: 3s
      retries: 10
    ports: ["3306:3306"]
    restart: unless-stopped
```

Redis
```yaml
version: "3.9"
services:
  redis:
    image: redis:7.4@sha256:<pin>
    command: ["redis-server","--appendonly","yes"]
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD","redis-cli","ping"]
      interval: 10s
      timeout: 2s
      retries: 10
    ports: ["6379:6379"]
    restart: unless-stopped
```

LLM 推理（vLLM；GPU）
```yaml
version: "3.9"
services:
  vllm:
    image: vllm/vllm-openai:0.6.2.post1@sha256:<pin>
    gpus: all  # Compose（非 Swarm）推荐写法
    volumes:
      - /data/models/huggingface/<org>/<model>:/models/<model>:ro
      - ./logs:/logs
      - ./conf:/conf:ro
      - ./data:/data
    environment:
      HF_HOME: /data/projects/llm/<svc>/.cache/hf
    command: ["--model","/models/<model>","--port","8001"]
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:8001/health"]
      interval: 30s
      timeout: 3s
      retries: 10
    ports: ["8001:8001"]
    restart: unless-stopped
```

LLM 推理（Text Generation Inference；GPU）
```yaml
version: "3.9"
services:
  tgi:
    image: ghcr.io/huggingface/text-generation-inference:2.4@sha256:<pin>
    gpus: all
    environment:
      MODEL_ID: /models/<model>
      MAX_INPUT_TOKENS: "4096"
    volumes:
      - /data/models/huggingface/<org>/<model>:/models/<model>:ro
    healthcheck:
      test: ["CMD","curl","-fsS","http://localhost:80/health"]
      interval: 30s
      timeout: 3s
      retries: 10
    ports: ["8080:80"]
    restart: unless-stopped
```

ASR（Vosk）/TTS（Piper）
```yaml
version: "3.9"
services:
  asr:
    image: alphacep/kaldi-vosk-server:0.3@sha256:<pin>
    volumes:
      - /data/models/vosk/<lang>:/opt/vosk-model:ro
    environment:
      VOSK_MODEL_PATH: /opt/vosk-model
    ports: ["2700:2700"]
    restart: unless-stopped
  tts:
    image: rhasspy/piper:1.2.0@sha256:<pin>
    volumes:
      - /data/models/piper:/piper:ro
    command: ["--voice","/piper/<voice>.onnx","--server","--host","0.0.0.0","--port","59125"]
    ports: ["59125:59125"]
    restart: unless-stopped
```

Datasets SOP
- 服务私有：`/data/projects/<stack>/<svc>/data/{raw,work,eval}`
- 组织复用：`/data/datasets/{raw,work,eval}`（只读挂载给服务）
- 分区示例：`raw/y=2025/m=10/d=21/source=foo/`、`work/v2/ds=2025-10-21/`、`eval/v1/task=<name>/`
- 写入规则：仅作者有写权限；共享区由数据平台发布，消费只读

Models SOP
- 默认本地：`/data/projects/<stack>/<svc>/models/<org>/<model>`（可为指向 `/data/models` 的符号链接）
- 组织复用：`/data/models/<org>/<model>`（只读挂载）

Caching（HF/pip/torch 等）
- 全局已在 `/etc/profile.d/caches.sh` 指向 `/data/caches/...`
- 若需服务级隔离，可在 `<svc>/conf/.env` 再次覆盖：
```env
HF_HOME=/data/projects/<stack>/<svc>/.cache/hf
HF_DATASETS_CACHE=/data/projects/<stack>/<svc>/.cache/hf/datasets
PIP_CACHE_DIR=/data/projects/<stack>/<svc>/.cache/pip
```

Logging & Rotation
- 应用日志：写到 `/data/projects/<stack>/<svc>/logs`
- Docker 日志：`json-file` + 轮转（或 `local` 驱动）
- 可在 `<svc>/conf/logrotate.d/<app>` 放置 per-service 轮转策略

备份与恢复
- 建议备份：`/data/projects/*/conf`、`/data/projects/*/app`、`/data/projects/*/data/{raw,eval}`、`/data/secrets`
- 可排除：可再生成的 `work/`、可再拉取的模型/镜像
- restic 示例：
```bash
export RESTIC_REPOSITORY=/data/backup/restic
export RESTIC_PASSWORD=<pass>
restic init || true
restic backup /data/projects /data/secrets --exclude /data/projects/**/work --exclude /data/docker
restic snapshots
```

安全与 Secrets
- 默认只读挂载共享资源；限制 RW 挂载；容器内尽量非 root 用户
- 使用 Docker secrets 或只读挂载文件，不将密钥写入镜像
- `/data/secrets` 权限严格（目录 0700，文件 0400）

监控（建议）
- 导入 Node Exporter、DCGM Exporter 至 Prometheus；Grafana 仪表盘
- 基础健康检查：GPU `nvidia-smi`、磁盘 `fio` 小测、端口存活

验证清单（Go/No-Go）
```bash
# Docker 根目录
docker info --format '{{.DockerRootDir}}'           # 期望 /data/docker
# 全局缓存变量
env | egrep 'PIP_CACHE_DIR|TORCH_HOME|HF_HOME|GRADLE_USER_HOME'
# Compose GPU 生效（容器内）
docker exec -it <svc> nvidia-smi
# 数据/模型路径
ls -1 /data/projects/<stack>/<svc>/data ; ls -1 /data/models | head
```

新服务落地 Runbook（SOP）
```bash
cd /data/projects && sudo mkdir -p <stack>/<svc>/{app,conf,data/{raw,work,eval},models,logs,tmp}
# 写入 compose.yaml 与 conf/.env，挂载卷遵循本文规范
docker compose -f /data/projects/<stack>/<svc>/compose.yaml up -d
```

参考与来源
- Docker 日志驱动与 json-file 轮转（daemon.json）
- Docker Compose（GPU：推荐 gpus: all；多文件/Profiles 等）
- Hugging Face Datasets 缓存与 cache_dir

附录：fstab 建议（按需）
- `/data` 使用 xfs 或 ext4，可加 `noatime,nodiratime`
- 如对 `/data/tmp` 需要限额/归档，可单独分区并设置挂载参数

附录：五层 Linus 式决策模板
1) 数据与所有权：实体/流向/去重
2) 特殊分支：列出 if/else 的缘由，尽可能消除
3) 复杂度：一句话说清本质；列概念，减半
4) 兼容性：不破坏用户路径；迁移用符号链接
5) 实用性：问题是否真实痛点；方案复杂度是否匹配
