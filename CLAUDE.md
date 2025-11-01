<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**AI应急大脑与全空间智能车辆系统** - 基于LangGraph的级联灾害AI智能体编排系统，专门用于地震级联灾害响应（地震→洪水→山体滑坡→化工泄露）。

> ⚠️ **重要补充**：本项目的 LangGraph 流程规范必须与官方 LangGraph Skill 保持同步。所有开发者在 Claude Code 中接入 Skill Seeker 后，应加载 `langgraph` Skill（见下文“LangGraph Skill 使用规范”），并按照其中的最佳实践执行状态机设计、持久化策略与人工审核流程。

### 核心架构特点
- **LangGraph状态机**: 智能体编排 + 人工审批中断点
- **5个核心AI智能体**: 态势感知、风险预测、方案生成、装备推荐、决策解释
- **多租户支持**: 通过checkpoint_ns实现租户隔离
- **三重数据存储**: PostgreSQL(状态) + Neo4j(知识图谱) + Qdrant(向量检索)
- **意图识别系统**: 分类器 + 验证器 + 路由器 + 槽位填充
- **语音对话系统**: ASR(阿里云/本地) + VAD + 意图处理 + TTS

### 当前状态
- **完成度**: ~15%（API框架、意图识别、语音系统已完成）
- **待实现**: 5个核心AI智能体的业务逻辑
- **开发重点**: Day 1目标是实现态势感知智能体，证明AI能工作

## 常用开发命令

### 环境准备
```bash
# 检查Python版本 (需要 >= 3.10)
python --version

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 开发服务启动
```bash
# 推荐：后台启动开发服务器
./scripts/dev-run.sh

# 前台启动（调试用）
set -a && source config/dev.env && set +a && \
export PYTHONPATH=src && \
python -m uvicorn emergency_agents.api.main:app --reload --port 8008

# 健康检查
curl http://localhost:8008/healthz

# 查看服务日志
tail -f temp/server.log

# 停止后台服务
kill $(cat temp/uvicorn.pid) 2>/dev/null || true
```

### 测试命令
```bash
# 快速单元测试（无外部依赖）
pytest -m unit -v

# 集成测试（需要Neo4j/Qdrant/PostgreSQL）
pytest -m integration -v

# 运行单个测试文件
pytest tests/test_health.py -v

# 运行特定测试函数
pytest tests/test_intent_flow_integration.py::test_rescue_intent_complete_flow -v

# 核心功能验证
pytest tests/test_health.py tests/test_intent_flow_integration.py -v
```

### 数据库管理
```bash
# 启动开发数据库服务（Docker）
docker-compose -f docker-compose.dev.yml up -d

# 停止数据库服务
docker-compose -f docker-compose.dev.yml down

# 检查环境配置
./scripts/check-env.sh

# 健康检查所有依赖服务
./scripts/health-check.sh
```

## 代码规范和约定

### 核心开发规则（来自AGENTS.md）
遵循AGENTS.md中的4阶段交互流程：
1. **问题对齐阶段**: 理解需求，复述确认
2. **方案对齐阶段**: 给出方案，确认影响和关键点
3. **执行阶段**: 用户确认后开始执行
4. **交付阶段**: 自测完成后交付用户测试

### 语言要求
- **注释**: 使用中文注释说明业务逻辑
- **变量命名**: 英文命名，中文注释
- **错误信息**: 中文错误信息便于用户理解
- **文档**: API文档和技术文档用中文编写

### 代码风格
- 使用Python 3.10+ 类型注解
- 遵循PEP 8规范
- 函数必须有docstring说明
- 错误必须处理，不允许"吞掉"异常
- 优先使用卫语句 (Guard Clauses)

### 项目特定约定

#### 配置管理
- 环境变量集中配置在 `config/dev.env`
- 敏感信息通过环境变量配置，不硬编码
- 开发环境使用远程服务器 8.147.130.215 (Neo4j/Qdrant/PostgreSQL)

#### 测试标记
- `@pytest.mark.unit`: 单元测试（无外部依赖）
- `@pytest.mark.integration`: 集成测试（需要外部服务）

#### 数据库模式
- **PostgreSQL**: LangGraph checkpoint + 审计日志
- **Neo4j**: 知识图谱，支持级联灾害关系（TRIGGERS/COMPOUNDS）
- **Qdrant**: 向量存储，按Domain分类（规范/案例/地理/装备）

## 系统架构

### LangGraph状态机流转
```
用户输入 → 报告受理 → 意图识别 → 槽位验证
                              ↓
                        [路由决策]
                              ↓
    ┌─────────────────────────┴─────────────────────────┐
    │                                                     │
