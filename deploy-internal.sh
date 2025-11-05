#!/bin/bash
# AI应急大脑 - 内网环境部署脚本
# 适用于生产环境部署到内网服务器（192.168.31.40）

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置
IMAGE_NAME="emergency-agents-langgraph"
IMAGE_TAG="${1:-latest}"
COMPOSE_FILE="docker-compose.internal.yml"
REMOTE_SERVER="${DEPLOY_SERVER:-192.168.31.40}"
REMOTE_USER="${DEPLOY_USER:-msq}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI应急大脑 - 内网部署${NC}"
echo -e "${BLUE}========================================${NC}"

# 部署模式选择
echo -e "${YELLOW}请选择部署模式：${NC}"
echo "1. 本地部署（当前机器）"
echo "2. 远程部署（通过SSH推送镜像）"
echo "3. 仅导出镜像（手动传输）"
read -p "请输入选项 [1-3]: " DEPLOY_MODE

case $DEPLOY_MODE in
    1)
        echo -e "${BLUE}[本地部署模式]${NC}"
        deploy_local
        ;;
    2)
        echo -e "${BLUE}[远程部署模式]${NC}"
        deploy_remote
        ;;
    3)
        echo -e "${BLUE}[导出镜像模式]${NC}"
        export_image
        ;;
    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac

# 本地部署函数
deploy_local() {
    echo -e "${BLUE}[1/3] 检查镜像...${NC}"
    if ! docker images | grep -q "$IMAGE_NAME"; then
        echo -e "${RED}镜像不存在，开始构建...${NC}"
        ./build.sh "$IMAGE_TAG"
    fi

    echo -e "${BLUE}[2/3] 停止旧服务...${NC}"
    docker-compose -f "$COMPOSE_FILE" down || true

    echo -e "${BLUE}[3/3] 启动新服务...${NC}"
    docker-compose -f "$COMPOSE_FILE" up -d

    # 健康检查
    echo -e "${BLUE}等待服务启动...${NC}"
    sleep 10

    check_health
}

# 远程部署函数
deploy_remote() {
    echo -e "${BLUE}[1/5] 检查SSH连接...${NC}"
    if ! ssh -q "${REMOTE_USER}@${REMOTE_SERVER}" exit; then
        echo -e "${RED}SSH连接失败，请检查网络和凭据${NC}"
        exit 1
    fi

    echo -e "${BLUE}[2/5] 导出镜像...${NC}"
    IMAGE_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar"
    docker save "${IMAGE_NAME}:${IMAGE_TAG}" -o "$IMAGE_FILE"

    echo -e "${BLUE}[3/5] 传输镜像到远程服务器...${NC}"
    scp "$IMAGE_FILE" "${REMOTE_USER}@${REMOTE_SERVER}:/tmp/"

    echo -e "${BLUE}[4/5] 在远程服务器加载镜像...${NC}"
    ssh "${REMOTE_USER}@${REMOTE_SERVER}" "docker load -i /tmp/$IMAGE_FILE && rm /tmp/$IMAGE_FILE"

    echo -e "${BLUE}[5/5] 传输配置文件并启动服务...${NC}"
    scp "$COMPOSE_FILE" "${REMOTE_USER}@${REMOTE_SERVER}:~/emergency-agents/"
    scp -r config "${REMOTE_USER}@${REMOTE_SERVER}:~/emergency-agents/"

    ssh "${REMOTE_USER}@${REMOTE_SERVER}" << 'ENDSSH'
        cd ~/emergency-agents
        docker-compose -f docker-compose.internal.yml down || true
        docker-compose -f docker-compose.internal.yml up -d
        sleep 10
        docker-compose -f docker-compose.internal.yml ps
ENDSSH

    # 清理本地临时文件
    rm "$IMAGE_FILE"

    echo -e "${GREEN}✓ 远程部署完成${NC}"
    echo -e "访问地址: ${GREEN}http://${REMOTE_SERVER}:8008/healthz${NC}"
}

# 导出镜像函数
export_image() {
    IMAGE_FILE="${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"

    echo -e "${BLUE}[1/2] 导出镜像...${NC}"
    docker save "${IMAGE_NAME}:${IMAGE_TAG}" | gzip > "$IMAGE_FILE"

    FILE_SIZE=$(du -h "$IMAGE_FILE" | cut -f1)
    echo -e "${BLUE}[2/2] 导出完成${NC}"
    echo -e "文件: ${GREEN}${IMAGE_FILE}${NC}"
    echo -e "大小: ${GREEN}${FILE_SIZE}${NC}"
    echo ""
    echo -e "手动部署步骤："
    echo -e "1. 传输镜像到目标服务器"
    echo -e "   ${BLUE}scp ${IMAGE_FILE} user@server:/tmp/${NC}"
    echo -e "2. 在目标服务器加载镜像"
    echo -e "   ${BLUE}docker load -i /tmp/${IMAGE_FILE}${NC}"
    echo -e "3. 传输配置文件"
    echo -e "   ${BLUE}scp -r config docker-compose.internal.yml user@server:~/emergency-agents/${NC}"
    echo -e "4. 启动服务"
    echo -e "   ${BLUE}docker-compose -f docker-compose.internal.yml up -d${NC}"
}

# 健康检查函数
check_health() {
    echo -e "${BLUE}健康检查...${NC}"

    if curl -sf "http://localhost:8008/healthz" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 服务健康${NC}"

        # 显示服务信息
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}✓ 部署成功！${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        docker-compose -f "$COMPOSE_FILE" ps
        echo ""
        echo -e "访问地址: ${GREEN}http://localhost:8008/healthz${NC}"
        echo -e "查看日志: ${BLUE}docker-compose -f ${COMPOSE_FILE} logs -f${NC}"
    else
        echo -e "${RED}✗ 健康检查失败${NC}"
        docker-compose -f "$COMPOSE_FILE" logs --tail 50
        exit 1
    fi
}

echo ""
