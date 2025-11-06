#!/bin/bash
# AI应急大脑 - Docker镜像构建脚本（使用代理）

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

IMAGE_NAME="emergency-agents-langgraph"
IMAGE_TAG="${1:-latest}"
PROXY="http://127.0.0.1:10809"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI应急大脑 - Docker镜像构建（外网环境+代理）${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "镜像名称: ${GREEN}${IMAGE_NAME}${NC}"
echo -e "镜像标签: ${GREEN}${IMAGE_TAG}${NC}"
echo -e "代理配置: ${GREEN}${PROXY}${NC}"
echo ""

# 检查env.external
if [ ! -f "config/env.external" ]; then
    echo -e "${RED}错误: config/env.external不存在${NC}"
    exit 1
fi

echo -e "${BLUE}开始构建（这可能需要10-15分钟）...${NC}"
docker build \
    --build-arg http_proxy="${PROXY}" \
    --build-arg https_proxy="${PROXY}" \
    --build-arg APP_ENV=external \
    --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
    --tag "${IMAGE_NAME}:latest" \
    --file Dockerfile \
    --progress=plain \
    .

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ 构建成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    docker images | grep "$IMAGE_NAME" | head -n 2
    echo ""
    echo -e "后续步骤："
    echo -e "1. 测试运行: ${BLUE}./run-external.sh${NC}"
    echo -e "2. 导出镜像: ${BLUE}docker save ${IMAGE_NAME}:${IMAGE_TAG} | gzip > emergency-agents-${IMAGE_TAG}.tar.gz${NC}"
    echo -e "3. 部署生产: ${BLUE}docker-compose -f docker-compose.external.yml up -d${NC}"
else
    echo -e "${RED}构建失败！${NC}"
    exit 1
fi
