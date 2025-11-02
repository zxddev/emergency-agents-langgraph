# 救援评估报告生成API业务逻辑

## 概述

本文档记录了救援评估报告生成API (`POST /reports/rescue-assessment`) 的完整业务逻辑，包括KG+RAG增强、置信度评分等专业特性。

**最后更新**: 2025-08-14
**相关文件**:
- `src/emergency_agents/api/reports.py` - API端点实现
- `src/emergency_agents/llm/prompts/rescue_assessment.py` - Prompt构建
- `src/emergency_agents/api/main.py` - 路由注册和依赖注入

## 业务背景

救援评估报告是面向省级应急指挥大厅的正式汇报文档，需要满足：
1. 符合国家灾情统计体系
2. 数据权威、可追溯
3. 装备推荐有依据
4. 能够通过专家验收

原有实现仅使用LLM生成，缺乏外部数据支撑。增强版集成了知识图谱（KG）和RAG检索，提供专业的数据来源和置信度评估。

## 核心流程

### 1. 输入模型 (RescueAssessmentInput)

包含9大类完整的救援信息：

| 模块 | 主要字段 | 数据源 |
|------|---------|--------|
| **基础信息** | 灾种、时间、地点、指挥单位、现场概况 | 前端录入 |
| **人员伤亡** | 死亡、失踪、受伤、转移、安置人数 | 现场统计 |
| **生命线中断** | 道路、供电、供水、通信中断村数 | 基础设施评估 |
| **基础设施损毁** | 房屋、交通、通信、能源设施损毁 | 工程评估 |
| **农业损失** | 农作物受灾/成灾/绝收面积 | 农业部门 |
| **资源部署** | 救援力量、装备、后勤保障 | 指挥部调度 |
| **支援需求** | 增援力量、物资缺口、协调事项 | 现场需求 |
| **风险研判** | 余震、气象、水文、危化品风险 | 专家研判 |
| **行动进展** | 已完成、进行中、待批示事项 | 执行反馈 |

**类型定义** (强类型实现):
```python
class RescueAssessmentInput(BaseModel):
    basic: BasicInfo
    casualties: CasualtyStats
    disruptions: DisruptionStatus
    infrastructure: InfrastructureDamage
    agriculture: AgricultureDamage
    resources: ResourceDeployment
    support_needs: SupportNeeds
    risk_outlook: RiskOutlook
    operations: OperationsProgress
```

### 2. 外部数据增强

#### 2.1 KG装备推荐

**调用时机**: 报告生成开始
**接口**: `_kg_service.recommend_equipment(hazard, environment, top_k=5)`
**参数构造**:
```python
hazard = payload.basic.disaster_type.value  # 如"地震灾害"
environment = payload.basic.frontline_overview  # 现场概况（可选）
```

**返回数据**:
```python
List[Dict[str, Any]] = [
    {"name": "生命探测仪", "score": 0.95},
    {"name": "破拆工具组", "score": 0.88},
    ...
]
```

**日志记录**:
- `kg_recommend_equipment_start`: 记录查询条件
- `kg_recommend_equipment_success`: 记录结果数量和耗时
- `kg_recommend_equipment_failed`: 记录错误（不中断流程）

**错误处理**:
- 如果KG服务未初始化，抛出 `RuntimeError`
- 如果查询失败，记录错误到 `errors` 列表，不影响后续流程

#### 2.2 RAG规范检索

**调用时机**: KG装备推荐后
**接口**: `_rag_pipeline.query(question, domain="规范", top_k=3)`
**参数构造**:
```python
spec_query = f"{disaster_type}应急预案规范"  # 如"地震灾害应急预案规范"
```

**返回数据** (RagChunk):
```python
List[RagChunk] = [
    RagChunk(text="...", source="国家地震应急预案", loc="第3章"),
    ...
]
```

**数据提取**:
- `spec_titles`: 提取所有规范文档的source字段
- `reference_materials`: 构造Markdown格式的引用片段

**日志记录**:
- `rag_query_specs_start`: 记录查询字符串
- `rag_query_specs_success`: 记录检索结果数量和耗时
- `rag_query_specs_failed`: 记录错误

#### 2.3 KG案例检索

**调用时机**: RAG规范检索后
**接口**: `_kg_service.search_cases(keywords, top_k=3)`
**参数构造**:
```python
case_keywords = f"{disaster_type} {location}"  # 如"地震灾害 四川"
```

**返回数据**:
```python
List[Dict[str, Any]] = [
    {"title": "汶川地震救援案例", "summary": "...", ...},
    ...
]
```

**数据提取**:
- `case_titles`: 提取所有案例的title字段
- `reference_materials`: 构造案例摘要

**日志记录**:
- `kg_search_cases_start`: 记录查询关键词
- `kg_search_cases_success`: 记录案例数量和耗时
- `kg_search_cases_failed`: 记录错误

### 3. Prompt增强

**函数**: `build_rescue_assessment_prompt(payload, reference_materials)`

**增强策略**:
1. 在原有数据基础上，新增"权威参考资料"章节
2. 包含：
   - 推荐装备配置（基于知识图谱）
   - 应急预案规范（RAG检索）
   - 历史救援案例（知识图谱）
