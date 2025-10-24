#!/usr/bin/env bash
# Source me to export proxy environment variables pointing to local Mihomo
# Usage: source scripts/wsl-proxy-env.sh

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "请使用: source $0" >&2
  exit 1
fi

set -euo pipefail

# Local smart proxy endpoints (from Mihomo started by scripts/wsl-proxy-up.sh)
HTTP_PORT=${HTTP_PORT:-7890}
SOCKS_PORT=${SOCKS_PORT:-7891}

WIN_IP=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf || true)

export HTTP_PROXY="http://127.0.0.1:${HTTP_PORT}"
export HTTPS_PROXY="$HTTP_PROXY"
export ALL_PROXY="socks5h://127.0.0.1:${SOCKS_PORT}"

# Bypass: localhost, LAN, reserved ranges, Windows host IP, local domains
NO_PROXY_LIST="localhost,127.0.0.1,::1,.local,.lan,home.arpa,"
NO_PROXY_LIST+="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10,"
NO_PROXY_LIST+="fc00::/7,fe80::/10,"
if [[ -n "${WIN_IP:-}" ]]; then NO_PROXY_LIST+="$WIN_IP,"; fi

# Optional: bypass .cn 域名（域名匹配并不完美，仅作为补充）
NO_PROXY_CN=${NO_PROXY_CN:-true}
if [[ "$NO_PROXY_CN" == "true" ]]; then
  NO_PROXY_LIST+=".cn,"
fi

# Trim trailing comma
NO_PROXY_LIST=${NO_PROXY_LIST%,}

export NO_PROXY="$NO_PROXY_LIST"

# Lowercase variants for tools that only read lowercase
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export all_proxy="$ALL_PROXY"
export no_proxy="$NO_PROXY"

echo "[OK] Proxy 环境变量已设置到当前 shell (HTTP=$HTTP_PROXY, SOCKS=$ALL_PROXY)"
echo "[INFO] NO_PROXY=$NO_PROXY"

