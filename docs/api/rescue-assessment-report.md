# 救援评估报告接口说明

> 更新时间：2025-10-29  
> 关联模块：`src/emergency_agents/api/reports.py`

---

## 概述

当前接口用于生成“前突侦察指挥组”向省级指挥大厅汇报灾情时使用的正式建议稿，覆盖国家标准《GB/T 24438.1-2025》要求的全部核心指标，并按照现场模板自动填充七大章节。

- **路由**：`POST /reports/rescue-assessment`
- **认证**：沿用全局 FastAPI 配置（当前无额外鉴权）
- **超时时间**：取决于底层 LLM（默认 30 秒内返回）
- **幂等性**：纯读写请求，无状态、副作用

---

## 请求体 `RescueAssessmentInput`

```jsonc
{
  "basic": {
    "disaster_type": "地震灾害",          // 必填，枚举列表见下
    "occurrence_time": "2025-10-29T08:30:00Z", // 必填，ISO8601
    "report_time": "2025-10-29T09:00:00Z",     // 必填
    "location": "天一市川北县",            // 必填
    "command_unit": "省消防救援总队前突指挥组", // 必填
    "frontline_overview": "县城西南 15 公里山地，持续降雨导致道路塌方。",
    "communication_status": "应急通信车已抵达，容量受限。",
    "weather_trend": "未来 24 小时仍有中到大雨。"
  },
  "casualties": {
    "affected_population": 13000,
    "deaths": 12,
    "missing": 5,
    "injured": 78,
    "emergency_evacuation": 4200,
    "emergency_resettlement": 3800,
    "urgent_life_support": 2600,
    "requiring_support": 1800,
    "casualty_notes": "仍有 4 个自然村通信中断，暂无法核实。"
  },
  "disruptions": {
    "road_blocked_villages": 11,
    "power_outage_villages": 14,
    "water_outage_villages": 9,
    "telecom_outage_villages": 7,
    "infrastructure_notes": "国道 213K+87 处桥梁断裂。"
  },
  "infrastructure": {
    "collapsed_buildings": 630,
    "severely_damaged_buildings": 1280,
    "mildly_damaged_buildings": 3560,
    "transport_damage": "三座桥梁损毁，两处滑坡阻断县道。",
    "communication_damage": "应急通信车已抵达但容量受限。",
    "energy_damage": "110kV 变电站停运，待抢修。",
    "water_facility_damage": "两处提灌站停运。",
    "public_service_damage": "县人民医院局部停电，启用备用电源。",
    "direct_economic_loss": 26800.0,      // 单位：万元
    "other_critical_damage": "粮食仓库受损需复核。"
  },
  "agriculture": {
    "affected_area_ha": 1450.0,           // 公顷
    "ruined_area_ha": 820.0,
    "destroyed_area_ha": 310.0,
    "livestock_loss": "死亡牛羊 860 头只。",
    "other_agri_loss": "冷棚蔬菜 60 亩倒伏。"
  },
  "resources": {
    "deployed_forces": [
      {
        "name": "国家综合性消防救援队伍第一支队",
        "personnel": 186,
        "equipment": "生命探测仪 12 套、破拆装备 18 套",
        "tasks": "城区倒塌建筑破拆搜救。"
      },
      {
        "name": "省地震局快速测震组",
        "personnel": 24,
        "equipment": "余震监测设备 6 台",
        "tasks": "部署临时监测网。"
      }
    ],
    "air_support": "陆航旅直升机 2 架维持空投。",
    "waterborne_support": "待补充",
    "medical_support": "省卫健委派出 60 人医疗队，两辆移动医院车。",
    "engineering_support": "武警工程部队 120 人正在抢通 213 国道。",
    "public_security_support": "当地公安维持秩序，封控险段。",
    "logistics_support": "前突组搭建 3 个野战补给点。"
  },
  "support_needs": {
    "reinforcement_forces": "请求调派空降兵侦察分队进入孤立乡镇。",
    "material_shortages": "急需移动通信基站 3 套、应急桥梁 2 套。",
    "infrastructure_requests": "请求调配大功率发电车 4 台保障县医院。",
    "coordination_matters": "需省指挥部统筹空投路线，避免与民航冲突。"
  },
  "risk_outlook": {
    "aftershock_risk": "过去 12 小时记录余震 18 次，需警惕山体滑坡。",
    "meteorological_risk": "未来 24 小时仍有中到大雨。",
    "hydrological_risk": "堰塞湖水位持续抬升，威胁下游乡镇。",
    "hazardous_sources": "化工园区储罐受震需专人监测。",
    "safety_measures": "对滑坡隐患点布控雷达监测，提前组织转移。"
  },
  "operations": {
    "completed_actions": "成功搜救 63 人，转运重伤员 41 人。",
    "ongoing_actions": "正在抢通国道 213 和县道 X034。",
    "pending_actions": "待指挥部批准增派无人机编队。"
  }
}
```

### 字段校验

- **灾种枚举**：`洪涝灾害`、`干旱灾害`、`台风灾害`、`风雹灾害`、`低温冷冻灾害`、`雪灾`、`沙尘暴灾害`、`地震灾害`、`地质灾害`、`海洋灾害`、`森林草原火灾`、`生物灾害`
- 所有数字字段均使用非负/正整型或非负浮点限制；输入负值会被拦截（HTTP 422）
- 允许字段缺省或 `null`，模型会在成文时使用“待补充”提示

---

## 返回体 `RescueAssessmentResponse`

```json
{
  "report_text": "# “**”地震抗震救灾方案（建议稿）\n...\n前突侦察指挥组\n2025年10月29日",
  "key_points": [
    "死亡 12 人",
    "失踪 5 人",
    "紧急安置 3800 人",
    "倒塌房屋 630 间",
    "直接经济损失 26800.0 万元",
    "增援诉求：请求调派空降兵侦察分队进入孤立乡镇。",
    "物资缺口：急需移动通信基站 3 套、应急桥梁 2 套。",
    "地质风险：过去 12 小时记录余震 18 次，需警惕山体滑坡。"
  ]
}
```

- `report_text`：完整 Markdown 汇报稿，七大章节顺序固定；缺失数据统一输出“待补充”  
- `key_points`：服务端根据关键指标自动抽取的要点，可直接展示为标签或提醒

### 错误返回

- **入参错误**：HTTP 422，由 FastAPI 自动生成校验信息  
- **LLM 失败 / 空响应**：HTTP 502，`{"detail": "模型生成失败，请稍后重试"}` 或 `{"detail": "模型未返回有效内容"}`

---

## 业务约束

1. 前端必须提供真实数字与地名；任何估算或推测应在 `casualty_notes` 等字符串字段注明。  
2. 若某指标暂无法确认，请留空或传 `null`，后端会在汇报稿中自动标注“待补充”。  
3. 生成结果默认长度不超过 1500 tokens（约 1200 汉字+Markdown），如需更长报告，可在配置层增大 `max_tokens`。

---

## 测试指引

- 单元测试：`pytest tests/api/test_rescue_assessment.py`  
- 手工测试示例：

```bash
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d @payload.json
```

若需对接真实 LLM，请确保运行环境设置好 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 及 `LLM_MODEL` 等变量。测试阶段可通过 monkeypatch/mock 将 `get_openai_client` 替换成固定响应。

