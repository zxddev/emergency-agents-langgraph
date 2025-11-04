#!/bin/bash
# 诊断和修复服务启动问题

echo "=========================================="
echo "应急救援系统启动诊断"
echo "=========================================="

# 1. 检查当前运行的服务
echo -e "\n1. 检查运行中的Python进程..."
ps aux | grep uvicorn | grep -v grep || echo "  没有找到uvicorn进程"

# 2. 杀死卡住的进程
echo -e "\n2. 停止卡住的服务..."
pkill -f "uvicorn emergency_agents.api.main:app"
sleep 2
echo "  进程已停止"

# 3. 检查依赖服务
echo -e "\n3. 检查依赖服务连接..."

# PostgreSQL
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/8.147.130.215/19532" 2>/dev/null; then
    echo "  ✅ PostgreSQL (8.147.130.215:19532) 可达"
else
    echo "  ❌ PostgreSQL 不可达"
fi

# Neo4j
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/192.168.31.40/7687" 2>/dev/null; then
    echo "  ✅ Neo4j (192.168.31.40:7687) 可达"
else
    echo "  ❌ Neo4j 不可达 - 建议启动本地Docker"
fi

# Qdrant
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/192.168.31.40/6333" 2>/dev/null; then
    echo "  ✅ Qdrant (192.168.31.40:6333) 可达"
else
    echo "  ❌ Qdrant 不可达 - 建议启动本地Docker"
fi

echo -e "\n=========================================="
echo "修复建议："
echo "=========================================="
echo ""
echo "选项1: 启动本地Docker服务（推荐）"
echo "  export POSTGRES_PASSWORD=rescue_password"
echo "  export NEO4J_AUTH=neo4j/neo4jzmkj123456"
echo "  docker-compose -f docker-compose.dev.yml up -d postgres neo4j qdrant"
echo "  sleep 10  # 等待服务启动"
echo ""
echo "选项2: 使用降级模式（无KG/RAG功能）"
echo "  修改代码让服务在依赖不可用时仍能启动"
echo ""
echo "选项3: 检查远程服务器"
echo "  确认 192.168.31.40 上的 Neo4j 和 Qdrant 服务正在运行"
echo ""
