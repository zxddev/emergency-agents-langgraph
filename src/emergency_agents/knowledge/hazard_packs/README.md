# 多灾种知识包 (Hazard Knowledge Packs)

## 概述

多灾种知识包是应急救援AI系统的知识底座，为不同类型的灾害提供标准化的任务模板、风险规则和历史案例参考。

## 目录结构

```
hazard_packs/
├── schemas/
│   └── hazard_pack_schema.json    # JSON Schema定义
├── bridge_collapse.json            # 桥梁坍塌知识包 v1.0.0
├── chemical_leak.json              # 化工泄漏知识包 v1.0.0
├── landslide.json                  # 山体滑坡知识包 v1.0.0
├── version_manifest.json           # 版本管理清单
└── README.md                       # 本文档
```

## 已支持的灾种

| 灾种类型 | 文件名 | 当前版本 | 任务阶段数 | 任务总数 | 状态 |
|---------|--------|---------|-----------|---------|------|
| 桥梁坍塌 | bridge_collapse.json | 1.0.0 | 4 | 8 | ✅ Stable |
| 化工泄漏 | chemical_leak.json | 1.0.0 | 4 | 8 | ✅ Stable |
| 山体滑坡 | landslide.json | 1.0.0 | 4 | 8 | ✅ Stable |

## 知识包结构

每个知识包包含以下核心字段:

### 1. 元数据
- `hazard_type`: 灾种类型标识符
- `version`: 版本号 (semver格式)
- `severity_levels`: 严重程度分级阈值

### 2. 任务模板 (`mission_templates`)
按4个执行阶段组织:
- **reconnaissance** (侦察阶段): 无人机/地面侦察、结构评估、生命探测
- **rescue** (救援阶段): 被困人员救援、堵漏止泄、挖掘作业
- **alert** (警戒阶段): 警戒线设置、疏散撤离、持续监测
- **logistics** (后勤阶段): 医疗支持、物资供应、临时安置

每个任务包含:
- `task_id`: 唯一标识 (格式: `phase_type_序号`)
- `task_type`: 任务类型
- `required_capabilities`: 必需能力标签 (用于资源匹配)
- `recommended_equipment`: 推荐装备清单
- `duration_minutes`: 预计时长
- `dependencies`: 前置任务依赖 (DAG)
- `parallel_allowed`: 是否允许并行执行
- `description`: 任务描述
- `safety_notes`: 安全注意事项

### 3. 风险规则 (`risk_rules`)
- `rule_id`: 规则标识
- `condition`: 触发条件 (自然语言)
- `action`: 应对措施
- `priority`: 优先级 (critical/high/medium/low)

### 4. 参考案例 (`reference_cases`)
- `case_id`: 案例标识
- `title`: 案例标题
- `summary`: 案例摘要
- `date`: 发生日期
- `location`: 发生地点
- `lessons_learned`: 经验教训
- `rag_doc_id`: RAG系统文档ID (用于检索)

## 使用方法

### Python加载示例

```python
from emergency_agents.knowledge.hazard_pack_loader import HazardPackLoader

# 初始化加载器
loader = HazardPackLoader()

# 加载指定灾种的最新版本
pack = loader.load("bridge_collapse")

# 加载指定版本
pack = loader.load("bridge_collapse", version="1.0.0")

# 获取任务模板
recon_tasks = pack.get_tasks_by_phase("reconnaissance")

# 获取风险规则
critical_risks = pack.get_risks_by_priority("critical")

# 获取参考案例
cases = pack.get_reference_cases()
```

### 任务依赖关系解析

```python
# 构建任务DAG
task_graph = pack.build_task_dag()

# 获取拓扑排序 (执行顺序)
execution_order = task_graph.topological_sort()

# 获取某任务的所有前置任务
prerequisites = task_graph.get_prerequisites("rescue_trapped_01")
```

## 版本管理

### 版本号规范 (Semver)
- **Major (X.0.0)**: 破坏性变更 (任务模板结构调整、字段删除)
- **Minor (x.Y.0)**: 新增功能 (新任务模板、新风险规则)
- **Patch (x.y.Z)**: 修复错误 (文本修正、参数调整)

### 版本查询

```python
from emergency_agents.knowledge.version_manager import VersionManager

vm = VersionManager()

# 获取最新稳定版本
latest = vm.get_latest_version("bridge_collapse")

# 获取所有可用版本
versions = vm.list_versions("bridge_collapse")

# 检查版本兼容性
is_compatible = vm.check_compatibility("1.0.0", "1.1.0")
```

### 版本迁移

当知识包版本升级时:
1. 旧版本保留6个月 (根据`version_policy`)
2. 系统自动检测兼容性
3. 不兼容时提示更新

## 扩展新灾种

### 步骤1: 创建知识包文件

```bash
cp bridge_collapse.json new_hazard.json
```

### 步骤2: 修改内容

1. 更新 `hazard_type`
2. 定义 `severity_levels`
3. 设计 `mission_templates` (4个阶段)
4. 编写 `risk_rules`
5. 添加 `reference_cases`

### 步骤3: 验证Schema

```python
from emergency_agents.knowledge.validator import validate_pack

# 验证JSON格式
validate_pack("new_hazard.json")
```

### 步骤4: 更新version_manifest.json

在`packs`中添加新条目:

```json
"new_hazard": {
  "current_version": "1.0.0",
  "latest_stable": "1.0.0",
  "versions": [...]
}
```

### 步骤5: 注册到枚举

编辑 `hazard_pack_schema.json`:

```json
"hazard_type": {
  "enum": [
    "bridge_collapse",
    "chemical_leak",
    "landslide",
    "new_hazard"  // 添加
  ]
}
```

## 能力标签规范

常用能力标签(用于资源匹配):

### 无人机/机器人
- `uav_operation`: 无人机操作
- `thermal_imaging`: 热成像
- `video_transmission`: 视频传输
- `water_rescue`: 水域救援
- `robotic_dog_operation`: 机器狗操作

### 救援队伍
- `heavy_rescue`: 重型救援
- `medical_first_aid`: 医疗急救
- `structural_engineering`: 结构工程
- `hazmat_specialist`: 危化品专家
- `search_rescue`: 搜救
- `cutting_tools`: 切割破拆

### 监测与评估
- `hazard_monitoring`: 危险监测
- `safety_evaluation`: 安全评估
- `chemical_analysis`: 化学分析
- `geological_engineering`: 地质工程

完整列表见: [capability_labels.json](../capability_labels.json)

## 性能优化

### 缓存策略
- 启动时预加载3个核心灾种到内存
- Redis缓存24小时TTL
- 版本变更时自动失效

### 加载性能
- 单个知识包加载: < 100ms (缓存命中)
- 冷启动加载: < 500ms (从磁盘读取)

## 审计与合规

所有知识包修改需记录:
- 修改人/修改时间
- 变更内容(changelog)
- 审批流程(重大变更需专家评审)

审计日志路径: `audit/knowledge_pack_changes/`

## 参考文档

- [任务模板DSL指南](../../../docs/temp/任务模板DSL指南.md)
- [多灾种知识包说明](../../../docs/temp/多灾种知识包说明.md)
- [资源匹配算法](../../../docs/temp/资源匹配算法.md)

## 维护者

- **创建日期**: 2025-10-30
- **维护团队**: 应急AI系统开发组
- **联系方式**: emergency-ai@cykj.com
