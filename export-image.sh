#!/bin/bash
# 导出Docker镜像为tar.gz文件

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

IMAGE_NAME="emergency-agents-langgraph:latest"
DATE=$(date +%Y%m%d-%H%M)
OUTPUT_FILE="emergency-agents-external-${DATE}.tar.gz"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}导出Docker镜像${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "镜像: ${GREEN}${IMAGE_NAME}${NC}"
echo -e "输出文件: ${GREEN}${OUTPUT_FILE}${NC}"
echo ""

echo -e "${BLUE}开始导出（这可能需要5-10分钟）...${NC}"
docker save "${IMAGE_NAME}" | gzip > "${OUTPUT_FILE}"

if [ -f "${OUTPUT_FILE}" ]; then
    SIZE=$(du -h "${OUTPUT_FILE}" | cut -f1)
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ 导出成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "文件: ${GREEN}${OUTPUT_FILE}${NC}"
    echo -e "大小: ${GREEN}${SIZE}${NC}"
    echo ""
    echo -e "部署到生产服务器："
    echo -e "1. 传输文件: ${BLUE}scp ${OUTPUT_FILE} user@server:/tmp/${NC}"
    echo -e "2. 加载镜像: ${BLUE}docker load -i /tmp/${OUTPUT_FILE}${NC}"
    echo -e "3. 启动服务: ${BLUE}docker-compose -f docker-compose.external.yml up -d${NC}"
else
    echo -e "${RED}导出失败！${NC}"
    exit 1
fi
