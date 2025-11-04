# Postman 调用救援评估报告API指南

## ✅ 验证通过 - API正常工作

**测试时间**: 2025-11-03 00:32
**测试结果**: ✅ 200 OK
**响应时间**: < 10秒

---

## 📍 Postman 配置步骤

### 1. 基本信息

| 配置项 | 值 |
|--------|---|
| **请求方法** | `POST` |
| **请求URL** | `http://localhost:8000/reports/rescue-assessment` |
| **Content-Type** | `application/json` |

### 2. Headers 配置

在 Postman 的 **Headers** 标签页添加：

| KEY | VALUE |
|-----|-------|
| Content-Type | application/json |

### 3. Body 配置

选择 **Body** → **raw** → **JSON**

#### ✅ 最简请求（确保能成功）

```json
{
  "basic": {
    "disaster_type": "地震灾害",
    "occurrence_time": "2025-01-02T14:28:00",
    "report_time": "2025-11-03T00:30:00",
    "location": "四川省",
    "command_unit": "应急指挥部"
  },
  "casualties": {},
  "disruptions": {},
  "infrastructure": {},
  "agriculture": {},
  "resources": {
    "deployed_forces": []
  },
  "support_needs": {},
  "risk_outlook": {},
  "operations": {}
}
```

#### ✅ 完整请求（包含更多数据）

```json
{
  "basic": {
    "disaster_type": "地震灾害",
    "occurrence_time": "2025-01-02T14:28:00",
    "report_time": "2025-11-03T00:30:00",
    "location": "四川省阿坝州汶川县映秀镇",
    "command_unit": "前突侦察指挥组",
    "frontline_overview": "震中映秀镇建筑损毁严重，道路中断，通信受阻",
    "communication_status": "卫星通信已建立",
    "weather_trend": "未来24小时晴转多云"
  },
  "casualties": {
    "affected_population": 50000,
    "deaths": 100,
    "missing": 50,
    "injured": 300,
    "emergency_evacuation": 5000,
    "emergency_resettlement": 3000,
    "urgent_life_support": 8000,
    "requiring_support": 10000,
    "casualty_notes": "伤员主要为建筑倒塌所致"
  },
  "disruptions": {
    "road_blocked_villages": 15,
    "power_outage_villages": 20,
    "water_outage_villages": 18,
    "telecom_outage_villages": 12,
    "infrastructure_notes": "主要干道已抢通"
  },
  "infrastructure": {
    "collapsed_buildings": 500,
    "severely_damaged_buildings": 1200,
    "mildly_damaged_buildings": 3000,
    "transport_damage": "映秀至汶川主干道中断3处",
    "communication_damage": "3座通信基站损毁",
    "energy_damage": "2座变电站受损",
    "water_facility_damage": "主供水管网破裂",
    "public_service_damage": "县医院受损",
    "direct_economic_loss": 50000.0,
    "other_critical_damage": "学校、政府办公楼受损"
  },
  "agriculture": {
    "affected_area_ha": 5000.0,
    "ruined_area_ha": 2000.0,
    "destroyed_area_ha": 500.0,
    "livestock_loss": "猪500头、牛30头死亡",
    "other_agri_loss": "大棚损毁200个"
  },
  "resources": {
    "deployed_forces": [
      {
        "name": "消防救援队",
        "personnel": 200,
        "equipment": "生命探测仪、破拆工具",
        "tasks": "搜救被困人员"
      },
      {
        "name": "医疗队",
        "personnel": 50,
        "equipment": "医疗急救设备",
        "tasks": "现场医疗救治"
      }
    ],
    "air_support": "2架直升机",
    "medical_support": "野战医疗点已建立",
    "engineering_support": "工程机械5台",
    "logistics_support": "物资中转站已设立"
  },
  "support_needs": {
    "reinforcement_forces": "需增援医疗队50人",
    "material_shortages": "帐篷500顶、食品10吨",
    "infrastructure_requests": "需直升机2架",
    "coordination_matters": "需协调周边县市医院接收重伤员"
  },
  "risk_outlook": {
    "aftershock_risk": "余震风险高，持续监测",
    "meteorological_risk": "未来24小时无降雨",
    "hydrological_risk": "上游河道巡查中",
    "hazardous_sources": "无重大危化品风险",
    "safety_measures": "已设置安全警戒线"
  },
  "operations": {
    "completed_actions": "已搜救300人",
    "ongoing_actions": "仍有50人被困待救",
    "pending_actions": "需批准增援请求"
  }
}
```

---

## 📊 真实响应数据

### 响应结构

```json
{
  "report_text": "完整的Markdown报告文本（见下方）",
  "key_points": [],
  "data_sources": ["RAG规范文档库"],
  "confidence_score": 0.262,
  "referenced_specs": [
    "应急管理部预案库",
    "应急管理部预案库",
    "应急管理部预案库"
  ],
  "referenced_cases": [],
  "equipment_recommendations": [],
  "errors": []
}
```

### report_text 内容（Markdown格式）

