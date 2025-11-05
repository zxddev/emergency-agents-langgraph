#!/bin/bash
# 检查Docker构建状态的脚本

echo "==================================="
echo "Docker构建状态检查"
echo "==================================="
echo ""

# 检查构建进程
BUILD_PROCS=$(ssh root@8.147.130.215 -p 19522 "ps aux | grep -E 'docker build|buildx' | grep -v grep | wc -l")
echo "构建进程数: $BUILD_PROCS"

if [ "$BUILD_PROCS" -gt 0 ]; then
    echo "状态: 构建进行中..."
else
    echo "状态: 构建已完成或未启动"
fi

echo ""
echo "构建日志（最后20行）:"
echo "-----------------------------------"
ssh root@8.147.130.215 -p 19522 "cd /opt/emergency-agents && tail -20 build.log"

echo ""
echo "Docker镜像列表:"
echo "-----------------------------------"
ssh root@8.147.130.215 -p 19522 "docker images emergency-agents-langgraph"

echo ""
echo "==================================="
