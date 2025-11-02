# 🚀 快速开始指南

> 从这里开始，用最短的时间理解项目并开始工作

---

## 📚 核心文档（按阅读顺序）

### 1️⃣ 了解需求
**[docs/需求/AI应急大脑与全空间智能车辆系统.md](docs/需求/AI应急大脑与全空间智能车辆系统.md)**
- 完整的产品需求：15个模型 + 15个智能体 + 58个功能点
- 阅读时间：10分钟
- 适合：产品经理、技术leader

### 2️⃣ 理解现状
**[docs/分析报告/Linus式深度分析-级联灾害AI系统.md](docs/分析报告/Linus式深度分析-级联灾害AI系统.md)**
- Linus式五层深度思考的完整分析
- 需求 vs 现实的差距、AI使用策略、可行的实现路线
- 阅读时间：30-45分钟
- 适合：所有开发人员

### 3️⃣ 立即行动
**[docs/行动计划/ACTION-PLAN-DAY1.md](docs/行动计划/ACTION-PLAN-DAY1.md)**
- Day 1 立即可执行的详细步骤（上午4小时 + 下午4小时）
- 目标：证明AI能工作
- 执行时间：1天（8小时）
- 适合：开发人员

**[docs/行动计划/README.md](docs/行动计划/README.md)**
- 完整的6个阶段行动计划索引
- 适合：项目管理、进度跟踪

---

## 🎯 关键场景：地震级联灾害

我们聚焦的核心场景：
```
地震（主灾害）
  ↓
├─→ 洪水（水库大坝损坏）
├─→ 山体滑坡（地形+余震）
└─→ 化工厂泄露（设施损坏）
```

**复杂度特点**：
- 时序关系：T+0h（地震） → T+2h（洪水） → T+4h（泄露扩散）
- 风险叠加：洪水 + 泄露 = 有毒污染扩散（非线性效应）
- 决策窗口：极短（分钟级），需要AI快速预测和决策

---

## 🤖 AI智能体架构（简化版）

从15个智能体简化到**5个核心AI智能体**：

1. **态势感知智能体**（Situation Agent）
   - 输入：非结构化文本报告
   - AI任务：提取结构化JSON数据
   - 输出：灾害类型、震级、位置、附近设施等

2. **风险预测智能体**（Risk Predictor Agent）
   - 输入：态势数据 + 知识图谱 + 历史案例（RAG）
   - AI任务：预测次生灾害（类型、概率、时间窗口）
   - 输出：风险列表 + 推理依据

3. **方案生成智能体**（Plan Generator Agent）
   - 输入：态势 + 预测风险 + 可用资源
   - AI任务：生成救援行动方案
   - 输出：优先级排序 + 资源分配 + 时间安排 + 应急预案

4. **装备推荐智能体**（Equipment Recommender）
   - 输入：灾害链 + 方案
   - AI任务：推荐装备配置（用KG交叉验证防幻觉）
   - 输出：装备清单 + 数量 + 推荐理由

5. **决策解释智能体**（Explainer Agent）
   - 输入：所有AI决策结果
   - AI任务：生成可解释的决策报告
   - 输出：决策摘要 + 关键依据 + 风险点 + 应急预案

---

## 📊 项目现状

### 当前完成度：< 5%

| 维度 | 需求 | 已实现 | 状态 |
|------|------|--------|------|
| 智能体 | 15个 | 0个 | ❌ 全部未实现 |
| 功能点 | 58个 | ~3个 | ⚠️ 仅API框架 |
| 代码量 | ~30,000行 | ~500行 | ❌ 大部分占位代码 |

### 核心差距
1. **15个智能体**：一个都没有实现，只有LangGraph的4个占位节点
2. **AI能力**：LLM配置存在，但没有任何智能体使用它
3. **知识图谱**：Schema未扩展，不支持级联灾害（TRIGGERS/COMPOUNDS关系）
4. **测试**：几乎没有测试（覆盖率 < 5%）

### 预计工作量
- **完整实现58功能点**：6-12个月（2-3人团队）
- **实现5个核心AI智能体的原型**：3周（15天，1-2人）

---

## ⏱️ 3周实现路线

### Week 1：基础验证 + 风险预测
- **Day 1-2**：态势感知AI（证明AI能工作）
- **Day 3-5**：风险预测AI（KG + RAG集成）

### Week 2：方案生成 + 装备推荐
- **Day 6-8**：方案生成AI + 人工审批流程
- **Day 9-10**：装备推荐AI

### Week 3：解释性 + 集成部署
- **Day 11-12**：决策解释 + 审计日志
- **Day 13-15**：集成测试 + 部署

---

## 🔧 技术栈

### 核心框架
- **LangGraph**：AI编排（状态机 + Checkpoint）
- **FastAPI**：API服务
- **Neo4j**：知识图谱（级联灾害关系）
- **Qdrant**：向量存储（RAG）
- **Mem0**：记忆管理（多租户）

### LLM选项
1. **智谱API**（推荐，快速）：glm-4 / glm-4-plus
2. **本地vLLM**（需GPU）：Qwen2.5-7B / Qwen2.5-72B

### 数据库
- **PostgreSQL**：Checkpoint + 审计日志
- **Qdrant**：向量存储
- **Neo4j**：知识图谱

### 语音识别（ASR）

项目内置 ASR（无降级策略）：通过环境变量选择单一提供方。

可选实现：
- 阿里云百炼 fun-asr（在线）：设置 `ASR_PROVIDER=aliyun` 且提供 `DASHSCOPE_API_KEY`
- 本地 FunASR（WebSocket）：设置 `ASR_PROVIDER=local`，可选 `VOICE_ASR_WS_URL`

依赖：已在 `requirements.txt` 中包含 `dashscope`、`websockets`、`structlog`。

