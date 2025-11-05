#!/bin/bash
# AI应急大脑 - Docker容器测试运行脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# 配置
IMAGE_NAME="emergency-agents-langgraph"
CONTAINER_NAME="emergency-agents-test"
PORT=8008
ENV_FILE="config/env.internal"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI应急大脑 - 测试运行${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查镜像是否存在
if ! docker images | grep -q "$IMAGE_NAME"; then
    echo -e "${RED}错误: 镜像 ${IMAGE_NAME} 不存在${NC}"
    echo -e "请先运行: ${BLUE}./build.sh${NC}"
    exit 1
fi

# 检查env.internal是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}错误: 环境配置文件 ${ENV_FILE} 不存在${NC}"
    exit 1
fi

# 停止并删除旧容器（如果存在）
if docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo -e "${BLUE}[1/4] 停止并删除旧容器...${NC}"
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
else
    echo -e "${BLUE}[1/4] 未发现旧容器${NC}"
fi

# 启动容器
echo -e "${BLUE}[2/4] 启动新容器...${NC}"
docker run -d \
    --name "$CONTAINER_NAME" \
    --env-file "$ENV_FILE" \
    -p "$PORT:$PORT" \
    -v "$(pwd)/temp:/app/temp" \
    -v "$(pwd)/logs:/app/logs" \
    --restart unless-stopped \
    "$IMAGE_NAME:latest"

# 等待服务启动
echo -e "${BLUE}[3/4] 等待服务启动...${NC}"
sleep 5

# 健康检查
echo -e "${BLUE}[4/4] 健康检查...${NC}"
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf "http://localhost:$PORT/healthz" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 服务健康检查通过！${NC}"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "重试 $RETRY_COUNT/$MAX_RETRIES ..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}✗ 健康检查失败，查看日志：${NC}"
    docker logs "$CONTAINER_NAME" --tail 50
    exit 1
fi

# 显示容器信息
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 容器启动成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "容器名称: ${GREEN}${CONTAINER_NAME}${NC}"
echo -e "访问地址: ${GREEN}http://localhost:${PORT}${NC}"
echo ""
echo -e "常用命令："
echo -e "  查看日志: ${BLUE}docker logs -f ${CONTAINER_NAME}${NC}"
echo -e "  进入容器: ${BLUE}docker exec -it ${CONTAINER_NAME} bash${NC}"
echo -e "  停止容器: ${BLUE}docker stop ${CONTAINER_NAME}${NC}"
echo -e "  删除容器: ${BLUE}docker rm -f ${CONTAINER_NAME}${NC}"
echo ""
echo -e "测试API："
echo -e "  健康检查: ${BLUE}curl http://localhost:${PORT}/healthz${NC}"
echo -e "  Prometheus: ${BLUE}curl http://localhost:${PORT}/metrics${NC}"
echo ""
