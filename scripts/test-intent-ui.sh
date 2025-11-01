#!/usr/bin/env bash
set -euo pipefail

# 调用 AI 大脑 /intent/process，验证 UI 桥接（camera_flyto / toggle_layer）

API="${API:-http://localhost:8008}"
USER_ID="${USER_ID:-demo_user}"
THREAD_ID="${THREAD_ID:-thread-$(date +%s)-$RANDOM}"
MSG="${MSG:-把镜头飞到经度120.10纬度30.20缩放12}"

BODY=$(cat <<JSON
{
  "user_id": "${USER_ID}",
  "thread_id": "${THREAD_ID}",
  "message": "${MSG}",
  "metadata": {"source": "curl"}
}
JSON
)

echo "POST ${API}/intent/process"
curl -sS -X POST "${API}/intent/process" -H 'Content-Type: application/json' -d "${BODY}" | jq -C . || true

echo "\n提示：若前端收到 UI 指令，地图应执行对应动作；Java 网关日志会记录 publish 与 /app/ui/ack。"

