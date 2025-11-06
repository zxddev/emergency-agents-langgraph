#!/bin/bash
# AI应急大脑 - 外网环境测试运行脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# 配置
IMAGE_NAME="emergency-agents-langgraph:latest"
CONTAINER_NAME="emergency-agents-test-external"
ENV_FILE="./config/env.external"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI应急大脑 - 外网环境测试${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查env.external是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}错误: $ENV_FILE 不存在${NC}"
    exit 1
fi

# 停止并删除已存在的测试容器
if docker ps -a | grep -q "$CONTAINER_NAME"; then
    echo -e "${BLUE}停止并删除已存在的测试容器...${NC}"
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
fi

# 启动容器
echo -e "${BLUE}启动测试容器...${NC}"
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --env-file "$ENV_FILE" \
    -e APP_ENV=external \
    -e LOG_LEVEL=INFO \
    -p 8008:8008 \
    -v "$(pwd)/temp:/app/temp" \
    -v "$(pwd)/logs:/app/logs" \
    "$IMAGE_NAME"

# 等待服务启动
echo -e "${BLUE}等待服务启动（最多30秒）...${NC}"
for i in {1..30}; do
    if docker exec "$CONTAINER_NAME" curl -sf http://localhost:8008/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 服务启动成功！${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ 服务启动超时${NC}"
        docker logs "$CONTAINER_NAME" --tail 50
        exit 1
    fi
    echo -n "."
    sleep 1
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 测试容器运行成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "容器名称: ${GREEN}${CONTAINER_NAME}${NC}"
echo -e "访问地址: ${GREEN}http://localhost:8008/healthz${NC}"
echo ""
echo -e "常用命令："
echo -e "  查看日志: ${BLUE}docker logs -f ${CONTAINER_NAME}${NC}"
echo -e "  查看状态: ${BLUE}docker ps | grep ${CONTAINER_NAME}${NC}"
echo -e "  进入容器: ${BLUE}docker exec -it ${CONTAINER_NAME} bash${NC}"
echo -e "  停止容器: ${BLUE}docker stop ${CONTAINER_NAME}${NC}"
echo -e "  删除容器: ${BLUE}docker rm ${CONTAINER_NAME}${NC}"
echo ""
