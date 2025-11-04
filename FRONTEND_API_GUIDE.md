# 救援评估报告生成API - 前端调用文档

## 📌 接口概述

**功能说明**: 根据录入的灾情数据，自动生成专业的救援评估报告（Markdown格式）

**适用场景**:
- 前突侦察指挥组现场灾情汇报
- 应急指挥大厅态势评估
- 救援决策支持系统

---

## 🔗 接口地址

```
POST /reports/rescue-assessment
```

**完整URL**: `http://localhost:8000/reports/rescue-assessment`

**请求方式**: POST

**Content-Type**: `application/json`

---

## 📥 请求参数（入参）

### 整体结构

请求体由 **9个顶层对象** 组成，只有 `basic` 对象中的5个字段为必填，其他均为可选。

```javascript
{
  basic: {},           // 基本信息（必填字段在此）
  casualties: {},      // 人员伤亡
  disruptions: {},     // 四断情况
  infrastructure: {}, // 基础设施
  agriculture: {},     // 农业损失
  resources: {},       // 救援力量
  support_needs: {},   // 支援需求
  risk_outlook: {},    // 风险展望
  operations: {}       // 行动进展
}
```

---

### 1. basic - 基本信息 ⭐必填

| 字段名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| `disaster_type` | string | ✅ | 灾害类型（枚举值见下方） | "地震灾害" |
| `occurrence_time` | string | ✅ | 灾害发生时间（ISO 8601格式） | "2025-01-02T14:28:00" |
| `report_time` | string | ✅ | 报告时间 | "2025-11-03T00:30:00" |
| `location` | string | ✅ | 灾害地点 | "四川省阿坝州汶川县" |
| `command_unit` | string | ✅ | 指挥单位名称 | "前突侦察指挥组" |
| `frontline_overview` | string | ❌ | 一线情况概述 | "震中映秀镇建筑损毁严重" |
| `communication_status` | string | ❌ | 通信状态 | "卫星通信已建立" |
| `weather_trend` | string | ❌ | 天气趋势 | "未来24小时晴转多云" |

**disaster_type 枚举值**:
- `"地震灾害"` ← 推荐测试
- `"洪涝灾害"`
- `"台风灾害"`
- `"森林草原火灾"`
- `"地质灾害"`
- `"干旱灾害"`
- `"风雹灾害"`
- `"低温冷冻灾害"`
- `"雪灾"`
- `"沙尘暴灾害"`
- `"海洋灾害"`
- `"生物灾害"`

---

### 2. casualties - 人员伤亡

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `affected_population` | number | 受灾人口数 | 50000 |
| `deaths` | number | 死亡人数 | 100 |
| `missing` | number | 失踪人数 | 50 |
| `injured` | number | 受伤人数 | 300 |
| `emergency_evacuation` | number | 紧急转移安置人数 | 5000 |
| `emergency_resettlement` | number | 紧急安置人数 | 3000 |
| `urgent_life_support` | number | 急需生活救助人数 | 8000 |
| `requiring_support` | number | 需救助人数 | 10000 |
| `casualty_notes` | string | 备注说明 | "伤员主要为建筑倒塌所致" |

---

### 3. disruptions - 四断情况

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `road_blocked_villages` | number | 道路中断村庄数 | 15 |
| `power_outage_villages` | number | 停电村庄数 | 20 |
| `water_outage_villages` | number | 停水村庄数 | 18 |
| `telecom_outage_villages` | number | 通信中断村庄数 | 12 |
| `infrastructure_notes` | string | 备注说明 | "主要干道已抢通" |

---

### 4. infrastructure - 基础设施受损

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `collapsed_buildings` | number | 倒塌房屋数（间） | 500 |
| `severely_damaged_buildings` | number | 严重损坏房屋数 | 1200 |
| `mildly_damaged_buildings` | number | 一般损坏房屋数 | 3000 |
| `transport_damage` | string | 交通设施损毁情况 | "映秀至汶川主干道中断3处" |
| `communication_damage` | string | 通信设施损毁情况 | "3座通信基站损毁" |
| `energy_damage` | string | 能源设施损毁情况 | "2座变电站受损" |
| `water_facility_damage` | string | 供水设施损毁情况 | "主供水管网破裂" |
| `public_service_damage` | string | 公共服务设施损毁 | "县医院受损" |
| `direct_economic_loss` | number | 直接经济损失（万元） | 50000.0 |
| `other_critical_damage` | string | 其他重要设施损毁 | "学校、政府办公楼受损" |

