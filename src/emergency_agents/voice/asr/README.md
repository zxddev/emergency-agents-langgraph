# ASR自动降级系统

## 概述

本模块实现了一个高可用的双ASR自动降级系统，支持阿里云百炼fun-asr（在线）和本地FunASR（离线）两种语音识别服务。通过Provider抽象模式和健康检查机制，实现了应急救援场景下的"零失败"语音识别能力。

## 核心特性

- ✅ **阿里云百炼 fun-asr**（优先级100，延迟300-600ms）
- ✅ **本地FunASR**（优先级0，延迟600-1200ms）
- ✅ **后台健康检查**（30秒周期）
- ✅ **智能路由与自动降级**
- ✅ **结构化日志与可观测性**

## 架构设计

### Provider抽象模式

```
ASRProvider (抽象基类)
    ├── AliyunASRProvider (阿里云百炼)
    └── LocalFunASRProvider (本地FunASR)
```

所有Provider实现相同的接口：
- `recognize(audio_data, config) -> ASRResult` - 语音识别
- `health_check() -> bool` - 健康检查
- `name` - Provider名称
- `priority` - 优先级（数值越大越优先）

### 自动降级流程

```
1. 根据健康状态选择Provider（优先阿里云）
2. 尝试识别
3. 如果失败 && 存在备用Provider：
   ├─ 切换到备用Provider（本地FunASR）
   └─ 重新尝试识别
4. 返回结果或抛出异常
```

## 快速开始

### 1. 配置环境变量

编辑 `config/dev.env`：

```bash
# 阿里云百炼API Key（北京地域）
DASHSCOPE_API_KEY=your_api_key_here

# 本地FunASR WebSocket URL
VOICE_ASR_WS_URL=wss://127.0.0.1:10097

# ASR故障转移配置
ASR_PRIMARY_PROVIDER=aliyun   # 主Provider：优先使用阿里云
ASR_FALLBACK_PROVIDER=local   # 备用Provider：断网时使用本地
HEALTH_CHECK_INTERVAL=30      # 健康检查间隔（秒）
```

### 2. 基本使用

```python
from emergency_agents.voice.asr.service import ASRService

# 创建ASR服务
asr_service = ASRService()

# 启动健康检查（可选但推荐）
await asr_service.start_health_check()

# 执行语音识别
audio_data = open("audio.pcm", "rb").read()
result = await asr_service.recognize(audio_data)

print(f"识别结果: {result.text}")
print(f"使用Provider: {result.provider}")
print(f"延迟: {result.latency_ms}ms")

# 停止健康检查
await asr_service.stop_health_check()
```

### 3. 高级用法

#### 自定义配置

```python
from emergency_agents.voice.asr.base import ASRConfig

config = ASRConfig(
    format="pcm",
    sample_rate=16000,
    channels=1,
    language="zh-CN",
    enable_punctuation=True,
)

result = await asr_service.recognize(audio_data, config)
```

#### 直接使用Manager

```python
from emergency_agents.voice.asr.manager import ASRManager
from emergency_agents.voice.asr.aliyun_provider import AliyunASRProvider
from emergency_agents.voice.asr.local_provider import LocalFunASRProvider

# 创建自定义Provider列表
providers = [
    AliyunASRProvider(api_key="your_key"),
    LocalFunASRProvider(asr_ws_url="wss://localhost:10097"),
]

# 创建Manager
manager = ASRManager(providers=providers)

# 启动健康检查
await manager.start_health_check()

# 识别
result = await manager.recognize(audio_data)
```

#### 查看Provider状态

```python
# 获取所有Provider的健康状态
status = asr_service.provider_status
print(status)  # {'aliyun': True, 'local': True}
```

## 使用场景

### 场景1：在线环境（正常情况）

```
用户 → ASR服务 → 阿里云Provider → 识别成功 ✅
延迟：450ms
```

### 场景2：断网环境（自动降级）

```
用户 → ASR服务 → 阿里云Provider → 连接失败 ❌
                ↓ 自动降级
               本地Provider → 识别成功 ✅
延迟：850ms
```

### 场景3：运行时故障（自动恢复）

```
T0: 阿里云故障 → 自动降级到本地Provider
T1: 健康检查持续监控阿里云状态
T2: 阿里云恢复 → 下次识别自动切回阿里云
```