3. 如果没有检索到任何外部资料，添加提示信息

**Prompt结构**:
```
【系统要求】（指令、规范、约束）
   ↓
【必须生成的章节】（7个标准章节）
   ↓
【数据载荷】（JSON格式的输入数据）
   ↓
【权威参考资料】（KG + RAG检索结果）← 新增
   ↓
【写作要点】（格式要求、注意事项）
```

**关键要求**:
- 引用外部资料时，需标注来源
- 装备推荐需注明"依据知识图谱推荐"
- 规范引用需注明文档标题和章节

### 4. LLM生成

**模型配置**:
```python
model = cfg.llm_model  # 默认 glm-4-flash
temperature = 0.2  # 低温度保证稳定性
max_tokens = 2000  # 增加到2000（原1500）
```

**System Prompt**:
```
你是一名国家级应急救援指挥专家，擅长将复杂灾情转化为结构化的正式汇报。
务必严格遵循用户提供的数据和权威参考资料，严禁虚构。
在汇报中引用外部资料时，需标注来源。
```

**日志记录**:
- `rescue_assessment_llm_success`: 记录生成耗时和输出长度
- `rescue_assessment_llm_failed`: 记录失败原因并抛出HTTP 502错误

### 5. 置信度评分

**算法**: 多维度加权评分

#### 5.1 输入完整性（40%权重）

**函数**: `_calculate_input_completeness(payload)`

**计算逻辑**:
```python
total_fields = 统计所有字段数量（递归遍历嵌套dict/list）
filled_fields = 统计非空字段数量
completeness = filled_fields / total_fields
```

#### 5.2 外部数据支撑度（40%权重）

**计算公式**:
```python
external_support = (
    min(spec_count / expected_specs, 1.0) * 0.4 +
    min(case_count / expected_cases, 1.0) * 0.3 +
    min(equipment_count / expected_equipment, 1.0) * 0.3
)
```

**期望值**:
- `expected_specs = 3` (期望检索到3条规范)
- `expected_cases = 2` (期望检索到2个案例)
- `expected_equipment = 5` (期望推荐5件装备)

#### 5.3 数据源多样性（20%权重）

**计算逻辑**:
```python
used_sources = [
    "知识图谱装备库" if equipment_count > 0 else None,
    "RAG规范文档库" if spec_count > 0 else None,
    "知识图谱案例库" if case_count > 0 else None,
]
source_diversity = len([s for s in used_sources if s]) / 3.0
```

#### 5.4 综合评分

**公式**:
```python
confidence_score = (
    input_completeness * 0.4 +
    external_support * 0.4 +
    source_diversity * 0.2
)
```

**返回**: 保留3位小数的浮点数（0-1）

**日志记录**:
- `confidence_score_calculated`: 记录各维度得分和最终分数

### 6. 输出模型 (RescueAssessmentResponse)

**扩展字段**（强类型）:

| 字段 | 类型 | 说明 | 来源 |
|------|------|------|------|
| `report_text` | str | 完整报告（Markdown） | LLM生成 |
| `key_points` | List[str] | 要点摘要（≤8条） | 提取函数 |
| `data_sources` | List[str] | 数据来源列表 | 收集汇总 |
| `confidence_score` | float | 置信度（0-1） | 评分算法 |
| `referenced_specs` | List[str] | 引用的规范标题 | RAG检索 |
| `referenced_cases` | List[str] | 引用的案例标题 | KG检索 |
| `equipment_recommendations` | List[EquipmentRecommendation] | 装备推荐清单 | KG推荐 |
| `errors` | List[str] | 错误或警告信息 | 异常收集 |

**EquipmentRecommendation 子模型**:
```python
class EquipmentRecommendation(BaseModel):
    name: str  # 装备名称
    score: float  # 推荐得分（0-1）
    source: str  # 推荐来源（默认"知识图谱"）
```

## 技术要点

### 依赖注入

**模块级变量**:
```python
# src/emergency_agents/api/reports.py
_kg_service: Any | None = None
_rag_pipeline: Any | None = None
```

**注入时机**: `main.py` 的 `startup_event`
```python
reports_api._kg_service = _kg
reports_api._rag_pipeline = _rag
```

**参考模式**: 参考 `sitrep_api` 的依赖注入实现

### 错误处理策略

**原则**: 不降级，透明展示

**实现**:
1. 外部调用失败时，记录错误到 `errors` 列表
2. 不因部分失败而中断整个流程
3. 在response中明确告知哪些数据源不可用
4. LLM调用失败直接抛出HTTP 502错误

**示例**:
```python
try:
    kg_equipment = _kg_service.recommend_equipment(...)
except Exception as e:
    logger.error("kg_recommend_equipment_failed", error=str(e))
    errors.append(f"知识图谱装备推荐失败: {str(e)}")
```

### 日志记录规范

**结构化日志** (使用 structlog):
```python
logger.info(
    "rescue_assessment_start",
    disaster_type=disaster_type,
    location=location,
)
```