---

### 5. agriculture - 农业损失

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `affected_area_ha` | number | 农作物受灾面积（公顷） | 5000.0 |
| `ruined_area_ha` | number | 农作物成灾面积（公顷） | 2000.0 |
| `destroyed_area_ha` | number | 农作物绝收面积（公顷） | 500.0 |
| `livestock_loss` | string | 畜牧业损失 | "猪500头、牛30头死亡" |
| `other_agri_loss` | string | 其他农业损失 | "大棚损毁200个" |

---

### 6. resources - 已投入救援力量

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `deployed_forces` | array | 已部署队伍列表 | 见下方 |
| `air_support` | string | 航空支援情况 | "2架直升机" |
| `medical_support` | string | 医疗支援情况 | "野战医疗点已建立" |
| `engineering_support` | string | 工程机械支援 | "工程机械5台" |
| `logistics_support` | string | 后勤保障情况 | "物资中转站已设立" |

**deployed_forces 数组元素结构**:
```javascript
{
  name: "消防救援队",              // 队伍名称
  personnel: 200,                  // 人数
  equipment: "生命探测仪、破拆工具", // 装备
  tasks: "搜救被困人员"             // 任务
}
```

---

### 7. support_needs - 支援需求

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `reinforcement_forces` | string | 需要增援的力量 | "需增援医疗队50人" |
| `material_shortages` | string | 物资缺口 | "帐篷500顶、食品10吨" |
| `infrastructure_requests` | string | 基础设施需求 | "需直升机2架" |
| `coordination_matters` | string | 需要协调的事项 | "需协调周边县市医院接收重伤员" |

---

### 8. risk_outlook - 风险展望

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `aftershock_risk` | string | 余震风险 | "余震风险高，持续监测" |
| `meteorological_risk` | string | 气象风险 | "未来24小时无降雨" |
| `hydrological_risk` | string | 水文风险 | "上游河道巡查中" |
| `hazardous_sources` | string | 危险源情况 | "无重大危化品风险" |
| `safety_measures` | string | 安全措施 | "已设置安全警戒线" |

---

### 9. operations - 行动进展

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `completed_actions` | string | 已完成的行动 | "已搜救300人" |
| `ongoing_actions` | string | 正在进行的行动 | "仍有50人被困待救" |
| `pending_actions` | string | 待决策的行动 | "需批准增援请求" |

---

## 📤 返回参数（出参）

### 成功响应（HTTP 200）

```javascript
{
  report_text: string,              // 完整报告文本（Markdown格式）
  key_points: string[],             // 要点摘要（便于前端展示）
  data_sources: string[],           // 数据来源列表
  confidence_score: number,         // 置信度评分（0-1）
  referenced_specs: string[],       // 引用的规范文档标题
  referenced_cases: string[],       // 引用的历史案例标题
  equipment_recommendations: EquipmentRecommendation[],  // 装备推荐
  errors: string[]                  // 错误或警告信息
}
```

### 返回字段详解

| 字段名 | 类型 | 说明 | 用途 |
|--------|------|------|------|
| `report_text` | string | **完整报告**（Markdown格式）<br>包含9个标准章节 | 直接渲染显示或导出 |
| `key_points` | string[] | 要点摘要列表 | 用于前端卡片展示 |
| `data_sources` | string[] | 数据来源标识<br>如 `["RAG规范文档库", "知识图谱"]` | 显示报告可信度依据 |
| `confidence_score` | number | 置信度评分（0-1）<br>0.7以上为高可信 | 显示报告质量指标 |
| `referenced_specs` | string[] | 引用的应急预案规范文档标题 | 提供溯源依据 |
| `referenced_cases` | string[] | 引用的历史救援案例标题 | 提供实践参考 |
| `equipment_recommendations` | array | 装备推荐清单 | 显示建议配置 |
| `errors` | string[] | 错误或警告信息 | 透明展示问题 |

**equipment_recommendations 数组元素结构**:
```javascript
{
  name: "生命探测仪",      // 装备名称
  score: 0.95,            // 推荐得分（0-1）
  source: "知识图谱"       // 推荐来源
}
```

---

## 💡 前端调用示例

### JavaScript (Fetch API)

