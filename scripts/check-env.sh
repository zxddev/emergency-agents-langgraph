#!/usr/bin/env bash
# 环境检查脚本 - 验证开发环境是否就绪

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

ERRORS=0

echo "==================================="
echo "环境检查脚本"
echo "==================================="

# 检查 Python 版本
echo "1️⃣ 检查 Python 版本..."
if command -v python3 &> /dev/null; then
  PY_VERSION=$(python3 --version | awk '{print $2}')
  echo "✓ Python 版本: $PY_VERSION"
  
  # 检查版本是否 >= 3.10
  if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "✓ Python 版本符合要求 (>= 3.10)"
  else
    echo "❌ Python 版本过低，需要 >= 3.10"
    ((ERRORS++))
  fi
else
  echo "❌ Python3 未安装"
  ((ERRORS++))
fi

# 检查虚拟环境
echo ""
echo "2️⃣ 检查虚拟环境..."
if [[ -d .venv ]]; then
  echo "✓ .venv 目录存在"
  
  # 检查是否安装了依赖
  if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
    if python -c "import fastapi" &> /dev/null; then
      echo "✓ 依赖已安装"
    else
      echo "⚠ 依赖未安装或不完整"
      echo "  运行: pip install -r requirements.txt"
    fi
  fi
else
  echo "❌ .venv 不存在"
  echo "  运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  ((ERRORS++))
fi

# 检查配置文件
echo ""
echo "3️⃣ 检查配置文件..."
if [[ -f config/dev.local.env ]]; then
  echo "✓ config/dev.local.env 存在"
  CONFIG_FILE="config/dev.local.env"
elif [[ -f config/dev.env ]]; then
  echo "⚠ 使用默认 config/dev.env"
  echo "  建议: cp config/.env.example config/dev.local.env"
  CONFIG_FILE="config/dev.env"
else
  echo "❌ 配置文件不存在"
  ((ERRORS++))
  CONFIG_FILE=""
fi

# 检查必需环境变量
if [[ -n "$CONFIG_FILE" ]]; then
  echo ""
  echo "4️⃣ 检查必需环境变量..."
  set -a
  source "$CONFIG_FILE"
  set +a
  
  # 检查 LLM API Key
  if [[ -z "${OPENAI_API_KEY:-}" ]] || [[ "${OPENAI_API_KEY}" == "your_api_key_here" ]] || [[ "${OPENAI_API_KEY}" == "dummy" ]]; then
    echo "❌ OPENAI_API_KEY 未配置"
    ((ERRORS++))
  else
    echo "✓ OPENAI_API_KEY 已配置"
  fi
  
  # 检查数据库连接配置
  [[ -n "${QDRANT_URL:-}" ]] && echo "✓ QDRANT_URL 已配置" || echo "⚠ QDRANT_URL 未配置"
  [[ -n "${NEO4J_URI:-}" ]] && echo "✓ NEO4J_URI 已配置" || echo "⚠ NEO4J_URI 未配置"
  [[ -n "${POSTGRES_DSN:-}" ]] && echo "✓ POSTGRES_DSN 已配置" || echo "⚠ POSTGRES_DSN 未配置"
fi

# 检查网络连通性（可选）
echo ""
echo "5️⃣ 检查网络连通性..."
if command -v curl &> /dev/null; then
  if curl -s --connect-timeout 3 http://8.147.130.215:6333 &> /dev/null; then
    echo "✓ 远程服务 8.147.130.215 可访问"
  else
    echo "⚠ 远程服务 8.147.130.215 不可访问"
    echo "  提示: 如需本地开发，使用 docker-compose up"
  fi
fi

# 总结
echo ""
echo "==================================="
if [[ $ERRORS -eq 0 ]]; then
  echo "✅ 环境检查通过！"
  echo "==================================="
  echo ""
  echo "下一步："
  echo "1. 初始化数据库: ./scripts/init-db.sh"
  echo "2. 启动服务: ./scripts/dev-run.sh"
else
  echo "❌ 发现 $ERRORS 个错误"
  echo "==================================="
  exit 1
fi
