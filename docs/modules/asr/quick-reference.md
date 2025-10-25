# ASR自动降级系统 - 快速参考

## 快速开始

### 1. 配置环境变量 (config/dev.env)

```bash
# 阿里云百炼API Key
DASHSCOPE_API_KEY=your_api_key_here
# 阿里云 ASR 超时时间（秒，默认60，最低30）
ALIYUN_ASR_TIMEOUT_SECONDS=60

# 本地FunASR WebSocket URL
VOICE_ASR_WS_URL=wss://127.0.0.1:10097

# 故障转移配置
ASR_PRIMARY_PROVIDER=aliyun
ASR_FALLBACK_PROVIDER=local
HEALTH_CHECK_INTERVAL=30
```

### 2. 基本使用

```python
from emergency_agents.voice.asr.service import ASRService

# 创建服务
asr = ASRService()

# 启动健康检查（推荐）
await asr.start_health_check()

# 识别
audio = open("audio.pcm", "rb").read()
result = await asr.recognize(audio)

print(f"结果: {result.text}")
print(f"Provider: {result.provider}")
print(f"延迟: {result.latency_ms}ms")

# 停止健康检查
await asr.stop_health_check()
```

## Provider对比

| Provider | 优先级 | 精度 | 延迟 | 适用场景 |
|----------|--------|------|------|----------|
| **阿里云百炼** | 100 | 95% | 300-600ms | 在线环境 |
| **本地FunASR** | 0 | 90% | 600-1200ms | 离线环境 |

## 自动降级流程

```
1. 选择Provider → 阿里云（健康） / 本地（备用）
2. 尝试识别
3. 失败 → 自动切换到备用Provider
4. 返回结果
```

## 常用命令

### 验证安装
```bash
python3 -c "from src.emergency_agents.voice.asr.service import ASRService; print('✓ OK')"
```

### 运行示例
```bash
python3 src/emergency_agents/voice/asr/example_usage.py
```

### 查看Provider状态
```python
status = asr.provider_status
# {'aliyun': True, 'local': True}
```

## 日志关键字

| Event | 说明 |
|-------|------|
| `asr_recognize_start` | 识别开始 |
| `asr_recognize_success` | 识别成功 |
| `asr_recognize_failed` | 识别失败 |
| `asr_fallback` | 自动降级 |
| `asr_fallback_success` | 降级后成功 |
| `health_check_complete` | 健康检查完成 |
| `service_recovered` | 服务恢复 |

## 故障排查

### 问题: 阿里云无法连接
```bash
# 检查
echo $DASHSCOPE_API_KEY
# 应该输出你的API Key
```

### 问题: 本地ASR无法连接
```bash
# 检查服务
curl -k wss://127.0.0.1:10097
# 或
telnet 127.0.0.1 10097
```

### 问题: 两个都失败
```python
# 查看日志
logger.info("provider_status", status=asr.provider_status)
```

## 文档链接

- [使用文档](src/emergency_agents/voice/asr/README.md) - 完整使用指南
- [实现总结](ASR_IMPLEMENTATION_SUMMARY.md) - 技术细节
- [验证报告](ASR_VERIFICATION_REPORT.md) - 测试结果
- [业务分析](ASR_BUSINESS_LOGIC_ANALYSIS.md) - 设计分析

## 联系支持

如有问题，请查看日志文件并参考上述文档。