环境变量示例：
```bash
export ASR_PROVIDER=aliyun
export DASHSCOPE_API_KEY=your_dashscope_key
# 若使用本地：
# export ASR_PROVIDER=local
# export VOICE_ASR_WS_URL=wss://127.0.0.1:10097
```

调用示例：
```bash
curl -X POST "http://localhost:8008/asr/recognize" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/audio.pcm" -F "sample_rate=16000" -F "fmt=pcm"
```

---

## 🚀 Monday Morning（立即开始）

### Step 1：阅读核心文档（1小时）
```bash
# 1. 快速浏览需求
cat docs/需求/AI应急大脑与全空间智能车辆系统.md

# 2. 重点阅读分析报告的"执行摘要"部分
head -n 100 docs/分析报告/Linus式深度分析-级联灾害AI系统.md

# 3. 详细阅读Day 1行动计划
cat docs/行动计划/ACTION-PLAN-DAY1.md
```

### Step 2：环境检查（30分钟）

> ⚠️ **重要提示**：本项目**必须使用虚拟环境**运行！
>
> 原因：项目依赖CPU-only版本的PyTorch（用于语音VAD检测），如果使用系统Python可能加载错误的CUDA版本导致Bus error。

```bash
# 检查Python版本
python3 --version  # 需要 >= 3.10

# 创建并激活虚拟环境（如果还没有）
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 检查配置文件
cat config/dev.env

# 启动API服务（使用项目脚本，会自动激活venv）
./scripts/dev-run.sh

# 或手动启动（确保已激活venv）
# source .venv/bin/activate
# PYTHONPATH=src python -m uvicorn emergency_agents.api.main:app --reload --port 8008

# 测试健康检查（新终端）
curl http://localhost:8008/healthz
```

### Step 3：开始Day 1任务（8小时）
按照 [docs/行动计划/ACTION-PLAN-DAY1.md](docs/行动计划/ACTION-PLAN-DAY1.md) 执行

---

## 💡 关键原则

### Linus式开发哲学
> **"Talk is cheap. Show me the code."**  
> 停止讨论，开始编码

> **"First, make it work. Then, make it right. Then, make it fast."**  
> 先让它能跑，再让它跑对，最后让它跑快

> **"Don't waste time on perfect code."**  
> 别浪费时间追求完美，先让它工作起来

### 验收驱动开发
- 每个阶段都有明确的DoD（Definition of Done）
- 验收失败 = 阶段失败
- 不要自欺欺人地"差不多完成"

### 顺序执行，不跳过
- Day 1 失败 → 停下来解决问题
- Day 1 成功 → 继续 Day 2-3
- 不要跳跃式开发

---

## 📞 遇到问题？

### 常见问题

1. **Bus error或Segmentation fault（PyTorch导入失败）**
   - **症状**：运行`pytest`或`import torch`时Bus error
   - **根因**：使用了系统Python而非虚拟环境，加载了错误的PyTorch版本
   - **解决方案**：
     ```bash
     # 方式1：激活venv后运行
     source .venv/bin/activate
     pytest tests/

     # 方式2：直接使用venv的pytest
     .venv/bin/pytest tests/

     # 方式3：使用项目脚本（自动激活venv）
     ./scripts/dev-run.sh
     ```
   - **验证修复**：
     ```bash
     .venv/bin/python3 -c "import torch; print(f'✅ torch {torch.__version__} works')"
     ```
   - **详细诊断**：参见 `docs/新业务逻辑md/new_0.1/PyTorch-Bus-Error问题诊断.md`

2. **LLM连接失败**
   - 检查API Key是否正确
   - 检查网络连接
   - 尝试使用curl直接调用LLM API验证

3. **依赖安装失败**
   - 使用虚拟环境：`python3 -m venv .venv`
   - 激活环境：`source .venv/bin/activate`
   - 重新安装：`pip install -r requirements.txt`

4. **AI输出格式不稳定**
   - 降低temperature到0
   - 使用safe_json_parse函数（带重试）
   - 在prompt末尾强调"只返回JSON"

### 获取帮助
- 查看 [docs/分析报告/](docs/分析报告/) - 详细的技术分析
- 查看 [specs/](specs/) - 技术规范文档
- 查看 [docs/LangGraph最佳实践/](docs/LangGraph最佳实践/) - LangGraph使用指南

---

## 📁 项目结构

```
emergency-agents-langgraph/
├── docs/
│   ├── 需求/                    # 产品需求文档
│   ├── 分析报告/                # Linus式深度分析
│   ├── 行动计划/                # 阶段性行动计划（新）
│   ├── LangGraph最佳实践/       # 技术最佳实践
│   └── 开发指导/                # 开发指南
├── specs/                       # 技术规范（宪章、架构、错误恢复等）
├── src/emergency_agents/        # 核心代码
│   ├── api/                     # API层
│   ├── graph/                   # LangGraph编排
│   ├── agents/                  # 智能体实现（待创建）
│   ├── llm/                     # LLM客户端
│   ├── memory/                  # 记忆管理
│   └── rag/                     # RAG管线
├── tests/                       # 测试
├── config/                      # 配置文件
└── QUICK-START.md              # 本文件
```

---

## 🎯 下一步

1. ✅ 阅读本文档（5分钟）
2. 📖 阅读 [docs/行动计划/ACTION-PLAN-DAY1.md](docs/行动计划/ACTION-PLAN-DAY1.md)（20分钟）
3. 🚀 **开始执行 Day 1 任务**

**记住**：3周后，要看到一个能工作的demo，不是一堆更新的文档。

去写代码吧！ 💻

---

**文档版本**：v1.0  
**创建时间**：2025-10-19  
**维护者**：AI应急大脑团队  
**状态**：✅ 就绪

