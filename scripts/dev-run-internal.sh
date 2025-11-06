#!/bin/bash

# 内网环境启动脚本
# 仅依赖内网服务，不访问外网（智谱GLM除外）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== 应急救援AI大脑 - 内网环境启动 ===${NC}"

# 1. 加载内网环境配置
echo -e "${YELLOW}[1/5] 加载内网环境配置...${NC}"
if [ ! -f "config/env.internal" ]; then
    echo -e "${RED}错误: config/env.internal 不存在${NC}"
    exit 1
fi

set -a
source config/env.internal
set +a

# 2. 检查Python环境
echo -e "${YELLOW}[2/5] 检查Python虚拟环境...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}虚拟环境不存在，正在创建...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# 3. 创建必要目录
echo -e "${YELLOW}[3/5] 创建工作目录...${NC}"
mkdir -p temp logs

# 4. 检查内网服务连通性（跳过外网服务）
echo -e "${YELLOW}[4/5] 检查内网服务连通性...${NC}"

check_service() {
    local name=$1
    local host=$2
    local port=$3

    if timeout 2 bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name ($host:$port)"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name ($host:$port) - 无法连接"
        return 1
    fi
}

# 检查核心内网服务
check_service "Neo4j" "8.147.130.215" "7687" || echo "  提示: Neo4j可选，不影响基础功能"
check_service "Qdrant" "8.147.130.215" "6333" || echo "  提示: Qdrant可选，不影响基础功能"
check_service "PostgreSQL" "8.147.130.215" "19532" || echo "  提示: PostgreSQL可选，将使用SQLite"

# 5. 启动服务
echo -e "${YELLOW}[5/5] 启动FastAPI服务...${NC}"

export PYTHONPATH=src

# 停止旧进程
if [ -f temp/uvicorn.pid ]; then
    OLD_PID=$(cat temp/uvicorn.pid)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "停止旧进程 (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
fi

# 后台启动服务
nohup python -m uvicorn emergency_agents.api.main:app \
    --host 0.0.0.0 \
    --port 8008 \
    --reload \
    > temp/server.log 2>&1 &

NEW_PID=$!
echo $NEW_PID > temp/uvicorn.pid

echo -e "${GREEN}✓ 服务已启动 (PID: $NEW_PID)${NC}"
echo ""
echo -e "${GREEN}服务地址:${NC}"
echo "  - API: http://localhost:8008"
echo "  - 健康检查: http://localhost:8008/healthz"
echo "  - API文档: http://localhost:8008/docs"
echo ""
echo -e "${YELLOW}查看日志:${NC} tail -f temp/server.log"
echo -e "${YELLOW}停止服务:${NC} kill $NEW_PID"

# 等待服务启动并健康检查
echo ""
echo "等待服务启动..."
for i in {1..15}; do
    if curl -s http://localhost:8008/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 服务健康检查通过${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo -e "${GREEN}=== 内网环境启动完成 ===${NC}"
