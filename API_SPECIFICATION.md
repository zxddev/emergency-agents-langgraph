# 救援评估报告生成API接口规范

## 基本信息

| 项目 | 内容 |
|------|------|
| **接口路径** | `POST /reports/rescue-assessment` |
| **服务地址** | `http://localhost:8000` |
| **完整URL** | `http://localhost:8000/reports/rescue-assessment` |
| **Content-Type** | `application/json` |
| **认证方式** | 无（内网服务） |

---

## 请求参数

### 数据模型层级结构

```
RescueAssessmentInput
├─ basic: BasicInfo                    # 基本信息（必填）
├─ casualties: CasualtyStats            # 人员伤亡统计（必填）
├─ disruptions: DisruptionStatus        # 四断情况（必填）
├─ infrastructure: InfrastructureDamage # 基础设施损毁（必填）
├─ agriculture: AgricultureDamage       # 农业损失（必填）
├─ resources: ResourceDeployment        # 资源部署（必填）
├─ support_needs: SupportNeeds          # 增援需求（必填）
├─ risk_outlook: RiskOutlook            # 风险展望（必填）
└─ operations: OperationsProgress       # 行动进展（必填）
```

### 1. basic - 基本信息 (BasicInfo)

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| disaster_type | DisasterType | ✅ | 灾种分类（枚举值） | "地震灾害" |
| occurrence_time | datetime | ✅ | 灾害发生时间 | "2025-01-02T14:28:00" |
| report_time | datetime | ✅ | 报告生成时间 | "2025-11-03T00:20:00" |
| location | string | ✅ | 灾害影响行政区 | "四川省阿坝州汶川县映秀镇" |
| command_unit | string | ✅ | 指挥单位名称 | "前突侦察指挥组" |
| frontline_overview | string | ❌ | 现场态势概述 | "建筑损毁严重，道路中断" |
| communication_status | string | ❌ | 通信状况 | "卫星通信已建立" |
| weather_trend | string | ❌ | 天气趋势 | "未来24小时晴转多云" |

**灾种枚举值（DisasterType）**：
- `洪涝灾害`, `干旱灾害`, `台风灾害`, `风雹灾害`
- `低温冷冻灾害`, `雪灾`, `沙尘暴灾害`
- `地震灾害`, `地质灾害`, `海洋灾害`
- `森林草原火灾`, `生物灾害`

### 2. casualties - 人员伤亡统计 (CasualtyStats)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| affected_population | int | ❌ | 受灾人口数量 |
| deaths | int | ❌ | 死亡人数 |
| missing | int | ❌ | 失踪人数 |
| injured | int | ❌ | 受伤人数 |
| emergency_evacuation | int | ❌ | 紧急避险转移人口 |
| emergency_resettlement | int | ❌ | 紧急安置人口 |
| urgent_life_support | int | ❌ | 需紧急生活救助人口 |
| requiring_support | int | ❌ | 需持续救助人口 |
| casualty_notes | string | ❌ | 伤员情况说明 |

### 3. disruptions - 四断情况 (DisruptionStatus)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| road_blocked_villages | int | ❌ | 道路中断的行政村数 |
| power_outage_villages | int | ❌ | 供电中断的行政村数 |
| water_outage_villages | int | ❌ | 供水中断的行政村数 |
| telecom_outage_villages | int | ❌ | 通信中断的行政村数 |
| infrastructure_notes | string | ❌ | 其他基础设施受损说明 |

### 4. infrastructure - 基础设施损毁 (InfrastructureDamage)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| collapsed_buildings | int | ❌ | 倒塌房屋间数 |
| severely_damaged_buildings | int | ❌ | 严重损坏房屋间数 |
| mildly_damaged_buildings | int | ❌ | 一般损坏房屋间数 |
| transport_damage | string | ❌ | 交通设施受损情况 |
| communication_damage | string | ❌ | 通信设施受损情况 |
| energy_damage | string | ❌ | 能源设施受损情况 |
| water_facility_damage | string | ❌ | 水利设施受损情况 |
| public_service_damage | string | ❌ | 公共服务设施情况 |
| direct_economic_loss | float | ❌ | 直接经济损失（万元） |
| other_critical_damage | string | ❌ | 其它重点损毁信息 |

