# 多阶段构建 - AI应急大脑 Docker镜像
# 基于Python 3.11 Slim镜像（适合生产环境）

FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖（编译期需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libopus-dev \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖（使用pip缓存加速）
# 注意：PyTorch使用CPU版本以减少镜像大小
RUN pip install --no-cache-dir --user \
    torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --user -r requirements.txt

# ============================================
# 生产镜像
# ============================================
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    TZ=Asia/Shanghai

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libopus0 \
    libsndfile1 \
    curl \
    ca-certificates \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户（安全最佳实践）
RUN useradd -m -u 1000 -s /bin/bash emergency && \
    mkdir -p /app/temp /app/logs && \
    chown -R emergency:emergency /app

WORKDIR /app

# 从builder阶段复制Python依赖
COPY --from=builder --chown=emergency:emergency /root/.local /home/emergency/.local

# 复制应用代码
COPY --chown=emergency:emergency src/ ./src/
COPY --chown=emergency:emergency config/ ./config/

# 创建必要的目录
RUN mkdir -p temp logs sql && \
    chown -R emergency:emergency temp logs sql

# 切换到非root用户
USER emergency

# 将用户级pip安装路径加入PATH
ENV PATH=/home/emergency/.local/bin:$PATH

# 健康检查（每30秒检查一次，启动后10秒开始检查）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8008/healthz || exit 1

# 暴露端口
EXPOSE 8008

# 启动命令（使用内网环境配置）
CMD ["uvicorn", "emergency_agents.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8008", \
     "--workers", "1"]
