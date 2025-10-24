#!/usr/bin/env bash
# 数据库初始化脚本 - 自动初始化 PostgreSQL、Neo4j、Qdrant

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

echo "==================================="
echo "数据库初始化脚本"
echo "==================================="

# 加载环境变量
if [[ -f config/dev.local.env ]]; then
  echo "✓ 加载配置: config/dev.local.env"
  set -a
  source config/dev.local.env
  set +a
elif [[ -f config/dev.env ]]; then
  echo "⚠ 使用默认配置: config/dev.env (建议创建 dev.local.env)"
  set -a
  source config/dev.env
  set +a
else
  echo "❌ 错误: 找不到配置文件"
  exit 1
fi

# 检查虚拟环境
if [[ ! -d .venv ]]; then
  echo "❌ 错误: .venv 不存在"
  exit 1
fi

source .venv/bin/activate
export PYTHONPATH=src

# 检查 PostgreSQL
echo ""
echo "1️⃣ 检查 PostgreSQL..."
if [[ -n "${POSTGRES_DSN:-}" ]] && command -v psql &> /dev/null; then
  if psql "${POSTGRES_DSN}" -c "SELECT 1" &> /dev/null; then
    echo "✓ PostgreSQL 连接成功"
  else
    echo "❌ PostgreSQL 连接失败"
    exit 1
  fi
fi

# 初始化 Neo4j
echo ""
echo "2️⃣ 初始化 Neo4j..."
if [[ -n "${NEO4J_URI:-}" ]]; then
  python -m emergency_agents.graph.kg_seed
  echo "✓ Neo4j 初始化完成"
fi

# 检查 Qdrant
echo ""
echo "3️⃣ 检查 Qdrant..."
if [[ -n "${QDRANT_URL:-}" ]] && command -v curl &> /dev/null; then
  curl -s "${QDRANT_URL}/healthz" &> /dev/null && echo "✓ Qdrant 连接成功"
fi

echo ""
echo "✅ 初始化完成！"