```javascript
// 最简请求（只填必填字段）
async function generateReport() {
  try {
    const response = await fetch('http://localhost:8000/reports/rescue-assessment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        basic: {
          disaster_type: "地震灾害",
          occurrence_time: "2025-01-02T14:28:00",
          report_time: new Date().toISOString(),
          location: "四川省阿坝州",
          command_unit: "前突侦察指挥组"
        },
        casualties: {},
        disruptions: {},
        infrastructure: {},
        agriculture: {},
        resources: { deployed_forces: [] },
        support_needs: {},
        risk_outlook: {},
        operations: {}
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    // 渲染报告
    document.getElementById('report').innerHTML = marked.parse(data.report_text);

    // 显示置信度
    document.getElementById('confidence').textContent =
      `报告置信度: ${(data.confidence_score * 100).toFixed(1)}%`;

    return data;
  } catch (error) {
    console.error('生成报告失败:', error);
    throw error;
  }
}
```

### Vue 3 (Composition API)

```vue
<script setup>
import { ref } from 'vue'
import axios from 'axios'

const reportData = ref(null)
const loading = ref(false)
const error = ref(null)

async function generateReport(formData) {
  loading.value = true
  error.value = null

  try {
    const response = await axios.post(
      'http://localhost:8000/reports/rescue-assessment',
      formData,
      {
        headers: { 'Content-Type': 'application/json' },
        timeout: 60000 // 60秒超时
      }
    )

    reportData.value = response.data

    // 如果有错误信息，显示警告
    if (response.data.errors.length > 0) {
      console.warn('报告生成警告:', response.data.errors)
    }

  } catch (err) {
    error.value = err.response?.data?.detail || err.message
    console.error('生成报告失败:', err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <button @click="generateReport(formData)" :disabled="loading">
      {{ loading ? '生成中...' : '生成报告' }}
    </button>

    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="reportData">
      <!-- 置信度指示器 -->
      <div class="confidence-badge">
        置信度: {{ (reportData.confidence_score * 100).toFixed(1) }}%
      </div>

      <!-- Markdown报告渲染 -->
      <div class="report-content" v-html="renderMarkdown(reportData.report_text)"></div>

      <!-- 数据来源 -->
      <div class="sources">
        <h4>数据来源</h4>
        <ul>
          <li v-for="source in reportData.data_sources" :key="source">
            {{ source }}
          </li>
        </ul>
      </div>

      <!-- 装备推荐 -->
      <div v-if="reportData.equipment_recommendations.length > 0">
        <h4>推荐装备</h4>
        <ul>
          <li v-for="eq in reportData.equipment_recommendations" :key="eq.name">
            {{ eq.name }} (推荐度: {{ (eq.score * 100).toFixed(0) }}%)
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
```

### React (Hooks)

```jsx
import { useState } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'

function ReportGenerator() {
  const [reportData, setReportData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const generateReport = async (formData) => {
    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(
        'http://localhost:8000/reports/rescue-assessment',
        formData,
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 60000
        }
      )

      setReportData(response.data)

      // 检查警告
      if (response.data.errors.length > 0) {
        console.warn('报告生成警告:', response.data.errors)
      }

    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      console.error('生成报告失败:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <button onClick={() => generateReport(formData)} disabled={loading}>
        {loading ? '生成中...' : '生成报告'}
      </button>

      {error && <div className="error">{error}</div>}

      {reportData && (
        <div>
          <div className="confidence-badge">
            置信度: {(reportData.confidence_score * 100).toFixed(1)}%
          </div>

          <ReactMarkdown>{reportData.report_text}</ReactMarkdown>

          <div className="sources">
            <h4>数据来源</h4>
            <ul>
              {reportData.data_sources.map(source => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          </div>

          {reportData.equipment_recommendations.length > 0 && (
            <div>
              <h4>推荐装备</h4>
              <ul>
                {reportData.equipment_recommendations.map(eq => (
                  <li key={eq.name}>
                    {eq.name} (推荐度: {(eq.score * 100).toFixed(0)}%)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

---

## 🎨 前端展示建议

### 1. 置信度指示器

```javascript
function getConfidenceLevel(score) {
  if (score >= 0.7) return { label: '高', color: 'green' }
  if (score >= 0.4) return { label: '中', color: 'orange' }
  return { label: '低', color: 'red' }
}

