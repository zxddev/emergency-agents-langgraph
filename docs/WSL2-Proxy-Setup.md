# WSL2 全量代理（内网与国内直连）

目标：WSL2 中所有常见网络请求（MCP/GitHub/apt/pip 等）默认经代理，内网与国内 IP/域名直连。

## 架构选择（推荐）

- 在 WSL2 内运行本地智能代理层（Mihomo/Clash），对外暴露 HTTP:7890 / SOCKS5:7891。
- 上游出站指向 Windows v2rayN 的 SOCKS5 `10808`（需启用“允许来自局域网的连接”）。
- 通过规则实现：`GEOIP,CN → DIRECT`，RFC1918/LAN/Link-Local → DIRECT，其余 → PROXY。
- 优点：无需 Windows 侧再开 HTTP 代理 10809；apt/docker 等统一指向本地 HTTP 7890 即可。

## 快速开始

1) 启动智能代理

```bash
bash scripts/wsl-proxy-up.sh start    # 生成 /tmp/wsl-mihomo.yaml 并启动 mihomo
```

2) 设置当前 shell 代理环境变量

```bash
source scripts/wsl-proxy-env.sh
```

3) 验证

```bash
curl -I https://www.example.com
curl https://ipinfo.io/ip
```

## 持久化配置

1) Shell 登录统一启用代理环境变量

在 `/etc/profile.d/proxy.sh` 写入（需 sudo）：

```bash
WIN_IP=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf)
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="$HTTP_PROXY"
export ALL_PROXY="socks5h://127.0.0.1:7891"
export NO_PROXY="localhost,127.0.0.1,::1,.local,.lan,home.arpa,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10,fc00::/7,fe80::/10,$WIN_IP,.cn"
export http_proxy="$HTTP_PROXY"; export https_proxy="$HTTPS_PROXY"; export all_proxy="$ALL_PROXY"; export no_proxy="$NO_PROXY"
```

2) APT 代理（HTTP/HTTPS）

`/etc/apt/apt.conf.d/99proxy`（需 sudo）：

```
Acquire::http::Proxy "http://127.0.0.1:7890/";
Acquire::https::Proxy "http://127.0.0.1:7890/";
```

说明：APT 不支持 SOCKS 环境变量，指向本地 HTTP 即可。国内镜像站通常直连更快，本方案由 mihomo 规则决定直连与否。

3) Git

```bash
git config --global http.proxy  "http://127.0.0.1:7890"
git config --global https.proxy "http://127.0.0.1:7890"
```

SSH 仓库（可选，走 SOCKS5）：编辑 `~/.ssh/config`

```
Host github.com
  ProxyCommand nc -X 5 -x 127.0.0.1:7891 %h %p
```

需要 `netcat-openbsd` 或 `connect-proxy`。

4) Pip（可选）

`~/.pip/pip.conf`：

```
[global]
proxy = http://127.0.0.1:7890
```

如需 SOCKS：`pip install pysocks` 并按需配置。

5) Docker

- Docker Desktop（WSL 集成）：优先在 Windows Docker Desktop 设置代理为 `http://127.0.0.1:7890`（走 v2rayN 规则）。
- 原生 Linux Docker（WSL 中，systemd 可用时）：

  `/etc/systemd/system/docker.service.d/http-proxy.conf`：

  ```ini
  [Service]
  Environment="HTTP_PROXY=http://127.0.0.1:7890"
  Environment="HTTPS_PROXY=http://127.0.0.1:7890"
  Environment="NO_PROXY=localhost,127.0.0.1,::1,.local,.lan,home.arpa,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,100.64.0.0/10"
  ```

  重新加载并重启：

  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart docker
  ```

> 注意：`docker pull` 由 daemon 发起，需在 daemon 一侧配置代理；仅设置客户端环境变量不足以生效。

## 运行与维护

- 查看状态：`bash scripts/wsl-proxy-up.sh status`
- 停止：`bash scripts/wsl-proxy-up.sh stop`
- 日志：`tail -f /tmp/wsl-mihomo.log`

## 原则说明

- KISS：统一走本地 HTTP/ SOCKS 端口，最少改动各工具配置。
- YAGNI：先不启用 TUN/透明代理；如确有“全协议透明”需求再升级。
- DRY：集中到 mihomo 规则维护“CN/内网直连”，避免在各工具重复维护 no_proxy 域名清单。
- 单一职责：业务与网络策略解耦；策略由 mihomo 配置与环境变量注入决定。