**关键日志点**:
1. API入口：记录灾害类型、地点
2. 每次外部调用前：记录查询条件
3. 每次外部调用后：记录结果数量、耗时（ms）
4. Prompt构建：记录prompt长度、数据源数量
5. LLM生成：记录耗时、输出长度
6. 置信度计算：记录各维度得分
7. API返回：记录总耗时、置信度、错误数量

**性能监控**:
- 每个外部调用记录耗时（ms）
- 总耗时从请求开始到返回
- 便于性能分析和优化

## 路由注册

**文件**: `src/emergency_agents/api/main.py`

**导入**:
```python
from emergency_agents.api import reports as reports_api
```

**注册**:
```python
app.include_router(reports_api.router)
```

**依赖注入** (startup_event):
```python
reports_api._kg_service = _kg
reports_api._rag_pipeline = _rag
logger.info("api_reports_dependencies_injected")
```

## 使用示例

### 请求

```bash
POST /reports/rescue-assessment
Content-Type: application/json

{
  "basic": {
    "disaster_type": "地震灾害",
    "occurrence_time": "2025-08-14T10:30:00",
    "report_time": "2025-08-14T12:00:00",
    "location": "四川省阿坝州",
    "command_unit": "应急管理部前突指挥组",
    "frontline_overview": "山区地形，通信中断",
    "communication_status": "卫星电话可用",
    "weather_trend": "未来24小时有降雨"
  },
  "casualties": {
    "affected_population": 50000,
    "deaths": 15,
    "missing": 8,
    "injured": 120
  },
  ...
}
```

### 响应

```json
{
  "report_text": "# 前突侦察指挥组灾情汇报\n\n## 一、当前灾情初步评估\n...",
  "key_points": [
    "死亡 15 人",
    "失踪 8 人",
    "直接经济损失 5000 万元"
  ],
  "data_sources": [
    "知识图谱装备库",
    "RAG规范文档库",
    "知识图谱案例库"
  ],
  "confidence_score": 0.856,
  "referenced_specs": [
    "国家地震应急预案",
    "地震灾害救援规范"
  ],
  "referenced_cases": [
    "汶川地震救援案例"
  ],
  "equipment_recommendations": [
    {
      "name": "生命探测仪",
      "score": 0.95,
      "source": "知识图谱"
    }
  ],
  "errors": []
}
```

## 性能指标

**目标延迟** (端到端):
- P50: < 3000ms
- P95: < 5000ms
- P99: < 8000ms

**各环节耗时**:
- KG装备推荐: ~100-300ms
- RAG规范检索: ~200-500ms
- KG案例检索: ~100-300ms
- LLM生成: ~1000-3000ms
- 置信度计算: <10ms

**优化方向**:
- 考虑并行调用KG和RAG（当前串行）
- 缓存热门灾害类型的检索结果
- 优化LLM prompt长度

## 测试用例

### 单元测试

**测试文件**: `tests/test_rescue_assessment.py` (待补充)

**核心测试点**:
1. 输入完整性计算准确性
2. 置信度评分算法正确性
3. 外部调用失败时的错误处理
4. Prompt构建逻辑完整性
5. Response模型字段验证

### 集成测试

**前置条件**:
- KG服务可用（Neo4j）
- RAG服务可用（Qdrant）
- LLM服务可用（GLM-4）

**测试场景**:
1. 所有外部服务正常：验证完整流程
2. KG服务异常：验证降级处理
3. RAG服务异常：验证降级处理
4. 输入数据不完整：验证置信度降低
5. 空输入：验证必填字段校验

## 已知问题和后续优化

### 当前限制

1. **串行调用**: KG和RAG调用是串行的，可以并行优化
2. **无缓存**: 相同灾害类型的检索没有缓存
3. **固定top_k**: 检索数量固定，未根据灾害严重程度动态调整
4. **无RiskPredictor集成**: 风险预测器需要incident_id，当前未集成

### 后续增强方向

1. **并行调用优化**:
   ```python
   import asyncio
   equipment, specs, cases = await asyncio.gather(
       kg_recommend_async(...),
       rag_query_async(...),
       kg_search_cases_async(...),
   )
   ```

2. **智能缓存**:
   - 缓存常见灾害类型的规范和案例
   - TTL: 7天
   - 使用Redis或本地内存缓存

3. **动态top_k**:
   - 根据灾害severity动态调整检索数量
   - 严重灾害：top_k增加到10
   - 一般灾害：top_k保持5

4. **RiskPredictor集成**:
   - 在输入模型中添加可选的`incident_id`
   - 如果提供，调用RiskPredictor获取风险评估
   - 将风险评估注入到prompt中

## 参考资料

**代码参考**:
- `src/emergency_agents/api/sitrep.py` - 依赖注入模式
- `src/emergency_agents/graph/kg_service.py` - KG接口定义
- `src/emergency_agents/rag/pipe.py` - RAG接口定义

**文档参考**:
- 国家灾情统计体系文档
- 应急救援指挥规范
- LangGraph官方文档

**相关Issues**:
- 无

**变更历史**:
- 2025-08-14: 初版，实现KG+RAG增强和置信度评分