### 5. agriculture - 农业损失 (AgricultureDamage)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| affected_area_ha | float | ❌ | 农作物受灾面积（公顷） |
| ruined_area_ha | float | ❌ | 农作物成灾面积（公顷） |
| destroyed_area_ha | float | ❌ | 农作物绝收面积（公顷） |
| livestock_loss | string | ❌ | 畜牧、水产损失情况 |
| other_agri_loss | string | ❌ | 其他涉农损失说明 |

### 6. resources - 资源部署 (ResourceDeployment)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| deployed_forces | ForceUnit[] | ❌ | 已投入救援力量清单 |
| air_support | string | ❌ | 航空或无人机支援情况 |
| waterborne_support | string | ❌ | 水面救援力量 |
| medical_support | string | ❌ | 医疗救护力量部署 |
| engineering_support | string | ❌ | 工程抢险力量部署 |
| public_security_support | string | ❌ | 公安武警维稳力量 |
| logistics_support | string | ❌ | 后勤物资补给情况 |

**ForceUnit 子对象**：
```json
{
  "name": "消防救援队",      // 必填
  "personnel": 200,          // 选填
  "equipment": "生命探测仪",  // 选填
  "tasks": "搜救被困人员"     // 选填
}
```

### 7. support_needs - 增援需求 (SupportNeeds)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| reinforcement_forces | string | ❌ | 需追加的救援力量 |
| material_shortages | string | ❌ | 亟需调拨的物资 |
| infrastructure_requests | string | ❌ | 需协调的基础设施保障 |
| coordination_matters | string | ❌ | 需指挥部决策的重点事项 |

### 8. risk_outlook - 风险展望 (RiskOutlook)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| aftershock_risk | string | ❌ | 余震、滑坡等地质风险 |
| meteorological_risk | string | ❌ | 降雨、降温等气象风险 |
| hydrological_risk | string | ❌ | 堰塞湖、洪水等水文风险 |
| hazardous_sources | string | ❌ | 危化品等重大风险源 |
| safety_measures | string | ❌ | 拟采取的防范措施 |

### 9. operations - 行动进展 (OperationsProgress)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| completed_actions | string | ❌ | 已完成的救援行动 |
| ongoing_actions | string | ❌ | 正在推进的重点任务 |
| pending_actions | string | ❌ | 待批示事项或下一步计划 |

---

## 响应参数

### RescueAssessmentResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| report_text | string | 完整的灾情汇报文本（Markdown格式） |
| key_points | string[] | 关键要点摘要（便于前端展示） |
| data_sources | string[] | 数据来源列表 |
| confidence_score | float | 置信度评分（0-1） |
| referenced_specs | string[] | 引用的规范文档标题 |
| referenced_cases | string[] | 引用的历史案例标题 |
| equipment_recommendations | EquipmentRecommendation[] | 装备推荐清单 |
| errors | string[] | 执行错误或警告信息 |

**EquipmentRecommendation 子对象**：
```json
{
  "name": "生命探测仪",
  "score": 0.95,
  "source": "知识图谱"
}
```

---

## 请求示例

### cURL

```bash
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "basic": {
      "disaster_type": "地震灾害",
      "occurrence_time": "2025-01-02T14:28:00",
      "report_time": "2025-11-03T00:20:00",
      "location": "四川省阿坝州汶川县映秀镇",
      "command_unit": "前突侦察指挥组",
      "frontline_overview": "震中建筑损毁严重，道路中断，通信受阻"
    },
    "casualties": {
      "affected_population": 50000,
      "deaths": 100,
      "missing": 50,
      "injured": 300
    },
    "disruptions": {
      "road_blocked_villages": 15,
      "power_outage_villages": 20
    },
    "infrastructure": {
      "collapsed_buildings": 500,
      "severely_damaged_buildings": 1200
    },
    "agriculture": {},
    "resources": {
      "deployed_forces": [
        {
          "name": "消防救援队",
          "personnel": 200,
          "tasks": "搜救被困人员"
        }
      ]
    },
    "support_needs": {},
    "risk_outlook": {},
    "operations": {}
  }'
```