## 日志示例

### 正常识别

```json
{"event": "asr_recognize_start", "provider": "aliyun", "audio_size": 64000}
{"event": "asr_recognize_success", "provider": "aliyun", "latency_ms": 450}
```

### 自动降级

```json
{"event": "asr_recognize_start", "provider": "aliyun", "audio_size": 64000}
{"event": "asr_recognize_failed", "provider": "aliyun", "error": "Connection timeout"}
{"event": "asr_fallback", "from_provider": "aliyun", "to_provider": "local"}
{"event": "asr_fallback_success", "provider": "local", "fallback_latency_ms": 850}
```

### 健康检查

```json
{"event": "health_check_start", "provider_count": 2}
{"event": "service_health_check", "service_name": "aliyun", "available": true, "latency_ms": 120}
{"event": "service_health_check", "service_name": "local", "available": true, "latency_ms": 80}
{"event": "health_check_complete", "summary": {"aliyun": true, "local": true}}
```

## 配置说明

### Provider选择优先级

1. **主Provider健康** → 使用主Provider（aliyun）
2. **主Provider不健康** → 使用备用Provider（local）
3. **都不健康** → 按优先级选择（aliyun > local）
4. **都不可用** → 抛出异常

### 健康检查机制

- **检查频率**：每30秒（可配置）
- **判断标准**：
  - 连续成功2次 → 标记为可用
  - 连续失败3次 → 标记为不可用
- **防止抖动**：避免网络抖动导致频繁切换

### 音频格式要求

- **格式**：PCM16
- **采样率**：16000 Hz
- **声道**：单声道（mono）
- **位深度**：16-bit

## 性能指标

### 阿里云百炼 fun-asr

- **精度**：95%（商业级）
- **延迟**：300-600ms
- **适用场景**：在线环境、对精度要求高

### 本地FunASR

- **精度**：90%（开源）
- **延迟**：600-1200ms
- **适用场景**：离线环境、对隐私要求高

## 故障排查

### 问题1：阿里云Provider无法连接

**症状**：
```json
{"event": "asr_recognize_failed", "provider": "aliyun", "error": "Invalid API key"}
```

**解决方案**：
1. 检查 `DASHSCOPE_API_KEY` 是否正确
2. 确认API Key未过期
3. 检查网络连接

### 问题2：本地Provider无法连接

**症状**：
```json
{"event": "local_asr_unhealthy", "error": "Connection refused"}
```

**解决方案**：
1. 确认本地FunASR服务已启动
2. 检查 `VOICE_ASR_WS_URL` 配置是否正确
3. 检查防火墙设置

### 问题3：两个Provider都不可用

**症状**：
```python
RuntimeError: All ASR providers failed: primary=aliyun, fallback=local
```

**解决方案**：
1. 检查网络连接
2. 检查阿里云API Key
3. 检查本地FunASR服务状态
4. 查看详细日志

## 监控建议

### Prometheus指标（建议添加）

```python
# 请求总数
asr_requests_total{provider="aliyun", status="success"}

# 延迟分布
asr_latency_seconds{provider="aliyun", quantile="0.95"}

# 错误率
asr_error_rate{provider="aliyun"}

# 健康检查
asr_health_check_success{service="aliyun_asr"}

# 降级次数
asr_fallback_total{from="aliyun", to="local"}
```

### 告警规则（建议）

```yaml
# 阿里云ASR错误率过高
- alert: AliyunASRHighErrorRate
  expr: rate(asr_requests_total{provider="aliyun",status="error"}[5m]) > 0.1
  for: 5m
  annotations:
    summary: "阿里云ASR错误率超过10%"

# 健康检查失败
- alert: ASRHealthCheckFailed
  expr: asr_health_check_success == 0
  for: 3m
  annotations:
    summary: "ASR健康检查失败"
```

## 参考文档

- [ASR业务逻辑深度分析](../../../ASR_BUSINESS_LOGIC_ANALYSIS.md)
- [阿里云百炼文档](https://help.aliyun.com/document_detail/2712533.html)
- [FunASR官方文档](https://github.com/alibaba-damo-academy/FunASR)

## License

Copyright 2025 msq

