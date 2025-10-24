#!/usr/bin/env bash
# WSL2 smart proxy bootstrapper (Mihomo/Clash) chaining to Windows v2rayN SOCKS5
# Default: HTTP 7890 / SOCKS5 7891 locally; upstream to $WIN_IP:10808
# Usage:
#   bash scripts/wsl-proxy-up.sh start   # generate config + start
#   bash scripts/wsl-proxy-up.sh stop    # stop process
#   bash scripts/wsl-proxy-up.sh status  # show ports and PID
#   bash scripts/wsl-proxy-up.sh show-config

set -euo pipefail

ACTION=${1:-start}
PORT_HTTP=${PORT_HTTP:-7890}
PORT_SOCKS=${PORT_SOCKS:-7891}
UPSTREAM_SOCKS_PORT=${UPSTREAM_SOCKS_PORT:-10808}
CFG=${CFG:-/tmp/wsl-mihomo.yaml}
LOG=${LOG:-/tmp/wsl-mihomo.log}

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$REPO_ROOT/mihomo-linux-amd64"

if [[ ! -x "$BIN" ]]; then
  echo "[ERR] 找不到可执行文件: $BIN" >&2
  echo "提示: 确保仓库根目录存在 'mihomo-linux-amd64' 且有执行权限 (chmod +x)" >&2
  exit 1
fi

get_win_ip() {
  # WSL2: /etc/resolv.conf 的 nameserver 通常指向 Windows 虚拟网关
  awk '/nameserver/ {print $2; exit}' /etc/resolv.conf
}

start_proxy() {
  local WIN_IP
  WIN_IP=${WIN_IP:-$(get_win_ip)}
  if [[ -z "$WIN_IP" ]]; then
    echo "[ERR] 未能自动解析 Windows 主机 IP (nameserver)" >&2
    exit 1
  fi

  cat > "$CFG" <<YAML
port: $PORT_HTTP
socks-port: $PORT_SOCKS
allow-lan: true
mode: rule
log-level: info

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  default-nameserver: [119.29.29.29, 223.5.5.5, 1.1.1.1]
  nameserver: [223.5.5.5, 1.1.1.1]

proxies:
  - name: win-v2rayn
    type: socks5
    server: $WIN_IP
    port: $UPSTREAM_SOCKS_PORT

proxy-groups:
  - name: PROXY
    type: select
    proxies: [win-v2rayn]

  - name: DEFAULT
    type: select
    proxies: [DIRECT, PROXY]

rules:
  # 内网与本地域名直连
  - DOMAIN-SUFFIX,local,DIRECT
  - DOMAIN-SUFFIX,lan,DIRECT
  - DOMAIN-SUFFIX,home.arpa,DIRECT
  # 常见保留网段直连
  - IP-CIDR,10.0.0.0/8,DIRECT
  - IP-CIDR,172.16.0.0/12,DIRECT
  - IP-CIDR,192.168.0.0/16,DIRECT
  - IP-CIDR,169.254.0.0/16,DIRECT
  - IP-CIDR,127.0.0.0/8,DIRECT
  - IP-CIDR,100.64.0.0/10,DIRECT
  # 国内直连（需要内置 GeoIP 数据）
  - GEOIP,CN,DIRECT
  # 其他全部走代理
  - MATCH,PROXY
YAML

  echo "[INFO] 生成配置: $CFG"
  echo "[INFO] 上游 SOCKS5: $WIN_IP:$UPSTREAM_SOCKS_PORT (Windows v2rayN)"

  # 若已在运行，先停止
  if pgrep -f "$BIN -f $CFG" >/dev/null 2>&1; then
    echo "[INFO] 已在运行，先停止旧进程"
    stop_proxy || true
  fi

  echo "[INFO] 启动 Mihomo 本地代理... (HTTP:$PORT_HTTP, SOCKS5:$PORT_SOCKS)"
  nohup "$BIN" -f "$CFG" >"$LOG" 2>&1 &
  sleep 0.8
  status_proxy
}

stop_proxy() {
  if pgrep -f "$BIN -f $CFG" >/dev/null 2>&1; then
    pkill -f "$BIN -f $CFG" || true
    sleep 0.5
  fi
  echo "[INFO] 已停止 (如仍在监听，手动检查进程)"
}

status_proxy() {
  if pgrep -f "$BIN -f $CFG" >/dev/null 2>&1; then
    local pid
    pid=$(pgrep -f "$BIN -f $CFG" | head -n1)
    echo "[OK] 运行中，PID=$pid"
  else
    echo "[WARN] 未运行"
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp | (egrep ":($PORT_HTTP|$PORT_SOCKS)\s" || true)
  fi
  echo "[LOG] tail -n 50 $LOG"
  tail -n 50 "$LOG" 2>/dev/null || true
}

case "$ACTION" in
  start) start_proxy ;;
  stop)  stop_proxy ;;
  status) status_proxy ;;
  show-config) cat "$CFG" ;;
  *) echo "Usage: $0 {start|stop|status|show-config}" ; exit 2 ;;
esac