// 使用
const level = getConfidenceLevel(data.confidence_score)
```

### 2. 报告章节导航

从 `report_text` 提取章节标题生成侧边导航：

```javascript
function extractSections(markdownText) {
  const lines = markdownText.split('\n')
  return lines
    .filter(line => line.startsWith('## '))
    .map(line => line.replace('## ', ''))
}
```

### 3. 数据来源徽章

```jsx
<div className="sources-badges">
  {data.data_sources.map(source => (
    <span className="badge">{source}</span>
  ))}
</div>
```

### 4. Markdown渲染库推荐

- **Vue**: `vue-markdown-render` 或 `@vueuse/markdown`
- **React**: `react-markdown`
- **原生JS**: `marked.js`

---

## ⚠️ 错误处理

### 常见HTTP状态码

| 状态码 | 说明 | 前端处理建议 |
|--------|------|-------------|
| **200** | 成功 | 正常渲染 |
| **422** | 参数验证失败 | 检查必填字段、枚举值是否正确 |
| **500** | 服务器内部错误 | 提示用户稍后重试，记录错误日志 |
| **504** | 请求超时 | 提示"报告生成中，请稍候"，延长超时时间 |

### 错误响应示例

```json
{
  "detail": [
    {
      "loc": ["body", "basic", "disaster_type"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

### 前端错误处理示例

```javascript
try {
  const response = await fetch(url, options)

  if (!response.ok) {
    if (response.status === 422) {
      const error = await response.json()
      // 提取字段错误信息
      const fieldErrors = error.detail.map(e =>
        `${e.loc.join('.')}: ${e.msg}`
      ).join('\n')

      alert(`参数错误:\n${fieldErrors}`)
    } else {
      alert(`请求失败: ${response.status}`)
    }
    return
  }

  const data = await response.json()

  // 检查业务级错误
  if (data.errors.length > 0) {
    console.warn('业务警告:', data.errors)
    // 可以选择向用户展示警告信息
  }

} catch (error) {
  console.error('网络错误:', error)
  alert('网络连接失败，请检查网络设置')
}
```

---

## 🚀 性能优化建议

### 1. 请求超时设置

建议设置 **60秒超时**（包含LLM生成时间）：

```javascript
axios.defaults.timeout = 60000
```

### 2. Loading状态管理

显示进度提示，避免用户重复点击：

```javascript
setLoading(true)
showMessage('正在生成报告，预计需要10-30秒...')
```

### 3. 报告缓存

对于相同输入参数，可以缓存报告结果：

```javascript
const cacheKey = JSON.stringify(formData)
if (reportCache.has(cacheKey)) {
  return reportCache.get(cacheKey)
}
```

### 4. 分页加载（长报告）

如果报告很长，考虑分章节加载：

```javascript
// 懒加载章节
const sections = extractSections(data.report_text)
loadSectionOnScroll(sections)
```

---

## 📋 完整请求示例（供复制）

### 最简请求（仅必填字段）

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

### 完整请求（包含所有可选字段）

参考 `POSTMAN_GUIDE.md` 中的完整请求示例。

---

## 🔍 调试技巧

### 1. 浏览器开发者工具

```javascript
// 查看请求详情
console.log('Request:', requestBody)
console.log('Response:', responseData)

// 性能分析
console.time('reportGeneration')
await generateReport()
console.timeEnd('reportGeneration')
```

### 2. 网络请求拦截

```javascript
// Axios请求拦截器
axios.interceptors.request.use(config => {
  console.log('API Request:', config)
  return config
})

// 响应拦截器
axios.interceptors.response.use(
  response => {
    console.log('API Response:', response.data)
    return response
  },
  error => {
    console.error('API Error:', error.response?.data)
    return Promise.reject(error)
  }
)
```

---

## 📞 技术支持

**API健康检查**: `GET http://localhost:8000/healthz`

**API文档**: `GET http://localhost:8000/docs` (FastAPI自动生成的交互式文档)

**后端日志位置**: `temp/server.log`

---

## 📝 更新日志

- **2025-11-03**: 初始版本发布
  - 实现KG+RAG集成
  - 支持9大类灾情数据输入
  - 输出专业救援评估报告
  - 包含置信度评分机制

---

**文档版本**: v1.0
**最后更新**: 2025-11-03
**维护者**: AI应急大脑项目组
