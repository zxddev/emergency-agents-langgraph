#!/bin/bash
# AI应急大脑 - Docker镜像构建脚本（外网环境）

set -e  # 遇到错误立即退出

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
IMAGE_NAME="emergency-agents-langgraph"
IMAGE_TAG="${1:-latest}"  # 默认标签为latest，可通过参数指定
DOCKERFILE="Dockerfile"
BUILD_CONTEXT="."
ENV_TYPE="external"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI应急大脑 - Docker镜像构建（外网环境）${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "镜像名称: ${GREEN}${IMAGE_NAME}${NC}"
echo -e "镜像标签: ${GREEN}${IMAGE_TAG}${NC}"
echo -e "环境类型: ${GREEN}${ENV_TYPE}${NC}"
echo -e "构建上下文: ${GREEN}${BUILD_CONTEXT}${NC}"
echo ""

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker未安装或不在PATH中${NC}"
    exit 1
fi

# 检查Dockerfile是否存在
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}错误: Dockerfile不存在${NC}"
    exit 1
fi

# 检查env.external是否存在
if [ ! -f "config/env.external" ]; then
    echo -e "${RED}错误: config/env.external不存在，请先配置外网环境变量${NC}"
    exit 1
fi

# 验证env.external配置
echo -e "${BLUE}[1/5] 验证配置文件...${NC}"
if ! grep -q "QDRANT_URL" config/env.external; then
    echo -e "${YELLOW}警告: config/env.external 中未找到 QDRANT_URL 配置${NC}"
fi

# 显示构建信息
echo -e "${BLUE}[2/5] 清理旧镜像...${NC}"
docker images | grep "$IMAGE_NAME" || true

# 构建镜像
echo -e "${BLUE}[3/5] 开始构建镜像...${NC}"
docker build \
    --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
    --tag "${IMAGE_NAME}:latest" \
    --file "${DOCKERFILE}" \
    --progress=plain \
    --build-arg APP_ENV=external \
    "${BUILD_CONTEXT}"

if [ $? -ne 0 ]; then
    echo -e "${RED}构建失败！${NC}"
    exit 1
fi

# 显示镜像信息
echo -e "${BLUE}[4/5] 构建完成！镜像信息：${NC}"
docker images | grep "$IMAGE_NAME" | head -n 2

# 显示镜像大小
IMAGE_SIZE=$(docker images --format "{{.Size}}" "${IMAGE_NAME}:${IMAGE_TAG}" | head -n 1)
echo -e "镜像大小: ${GREEN}${IMAGE_SIZE}${NC}"

# 镜像历史（可选，用于调试）
echo ""
echo -e "${BLUE}[5/5] 镜像层级信息（前10层）：${NC}"
docker history "${IMAGE_NAME}:${IMAGE_TAG}" | head -n 11

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 构建成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "后续步骤："
echo -e "1. 测试运行: ${BLUE}./run-external.sh${NC}"
echo -e "2. 部署到生产: ${BLUE}docker-compose -f docker-compose.external.yml up -d${NC}"
echo -e "3. 查看日志: ${BLUE}docker-compose -f docker-compose.external.yml logs -f${NC}"
echo -e "4. 导出镜像: ${BLUE}docker save ${IMAGE_NAME}:${IMAGE_TAG} -o emergency-agents-${IMAGE_TAG}-external.tar${NC}"
echo -e "5. 推送到仓库: ${BLUE}docker tag ${IMAGE_NAME}:${IMAGE_TAG} registry.example.com/${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo ""
