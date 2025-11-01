#!/usr/bin/env bash
set -euo pipefail

# 开发启动脚本：在本地虚拟环境中后台启动 Uvicorn，并将日志写入 temp/server.log
# 要求：已创建 .venv，并在 config/dev.env 中配置必要环境变量

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  echo "FATAL: .venv not found. Please create and install dependencies first." >&2
  exit 1
fi

mkdir -p temp

# 加载环境变量（与 SOP 约定：配置集中于 config/dev.env）
set -a
source config/llm_keys.env
source config/dev.env
set +a

# 端口可通过环境变量覆盖，默认 8008
PORT="${PORT:-8008}"

# 禁用代理干扰（httpx 若检测到 SOCKS 代理会要求 socksio 依赖）
# 仅对本地开发生效：确保 127.0.0.1/localhost 直连
export NO_PROXY=${NO_PROXY:-127.0.0.1,localhost}
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true

# 后台启动并记录 PID
# 可通过 RELOAD=0 关闭热重载（默认开启）
RELOAD=${RELOAD:-1}
UVICORN_ARGS=("uvicorn" "emergency_agents.api.main:app" "--host" "0.0.0.0" "--port" "$PORT")
if [[ "$RELOAD" == "1" ]]; then
  UVICORN_ARGS+=("--reload")
fi

# 记录命令行，便于追溯
echo "${UVICORN_ARGS[*]}" > temp/uvicorn.cmdline

source .venv/bin/activate
export PYTHONPATH=src
nohup "${UVICORN_ARGS[@]}" > temp/server.log 2>&1 &
echo $! > temp/uvicorn.pid

echo "Uvicorn started on :$PORT (pid=$(cat temp/uvicorn.pid))"
echo "Logs: $ROOT_DIR/temp/server.log"

