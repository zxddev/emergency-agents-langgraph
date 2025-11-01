# 应急智能体服务启动手册

## 1. 环境准备
- 确保本机安装 Python 3.12，推荐使用虚拟环境隔离依赖。
- 创建与激活虚拟环境：
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- 安装项目依赖：
  ```bash
  pip install -r requirements.txt
  ```

## 2. 数据库准备
- 服务默认连接 PostgreSQL：`postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent`。
- 首次运行前需执行建表脚本（会话与消息表）：
  ```bash
  psql postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent \
    -f sql/patches/20251027_conversation_tables.sql
  ```

## 3. 启动服务
1. 激活虚拟环境并加载配置：
   ```bash
   source .venv/bin/activate
   source config/dev.env
   export PYTHONPATH=src
   ```
2. 后台启动 FastAPI：
   ```bash
   nohup .venv/bin/python -m uvicorn emergency_agents.api.main:app \
     --host 0.0.0.0 --port 8008 > temp/uvicorn.log 2>&1 & echo $! > temp/uvicorn.pid
   ```
3. 查看是否启动成功：
   ```bash
   tail -n 40 temp/uvicorn.log
   curl -s http://127.0.0.1:8008/healthz
   ```

## 4. 停止 / 重启
- 查询并终止占用 8008 端口的进程：
  ```bash
  lsof -i :8008
  kill <PID>
  ```
- 如使用 `temp/uvicorn.pid` 记录，可直接：
  ```bash
  kill $(cat temp/uvicorn.pid)
  ```
- 停止后重复第 3 节步骤重新启动。

## 5. 常见问题排查
- **端口被占用**：重复启动前必须清理旧进程，否则 uvicorn 会报 `Errno 98 address already in use`。
- **缺少依赖**：若日志提示 `ModuleNotFoundError: jsonschema`，执行 `pip install -r requirements.txt` 更新依赖。
- **高德 API 超时**：确认 `config/dev.env` 中 `AMAP_API_KEY` 可用，必要时检查网络连通。
- **TTS 备用节点告警**：`VOICE_TTS_URL` 指向的 192.168.20.100 若无响应会持续报 warning，可忽略或更换地址。

## 6. 真实意图验证
- 模拟用户文本请求：
  ```bash
  curl -s -X POST http://127.0.0.1:8008/intent/process \
    -H "Content-Type: application/json" \
    -d '{
      "user_id": "tester",
      "thread_id": "thread-rescue-demo",
      "message": "指挥中心：水磨镇发生地震，大约300人被困，请生成救援任务，mission_type=rescue，坐标103.85,31.68。"
    }'
  ```
- 首次请求若提示缺少字段，根据返回的 `prompt` 继续补充参数，直到 `status` 返回 `success` 并生成救援任务结果。

## 7. 日志查看
- 实时观察后台日志：
  ```bash
  tail -f temp/uvicorn.log
  ```
- 关键模块日志使用 `structlog`，可通过关键字（如 `rescue_task_completed`、`llm_endpoint_success`）定位。
