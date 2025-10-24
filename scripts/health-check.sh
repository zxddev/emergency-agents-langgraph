#!/usr/bin/env bash
# 服务健康检查脚本

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

# 加载配置
if [[ -f config/dev.local.env ]]; then
  set -a; source config/dev.local.env; set +a
elif [[ -f config/dev.env ]]; then
  set -a; source config/dev.env; set +a
fi

PORT="${PORT:-8008}"

echo "==================================="
echo "服务健康检查"
echo "==================================="

# 检查 API 服务
echo "1️⃣ 检查 API 服务 (localhost:${PORT})..."
if curl -s http://localhost:${PORT}/healthz | grep -q "ok"; then
  echo "✓ API 服务正常"
else
  echo "❌ API 服务异常"
  exit 1
fi

# 检查远程数据库服务
if [[ -n "${QDRANT_URL:-}" ]]; then
  echo "2️⃣ 检查 Qdrant (${QDRANT_URL})..."
  curl -s "${QDRANT_URL}" &> /dev/null && echo "✓ Qdrant 正常" || echo "❌ Qdrant 异常"
fi

if [[ -n "${NEO4J_URI:-}" ]]; then
  echo "3️⃣ 检查 Neo4j (${NEO4J_URI})..."
  echo "  (需要客户端工具，跳过自动检查)"
fi

echo ""
echo "✅ 健康检查完成"