```markdown
# 灾情汇报

## 一、当前灾情初步评估

- **灾种**：地震灾害
- **发生时间**：2025年01月02日14时28分
- **报告时间**：2025年11月03日00时30分
- **所在地区**：四川省
- **人员伤亡**：【待补充】
- **基础设施受损**：【待补充】
- **四断情况**：【待补充】
- **农业与经济损失**：【待补充】

## 二、组织指挥

- **现有组织体系**：应急指挥部
- **工作组设置**：前突侦察指挥组、救援行动组、物资保障组、医疗救护组
- **现场指挥机制**：由应急指挥部统一指挥，各工作组协同作战

## 三、救援力量部署与任务分工

- **已投入力量**：
  - 专业救援队伍：国家地震灾害紧急救援队（1-3支）
  - 消防救援编队（至少3个）
  - 消防救援人员（≥300人）
- **各自任务**：
  - 前突侦察指挥组：负责现场侦察、灾情评估、信息传递
  - 救援行动组：负责人员搜救、伤员救治
  - 物资保障组：负责物资调配、运输保障
  - 医疗救护组：负责伤员救治、医疗保障
- **装备配置**：
  - 无人机：用于现场侦察、灾情监测
  - 挖掘机：用于建筑拆除、道路清理
  - 医疗救护车：用于伤员转运
  - 【依据应急管理部预案库@崩塌隐患】

## 四、次生灾害预防与安全措施

- **余震风险**：持续监测余震活动，评估地震烈度及震源深度
- **降雨风险**：关注降雨情况，防止次生滑坡、泥石流等灾害
- **防范举措**：
  - 划定地震核心危险区（倒塌建筑周边50米），设置警戒隔离带
  - 疏散危险区内群众，禁止无关人员进入废墟作业区
  - 交通管控与...【依据应急管理部预案库@地震灾害应急处置预案】

## 五、通信与信息保障

- **通信恢复进展**：【待补充】
- **信息报送频率**：每小时一次

## 六、物资调配与运输保障

- **已到位物资**：【待补充】
- **仍需协调的物资**：
  - 食品：100吨
  - 水源：50吨
  - 医疗药品：50箱
- **时间节点**：预计24小时内到位

## 七、救援力量自身保障

- **救援人员轮换**：每6小时轮换一次
- **补给**：确保救援人员饮食、休息
- **医疗保障**：配备专业医疗队伍，随时待命

## 八、次生灾害风险与增援需求

- **次生灾害风险**：余震、降雨、滑坡等
- **增援需求**：
  - 专业救援队伍：2支
  - 医疗救护车：5辆
  - 物资：100吨
- **请指挥部决策**：是否增派救援力量及物资

## 九、总结

- **当前灾情**：地震灾害，灾情严重，需立即采取救援措施
- **救援进展**：已投入救援力量，正在开展救援行动
- **下一步工作**：持续救援，确保人员安全，防止次生灾害

## 前突侦察指挥组
## 2025年11月03日
```

---

## 🔧 Postman 常见问题排查

### 问题1: 连接超时

**可能原因**：
- 服务未启动
- 端口错误（应该是8000）

**解决方法**：
```bash
# 检查服务状态
curl http://localhost:8000/healthz

# 应返回: {"status":"ok"}
```

### 问题2: 422 Unprocessable Entity

**可能原因**：
- JSON格式错误
- 必填字段缺失
- disaster_type 枚举值错误

**解决方法**：
- 使用上面的"最简请求"测试
- 确保 disaster_type 是以下值之一：
  - "地震灾害"（推荐）
  - "洪涝灾害"
  - "台风灾害"
  - 等（见完整枚举列表）

### 问题3: 500 Internal Server Error

**可能原因**：
- LLM服务异常
- 依赖服务（Neo4j/Qdrant）连接问题

**解决方法**：
- 查看服务日志
- 检查配置文件

### 问题4: 响应为空或乱码

**可能原因**：
- Postman编码设置问题

**解决方法**：
- 在Postman Settings中设置：
  - Language detection: Auto
  - Response language: UTF-8

---

## 📋 完整枚举值列表

**disaster_type** 必须是以下值之一：

```
"洪涝灾害"
"干旱灾害"
"台风灾害"
"风雹灾害"
"低温冷冻灾害"
"雪灾"
"沙尘暴灾害"
"地震灾害"      ← 推荐测试使用
"地质灾害"
"海洋灾害"
"森林草原火灾"
"生物灾害"
```

---

## 🎯 快速验证步骤

### 步骤1: 测试服务连通性
```bash
curl http://localhost:8000/healthz
# 期望: {"status":"ok"}
```

### 步骤2: Postman配置
- Method: `POST`
- URL: `http://localhost:8000/reports/rescue-assessment`
- Headers: `Content-Type: application/json`
- Body: 复制"最简请求"的JSON

### 步骤3: 点击 Send

### 步骤4: 查看响应
- Status: `200 OK`
- Body: JSON格式响应，包含 `report_text` 字段

---

## 📸 Postman 截图配置说明

### Headers 标签
```
KEY                 | VALUE
--------------------|------------------
Content-Type        | application/json
```

### Body 标签
- 选择 `raw`
- 右侧下拉选择 `JSON`
- 粘贴请求JSON

### 超时设置
如果响应慢，可以调整超时：
- Settings → General → Request timeout: 60000 (毫秒)

---

## ✅ 测试成功标志

- **HTTP状态码**: 200
- **响应包含**:
  - `report_text`: 完整Markdown报告
  - `confidence_score`: 0-1之间的数字
  - `data_sources`: 数据来源数组
- **响应时间**: 通常 5-15 秒

---

**验证日期**: 2025-11-03
**API版本**: v1.0
**文档维护**: AI应急大脑项目组