救援流程                                            助手问答
    ↓                                                     ↓
态势分析 → 风险预测 → 方案生成 → 人工审批中断点      RAG检索 + 记忆管理
    ↓                                                     ↓
执行方案 → 装备推荐 → 决策解释 → 完成            生成回答 + 引用来源
```

### 核心组件详解

#### 1. 意图识别系统 (`src/emergency_agents/intent/`)
**关键特性**：
- **分类器** (`classifier.py`): 基于LLM的意图分类（救援/查询/通用）
- **验证器** (`validator.py`): 槽位填充验证（必填字段检查）
- **路由器** (`router.py`): 动态路由到对应处理节点
- **提示补全** (`prompt_missing.py`): 主动询问缺失信息

**意图类型**：
- `RESCUE_TASK_GENERATION`: 救援任务生成（需要灾情上下文）
- `QUERY_RESCUE`: 查询救援信息
- `GENERAL_CHAT`: 通用对话

**槽位定义**：
```python
# 救援意图必填字段
required_slots = ["disaster_type", "location", "severity"]
```

#### 2. 语音对话系统 (`src/emergency_agents/voice/`)
**架构**：
- **ASR服务** (`asr/service.py`): 阿里云百炼 FunASR（主） + 本地FunASR（备用）
- **VAD检测器** (`vad_detector.py`): 语音活动检测（WebRTC VAD）
- **意图处理** (`intent_handler.py`): 语音意图识别和路由
- **TTS客户端** (`tts_client.py`): 文本转语音（Edge TTS）

**自动故障转移**：
- 每30秒健康检查
- 主Provider失败自动切换到备用
- 支持热切换，不中断服务

**配置示例**：
```bash
# config/dev.env
DASHSCOPE_API_KEY=your_key
VOICE_ASR_WS_URL=wss://127.0.0.1:10097
ASR_PRIMARY_PROVIDER=aliyun
ASR_FALLBACK_PROVIDER=local
```

#### 3. 智能体系统 (`src/emergency_agents/agents/`)
每个智能体都是LangGraph节点：
- **态势感知** (`situation.py`): 从非结构化文本提取结构化灾情数据
- **风险预测** (`risk_predictor.py`): 基于KG+RAG预测次生灾害
- **方案生成** (`plan_generator.py`): 生成救援行动方案（需要人工审批）
- **装备推荐**: 推荐装备配置并用KG防幻觉（待实现）
- **决策解释**: 生成可解释的决策报告（待实现）

**关键实现模式**：
```python
def situation_agent(state: Dict[str, Any], llm_client, llm_model: str) -> Dict[str, Any]:
    """
    态势感知智能体

    输入: state["raw_report"] - 非结构化文本报告
    输出: state["situation"] - 结构化JSON数据

    幂等性: 如果situation已存在，直接返回（避免重复LLM调用）
    """
    if "situation" in state and state["situation"]:
        return state  # 幂等性保证

    # LLM调用 + safe_json_parse容错
    # ...