### Python requests

```python
import requests
from datetime import datetime

payload = {
    "basic": {
        "disaster_type": "地震灾害",
        "occurrence_time": "2025-01-02T14:28:00",
        "report_time": datetime.now().isoformat(),
        "location": "四川省阿坝州汶川县映秀镇",
        "command_unit": "前突侦察指挥组"
    },
    "casualties": {"deaths": 100, "missing": 50},
    "disruptions": {},
    "infrastructure": {},
    "agriculture": {},
    "resources": {"deployed_forces": []},
    "support_needs": {},
    "risk_outlook": {},
    "operations": {}
}

response = requests.post(
    "http://localhost:8000/reports/rescue-assessment",
    json=payload,
    timeout=60
)

result = response.json()
print(result['report_text'])
```

### JavaScript (Fetch API)

```javascript
const payload = {
  basic: {
    disaster_type: "地震灾害",
    occurrence_time: "2025-01-02T14:28:00",
    report_time: new Date().toISOString(),
    location: "四川省阿坝州汶川县映秀镇",
    command_unit: "前突侦察指挥组"
  },
  casualties: { deaths: 100, missing: 50 },
  disruptions: {},
  infrastructure: {},
  agriculture: {},
  resources: { deployed_forces: [] },
  support_needs: {},
  risk_outlook: {},
  operations: {}
};

fetch('http://localhost:8000/reports/rescue-assessment', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
  .then(res => res.json())
  .then(data => console.log(data.report_text));
```

---

## 响应示例

```json
{
  "report_text": "# 灾情汇报\n\n## 一、当前灾情初步评估\n...",
  "key_points": [
    "死亡 100 人",
    "失踪 50 人",
    "直接经济损失 50000.0 万元"
  ],
  "data_sources": [
    "RAG规范文档库",
    "知识图谱装备库"
  ],
  "confidence_score": 0.462,
  "referenced_specs": [
    "应急管理部预案库",
    "国家地震应急预案"
  ],
  "referenced_cases": [],
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

---

## 状态码说明

| 状态码 | 说明 | 处理建议 |
|--------|------|---------|
| 200 | 成功 | 正常处理响应 |
| 422 | 参数校验失败 | 检查请求参数格式 |
| 502 | LLM生成失败 | 稍后重试 |
| 500 | 服务器内部错误 | 联系技术支持 |

---

## 注意事项

### 必填字段
所有顶层对象（basic, casualties等）都必须提供，但对象内部的字段可选填。最少有效请求：

```json
{
  "basic": {
    "disaster_type": "地震灾害",
    "occurrence_time": "2025-01-02T14:28:00",
    "report_time": "2025-11-03T00:20:00",
    "location": "四川省",
    "command_unit": "应急指挥部"
  },
  "casualties": {},
  "disruptions": {},
  "infrastructure": {},
  "agriculture": {},
  "resources": {"deployed_forces": []},
  "support_needs": {},
  "risk_outlook": {},
  "operations": {}
}
```

### 数据类型约束
- 所有 int 字段必须 ≥ 0（NonNegativeInt）
- 所有 float 字段必须 ≥ 0.0（NonNegativeFloat）
- datetime 格式：ISO 8601（如 `2025-01-02T14:28:00`）

### 性能指标
- 平均响应时间：< 10秒
- 超时限制：60秒
- 最大报告长度：约2000字符

### 置信度评分说明
- **0.0-0.4**: 数据不完整，仅供参考
- **0.4-0.7**: 数据基本完整，可作为决策参考
- **0.7-1.0**: 数据完整且有权威资料支持，高置信度

---

## 完整测试脚本

完整的测试脚本见：`test_rescue_assessment_api.py`

运行测试：
```bash
python3 test_rescue_assessment_api.py
```

---

**文档版本**: v1.0
**最后更新**: 2025-11-03
**维护者**: AI应急大脑项目组
