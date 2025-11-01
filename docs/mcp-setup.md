# MCP 配置与自检清单

## 1. 配置基础
- Codex 配置文件：`/home/msq/.codex/config.toml`（WSL 中可通过 `\\wsl.localhost\Ubuntu\home\msq\.codex\config.toml` 编辑）。
- 修改完成后重启 Codex CLI，让新的 MCP 进程重新拉起。
- 统一把临时凭据写入 `~/.mcp-auth`，如需清理可执行 `rm -rf ~/.mcp-auth/*`。

## 2. 本地 MCP 服务
| 服务 | 关键修改 | 自检命令 |
| ---- | -------- | -------- |
| `ddg` | 使用 `npx -y duckduckgo-mcp-server@0.1.2` 并启用 `NODE_OPTIONS=--dns-result-order=ipv4first` | ```codex mcp test ddg tools.list``` |
| `context7` / `exa` / `mcp-deepwiki` / `open-websearch` / `playwright` / `postgres` / `repomix` / `sequential-thinking` / `spec-workflow` / `tavily` | 配置保持不变；只需在 Codex 中运行 `codex mcp test <server> tools.list` 验证能列出工具即可 | ```codex mcp test <server> tools.list``` |
| `serena` | 新增 `--mode interactive --mode editing --transport stdio`，并预留 `SERENA_OPENAI_API_KEY` | 1. 设置 Key：```uvx --from git+https://github.com/oraios/serena serena config set openai.api_key "<你的OpenAI Key>"```<br>2. 本地拉起检查：```uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context codex --mode interactive --mode editing --transport stdio```（看到 “Serena MCP server ready” 后 Ctrl+C 停止）<br>3. Codex 自检：```codex mcp test serena tools.list``` |

> 说明：`codex mcp test ...` 会自动启动目标 MCP 并调用 `tools.list`，若看到返回 JSON 列出工具即代表配置成功。

## 3. 远程 MCP（需人工授权）

### 3.1 Exa Remote
1. 预置命令（已写入 `config.toml`）：
   ```
   npx -y mcp-remote@latest https://mcp.exa.ai/mcp --header Authorization:${EXA_REMOTE_AUTH}
   ```
   环境变量 `EXA_REMOTE_AUTH` 已设置为 `Bearer 0add159f-c855-4742-8f79-8dab5b67c7c5`。
2. 首次授权：在任意终端执行下列命令完成 OAuth & 工具列表握手（需要打开浏览器并允许访问时同意即可）：  
   ```
   npx -p mcp-remote@latest mcp-remote-client https://mcp.exa.ai/mcp --header "Authorization: Bearer 0add159f-c855-4742-8f79-8dab5b67c7c5"
   ```
   出现 `Connected successfully!` 后自动写入 `~/.mcp-auth`。
3. Codex 验证：  
   ```
   codex mcp test exa-remote tools.list
   ```

### 3.2 Tavily Remote
1. 预置命令：  
   ```
   npx -y mcp-remote@latest "https://mcp.tavily.com/mcp/?tavilyApiKey=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" --debug
   ```
2. 首次授权：  
   ```
   npx -p mcp-remote@latest mcp-remote-client "https://mcp.tavily.com/mcp/?tavilyApiKey=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"
   ```
   看到 `Connected successfully!` 表示完成。
3. Codex 验证：  
   ```
   codex mcp test tavily-remote tools.list
   ```

### 3.3 其他 SSH 远程（AIssh / aliyun215mcp / ssh-local / ssh-survey118）
- 这些服务器使用 `@fangjunjie/ssh-mcp-server`，需要保证对应主机在线且允许密码登录。
- 自检命令：  
  ```
  codex mcp test AIssh tools.list
  codex mcp test aliyun215mcp tools.list
  codex mcp test ssh-local tools.list
  codex mcp test ssh-survey118 tools.list
  ```

## 4. 常见诊断命令
- 清除远程凭据：`rm -rf ~/.mcp-auth/*`
- 查看 Codex MCP 日志：`tail -n 200 ~/.codex/log/mcp.log`
- 强制刷新单个服务：`codex mcp restart <server>`

按上述清单依次执行即可确保所有 MCP 在 Codex CLI 中可被调用。***
