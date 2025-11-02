# 测试数据文件说明

本目录存放救援评估报告API的测试数据（Fixtures）。

## 📁 文件列表

### 1. rescue_assessment_minimal_input.json

**最简入参示例** - 仅包含必填字段

用途：
- 快速测试API是否正常工作
- 验证API对空字段的处理
- 最小化测试数据

包含字段：
- `basic`: 5个必填字段（disaster_type, occurrence_time, report_time, location, command_unit）
- 其他8个对象均为空

---

### 2. rescue_assessment_complete_input.json

**完整入参示例** - 包含所有可选字段

用途：
- 验证API对完整数据的处理
- 测试"增援需求"章节生成质量
- 生成高质量、高置信度报告

包含字段：
- `basic`: 8个字段（全部填充）
- `casualties`: 9个字段（人员伤亡详细数据）
- `disruptions`: 5个字段（四断情况）
- `infrastructure`: 10个字段（基础设施受损）
- `agriculture`: 5个字段（农业损失）
- `resources`: 5个字段 + 4支救援队伍
- `support_needs`: 4个字段（详细增援需求）
- `risk_outlook`: 5个字段（风险评估）
- `operations`: 3个字段（行动进展）

---

## 🚀 使用方式

### 方式1：直接使用curl

```bash
# 测试最简入参
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/rescue_assessment_minimal_input.json

# 测试完整入参
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/rescue_assessment_complete_input.json
```

---

### 方式2：使用Python测试脚本

```bash
# 使用完整测试数据
python3 tests/api/test_reports_new_features.py

# 在脚本中修改为使用最简数据
# 编辑 test_reports_new_features.py 第44行：
# test_payload = load_test_payload(use_complete=False)
```

---

### 方式3：在pytest中使用

```python
import json
import os
import pytest

@pytest.fixture
def minimal_input():
    """加载最简测试数据"""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "..", "fixtures",
        "rescue_assessment_minimal_input.json"
    )
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def complete_input():
    """加载完整测试数据"""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "..", "fixtures",
        "rescue_assessment_complete_input.json"
    )
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_minimal_input(minimal_input):
    """测试最简入参"""
    response = requests.post(API_URL, json=minimal_input)
    assert response.status_code == 200


def test_complete_input(complete_input):
    """测试完整入参"""
    response = requests.post(API_URL, json=complete_input)
    assert response.status_code == 200
    data = response.json()
    assert data['confidence_score'] > 0.5  # 完整数据应有更高置信度
```

---

## 📊 数据对比

| 指标 | minimal_input | complete_input |
|------|--------------|----------------|
| **必填字段** | ✅ 完整 | ✅ 完整 |
| **可选字段** | ❌ 全部为空 | ✅ 全部填充 |
| **救援队伍** | 0支 | 4支 |
| **增援需求** | 未填写 | 详细填写 |
| **风险评估** | 未填写 | 详细填写 |
| **预期置信度** | 0.2-0.3 | 0.7-0.9 |
| **报告质量** | 基础版 | 专业版 |

---

## 🎯 测试场景建议

### 场景1：冒烟测试（Smoke Test）

**使用**: `minimal_input.json`

**目的**: 快速验证API是否正常工作

**验证点**:
- HTTP 200响应
- 返回report_text不为空
- 包含9个章节标题

---

### 场景2：功能完整性测试

**使用**: `complete_input.json`

**目的**: 验证新增的"增援需求"章节

**验证点**:
- 第八章存在
- 包含具体数量（如"500顶"、"10吨"）
- 包含增援关键词（"需"、"增援"、"支援"）
- 置信度评分 > 0.5

---

### 场景3：性能测试

**使用**: `complete_input.json`

**目的**: 测试复杂数据处理性能

**验证点**:
- 响应时间 < 30秒
- KG+RAG调用成功
- 无超时错误

---

### 场景4：边界测试

**使用**: 修改后的 `minimal_input.json`

**测试点**:
- 空字段处理
- 必填字段缺失（预期422错误）
- 枚举值错误（预期422错误）
- 日期格式错误（预期422错误）

---

## 📝 修改测试数据

### 修改字段值

直接编辑JSON文件：

```json
{
  "basic": {
    "disaster_type": "洪涝灾害",  // 修改灾害类型
    "location": "湖北省武汉市"     // 修改地点
  }
}
```

### 添加新字段

参考 `complete_input.json` 的完整结构添加字段。

### 创建新的测试数据文件

```bash
# 复制现有文件
cp tests/fixtures/rescue_assessment_complete_input.json \
   tests/fixtures/rescue_assessment_custom.json

# 编辑新文件
vim tests/fixtures/rescue_assessment_custom.json
```

---

## 🔍 数据验证

### JSON格式验证

```bash
# 使用jq验证JSON格式
cat tests/fixtures/rescue_assessment_minimal_input.json | jq .
cat tests/fixtures/rescue_assessment_complete_input.json | jq .
```

### 必填字段验证

必填字段（5个）：
- `basic.disaster_type` (枚举值)
- `basic.occurrence_time` (ISO 8601日期)
- `basic.report_time` (ISO 8601日期)
- `basic.location` (字符串)
- `basic.command_unit` (字符串)

---

## 🎨 前端调用示例

```javascript
// 方式1：直接从文件加载（开发环境）
fetch('/tests/fixtures/rescue_assessment_complete_input.json')
  .then(res => res.json())
  .then(data => {
    return fetch('http://localhost:8000/reports/rescue-assessment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
  })
  .then(res => res.json())
  .then(report => console.log(report.report_text))

// 方式2：手动构造（生产环境）
const payload = {
  basic: {
    disaster_type: formData.disasterType,
    occurrence_time: formData.occurTime,
    report_time: new Date().toISOString(),
    location: formData.location,
    command_unit: formData.commandUnit
  },
  casualties: formData.casualties || {},
  // ... 其他字段
}

fetch('http://localhost:8000/reports/rescue-assessment', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
```

---

## 🐛 常见问题

### Q1: 为什么测试失败？

检查服务是否启动：
```bash
curl http://localhost:8000/healthz
```

### Q2: 如何查看实际请求内容？

```bash
# 使用jq美化输出
cat tests/fixtures/rescue_assessment_complete_input.json | jq .
```

### Q3: 如何修改灾害类型？

只能使用以下12个枚举值之一：
- 地震灾害、洪涝灾害、台风灾害、风雹灾害
- 低温冷冻灾害、雪灾、沙尘暴灾害、地质灾害
- 海洋灾害、森林草原火灾、生物灾害、干旱灾害

---

## 📚 相关文档

- **API规范**: `../../API_SPECIFICATION.md`
- **前端调用指南**: `../../FRONTEND_API_GUIDE.md`
- **Postman指南**: `../../POSTMAN_GUIDE.md`
- **测试脚本**: `../api/test_reports_new_features.py`

---

**创建日期**: 2025-11-03
**维护者**: AI应急大脑项目组