```

#### 4. 车载指挥扩展模块 (`src/emergency_agents/vehicle/`)
**新增功能**（演示版）：
- **视觉分析** (`vision.py`): GLM-4V无人机图像分析
- **装备推荐** (`equipment.py`): RAG+KG混合推理
- **任务优化** (`task_optimizer.py`): OR-Tools智能任务分配

**API端点**：
- `POST /vehicle/vision/analyze` - 视觉分析
- `POST /vehicle/equipment/recommend` - 装备推荐
- `POST /vehicle/task/allocate` - 任务分配

#### 5. 数据服务层
- **记忆管理** (`memory/mem0_facade.py`): 多租户记忆管理（Mem0）
- **RAG检索** (`rag/pipe.py`): 统一RAG检索接口（Qdrant）
- **知识图谱** (`graph/kg_service.py`): 装备推荐、案例检索（Neo4j）

### API设计 (`src/emergency_agents/api/`)
- RESTful API设计原则
- 统一的错误响应格式
- 请求trace_id追踪
- Prometheus监控指标

**核心API端点**：
```
# 救援线程管理
POST   /threads/start         # 启动救援线程
POST   /threads/approve       # 人工审批救援方案
POST   /threads/resume        # 继续执行救援线程
GET    /audit/trail/{id}      # 获取审计轨迹

# 智能助手
POST   /assist/answer         # RAG+记忆问答

# RAG服务
POST   /rag/index             # 批量索引文档
POST   /rag/query             # 检索文档

# 知识图谱
POST   /kg/recommend          # 装备推荐
POST   /kg/cases/search       # 案例检索

# 语音服务
POST   /asr/recognize         # 语音识别
WS     /ws/voice/chat         # 语音对话WebSocket

# 车载指挥（演示版）
POST   /vehicle/vision/analyze          # 视觉分析
POST   /vehicle/equipment/recommend     # 装备推荐
POST   /vehicle/task/allocate           # 任务分配
GET    /vehicle/health                  # 健康检查

# 监控
GET    /healthz               # 健康探针
GET    /metrics               # Prometheus指标
```

## 外部服务配置

### LLM服务
```bash
# 智谱GLM-4（默认）
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_API_KEY=your_api_key
LLM_MODEL=glm-4-flash

# 或本地vLLM
OPENAI_BASE_URL=http://192.168.1.40:8000/v1
LLM_MODEL=qwen2.5-7b-instruct
```

### 数据库连接
```bash
# Neo4j（知识图谱）
NEO4J_URI=bolt://8.147.130.215:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=example-neo4j

# Qdrant（向量存储）
QDRANT_URL=http://8.147.130.215:6333

# PostgreSQL（状态检查点 + 审计）
POSTGRES_DSN=postgresql://rescue:rescue_password@8.147.130.215:19532/rescue_system

# 本地SQLite检查点（开发环境）
CHECKPOINT_SQLITE_PATH=./checkpoints.sqlite3
```

### 语音服务
```bash
# ASR（阿里云百炼）
DASHSCOPE_API_KEY=your_api_key
ASR_PRIMARY_PROVIDER=aliyun

# ASR（本地FunASR WebSocket）
VOICE_ASR_WS_URL=wss://127.0.0.1:10097
ASR_FALLBACK_PROVIDER=local

# TTS（Edge TTS）
VOICE_TTS_URL=http://192.168.31.40:18002/api/tts
VOICE_TTS_VOICE=zh-CN-XiaoxiaoNeural
```

## 关键技术实现模式

### 1. LangGraph中断点（人工审批）
```python
# 错误写法（会报错）
graph.add_node("await", lambda s: {}, interrupt_before=True)  # ❌

# 正确写法
graph.add_node("await", lambda s: {})
app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["await"]  # ✅ 在compile时配置
)
```

### 2. 幂等性保证
所有智能体节点必须支持幂等性（避免重复调用LLM）：
```python
def agent_function(state):
    # 卫语句：如果已有结果，直接返回
    if "result_key" in state and state["result_key"]:
        return state

    # 执行昂贵的LLM调用
    result = call_llm(state)
    return state | {"result_key": result}
```

### 3. JSON解析容错
```python
from emergency_agents.agents.situation import safe_json_parse

# 支持多种格式：
# 1. 纯JSON
# 2. Markdown代码块中的JSON
# 3. 文本中嵌入的JSON
structured = safe_json_parse(llm_output)
```

### 4. 多租户隔离
```python
# 通过checkpoint_ns实现租户隔离
config = {
    "configurable": {
        "thread_id": f"rescue-{rescue_id}",
        "checkpoint_ns": f"tenant-{user_id}"  # 租户命名空间
    }
}
result = graph_app.invoke(state, config=config)
```

### 5. 动态中断恢复
```python
# 人工审批后恢复执行
from langgraph.types import Command

