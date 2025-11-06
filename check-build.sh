#!/bin/bash
# 检查构建状态

if [ -f build.pid ]; then
    PID=$(cat build.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✓ 构建正在进行中 (PID: $PID)"
        echo ""
        echo "=== 最新日志（最后30行）==="
        tail -30 build-external.log
        echo ""
        echo "=== 完整日志 ==="
        echo "查看完整日志: tail -f build-external.log"
    else
        echo "构建已完成或失败"
        echo ""
        echo "=== 构建结果 ==="
        tail -20 build-external.log
        echo ""
        if docker images | grep -q emergency-agents-langgraph; then
            echo "✓ 镜像构建成功！"
            docker images | grep emergency-agents-langgraph
        else
            echo "✗ 镜像构建失败"
        fi
    fi
else
    echo "未找到构建进程"
fi