# 方式1：传递审批结果
result = graph_app.invoke(
    Command(resume=approved_ids),  # 注入审批的ID列表
    config={"configurable": {"thread_id": thread_id}}
)

# 方式2：简单继续
result = graph_app.invoke(None, config=config)
```

## 开发流程和最佳实践

### 开发新智能体的标准流程
1. 在 `src/emergency_agents/agents/` 创建新文件
2. 实现智能体函数（输入state，返回state）
3. 确保幂等性（检查state中是否已有结果）
4. 使用safe_json_parse解析LLM输出
5. 在 `src/emergency_agents/graph/app.py` 注册节点
6. 编写单元测试（Mock LLM响应）
7. 编写集成测试（真实LLM调用）

### 测试策略
```python
# 单元测试：Mock LLM
@pytest.mark.unit
def test_situation_agent_with_mock():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    # ...

# 集成测试：真实LLM
@pytest.mark.integration
def test_situation_agent_integration():
    from emergency_agents.llm.client import get_openai_client
    from emergency_agents.config import AppConfig
    client = get_openai_client(AppConfig.load_from_env())
    # ...
```

### 调试技巧
```bash
# 1. 查看详细日志
tail -f temp/server.log | grep -i error

# 2. 测试LLM连接
python -c "
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig
client = get_openai_client(AppConfig.load_from_env())
resp = client.chat.completions.create(
    model='glm-4-flash',
    messages=[{'role': 'user', 'content': '你好'}],
    temperature=0
)
print(resp.choices[0].message.content)
"

# 3. 检查数据库连接
./scripts/health-check.sh

# 4. 查看Prometheus指标
curl http://localhost:8008/metrics
```

## 故障排查

### 常见问题

#### LLM连接失败
```bash
# 检查配置
grep OPENAI config/dev.env

# 测试连接
curl -X POST "$OPENAI_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"hi"}]}'
```

#### 数据库连接问题
```bash
# 检查Neo4j
docker exec -it neo4j cypher-shell -u neo4j -p example-neo4j

# 检查PostgreSQL
psql "$POSTGRES_DSN" -c "SELECT 1"

# 检查Qdrant
curl http://8.147.130.215:6333/collections
```

#### ASR识别失败
```bash
# 查看Provider状态
curl http://localhost:8008/healthz

# 测试阿里云ASR
curl -X POST http://localhost:8008/asr/recognize \
  -F "file=@test.pcm" -F "sample_rate=16000" -F "fmt=pcm"

# 查看ASR日志
tail -f temp/server.log | grep -i asr
```

#### WebSocket连接断开
- 检查Token有效性
- 查看服务器日志（temp/server.log）
- 确认网络连接稳定

## 性能要求
- API响应时间 < 100ms（健康检查）
- LLM调用temperature=0（保证稳定性）
- 向量检索top_k限制（避免性能问题）
- ASR识别延迟 < 1秒（阿里云）

## 重要提醒

1. **配置优先**: 始终先检查 `config/dev.env` 配置是否正确
2. **依赖检查**: 确保外部服务（Neo4j/Qdrant/PostgreSQL）可访问
3. **测试驱动**: 新功能必须包含单元测试和集成测试
4. **中文优先**: 注释、文档、错误信息都使用中文
5. **审计追踪**: 所有关键操作都会记录审计日志，支持决策回溯
6. **幂等性**: 所有智能体节点必须支持幂等执行
7. **遵循AGENTS.md**: 严格按照4阶段交互流程开发

开发环境使用远程服务器部署，确保网络连接正常。本地开发推荐使用 `./scripts/dev-run.sh` 后台启动服务。

## 参考文档

- **QUICK-START.md**: 快速开始指南
- **AGENTS.md**: 开发协议和规则（必读）
- **docs/行动计划/ACTION-PLAN-DAY1.md**: Day 1详细任务
- **docs/分析报告/Linus式深度分析-级联灾害AI系统.md**: 深度技术分析
- **ASR_QUICK_REFERENCE.md**: 语音识别快速参考
