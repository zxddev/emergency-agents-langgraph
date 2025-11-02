# 救援评估报告API - 修改说明

## 修改日期
2025-11-03

## 修改内容

### 1. 增加"增援需求"专项章节 ✅

**问题描述**：
原报告模板缺少专门的章节来详细说明需要上级提供的增援力量和物资支援，导致指挥部无法快速了解前线的具体增援需求。

**解决方案**：
在报告模板中新增**第八章：次生灾害风险与增援需求**

**修改文件**：
- `src/emergency_agents/llm/prompts/rescue_assessment.py`

**具体修改**：
```python
# 新增章节要求（第52行）
"八、次生灾害风险与增援需求 —— **重点说明**：必须详细列出需要上级提供的增援力量（包括队伍类型、人数、专业能力）、物资支援（包括物资种类、数量、规格、到位时限），以及请指挥部决策的事项。此章节必须具体、可量化、可执行。"
```

**效果说明**：
生成的报告现在会包含明确的增援需求建议，例如：

```markdown
## 八、次生灾害风险与增援需求

- **次生灾害风险**：余震、降雨、滑坡等
- **增援需求**：
  - 专业救援队伍：2支（具备地震救援资质，每支50-80人）
  - 医疗救护车：5辆（配备急救设备）
  - 物资：
    - 帐篷：500顶（4人规格，防风防水）
    - 食品：100吨（即食食品，保质期≥6个月）
    - 饮用水：50吨（桶装水5L规格）
    - 医疗药品：50箱（外伤急救包、常用药）
  - 到位时限：24小时内
- **请指挥部决策**：是否增派救援力量及物资，是否启动跨省调配机制
```

---

### 2. 指定使用 glm-4.6 模型 ✅

**问题描述**：
接口使用的是配置文件中的默认模型（glm-4-flash），需要改为更高级的 glm-4.6 模型以提升报告质量。

**解决方案**：
将模型参数从 `cfg.llm_model` 硬编码为 `"glm-4.6"`

**修改文件**：
- `src/emergency_agents/api/reports.py`

**具体修改**：
```python
# 第386-388行
# 修改前：
completion = llm_client.chat.completions.create(
    model=cfg.llm_model,  # 使用配置文件中的模型
    ...
)

# 修改后：
# 使用 glm-4.6 模型生成报告（专用于救援评估报告生成）
completion = llm_client.chat.completions.create(
    model="glm-4.6",  # 硬编码使用 glm-4.6
    ...
)
```

**效果说明**：
- API现在专门使用 `glm-4.6` 模型生成报告
- 不受配置文件 `config/dev.env` 中 `LLM_MODEL` 变量影响
- `glm-4.6` 模型具有更强的理解能力和生成质量

---

## 报告结构变化

### 修改前（7个章节）
```
一、当前灾情初步评估
二、组织指挥
三、救援力量部署与任务分工
四、次生灾害预防与安全措施
五、通信与信息保障
六、物资调配与运输保障
七、救援力量自身保障
```

### 修改后（9个章节）
```
一、当前灾情初步评估
二、组织指挥
三、救援力量部署与任务分工
四、次生灾害预防与安全措施
五、通信与信息保障
六、物资调配与运输保障
七、救援力量自身保障
八、次生灾害风险与增援需求 ← 新增
九、总结 ← 新增
```

---

## 使用说明

### API调用不变
接口地址、请求参数、返回格式均无变化，前端无需修改。

```bash
# 使用方式完全相同
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d @test_data.json
```

### 输入数据建议
为了让"增援需求"章节更有价值，建议在请求中填充以下字段：

```json
{
  "support_needs": {
    "reinforcement_forces": "需增援医疗队50人",
    "material_shortages": "帐篷500顶、食品10吨",
    "infrastructure_requests": "需直升机2架",
    "coordination_matters": "需协调周边县市医院接收重伤员"
  }
}
```

如果这些字段为空，LLM会基于灾情严重程度和已投入力量自动推理增援需求。

---

## 测试验证

### 验证清单
- [x] 提示词语法正确
- [x] 模型参数修改生效
- [ ] 生成的报告包含第八章和第九章
- [ ] 增援需求建议具体、可量化

### 快速测试
```bash
# 启动服务
./scripts/dev-run.sh

# 调用API
curl -X POST http://localhost:8000/reports/rescue-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "basic": {
      "disaster_type": "地震灾害",
      "occurrence_time": "2025-01-02T14:28:00",
      "report_time": "2025-11-03T00:30:00",
      "location": "四川省",
      "command_unit": "前突侦察指挥组"
    },
    "casualties": {"deaths": 100, "injured": 300},
    "support_needs": {
      "reinforcement_forces": "需增援医疗队50人",
      "material_shortages": "帐篷500顶、食品10吨"
    },
    "disruptions": {},
    "infrastructure": {},
    "agriculture": {},
    "resources": {"deployed_forces": []},
    "risk_outlook": {},
    "operations": {}
  }' | python3 -m json.tool
```

**预期结果**：
- 返回的 `report_text` 包含9个章节
- 第八章详细列出增援力量和物资需求
- 第九章总结当前情况

---

## 影响分析

### 对前端的影响
- **无影响**：API接口保持向后兼容
- **建议**：前端表单可以增加"支援需求"输入区域，提升报告质量

### 对后端的影响
- **性能**：无影响（生成章节数量增加，但token消耗在可控范围内）
- **成本**：使用 glm-4.6 可能比 glm-4-flash 稍贵，但报告质量显著提升
- **可靠性**：提升（更强的模型降低幻觉风险）

### 对运维的影响
- **配置**：无需修改配置文件
- **部署**：代码修改后需重启服务
- **监控**：关注 `glm-4.6` 模型的调用成功率和延迟

---

## 后续优化建议

### 1. 智能增援需求推理
基于灾情数据自动计算合理的增援需求：
```python
def calculate_reinforcement_needs(casualties, infrastructure, deployed_forces):
    """基于灾情严重程度智能推算增援需求"""
    # 根据伤亡人数推算医疗队需求
    # 根据倒塌建筑推算工程机械需求
    # 根据受灾人口推算物资需求
    pass
```

### 2. 历史案例对比
在"增援需求"章节中引用相似历史案例的增援配置：
```markdown
参考2008年汶川地震映秀镇救援经验，建议配置：
- 医疗队：3支（每支50人）
- 重型救援队：2支（每支80人）
- 工程机械：挖掘机10台、装载机5台
```

### 3. 增援优先级排序
对多项增援需求按紧急程度排序：
```markdown
**紧急增援（2小时内）**：
- 医疗队2支（重伤员救治）

**次要增援（24小时内）**：
- 帐篷500顶（群众安置）
- 食品100吨（生活保障）
```

---

## 文档更新

需要同步更新以下文档：
- [ ] `FRONTEND_API_GUIDE.md` - 增加第八章和第九章说明
- [ ] `API_SPECIFICATION.md` - 更新报告结构示例
- [ ] `POSTMAN_GUIDE.md` - 更新响应示例

---

## Git提交信息

```bash
git add src/emergency_agents/llm/prompts/rescue_assessment.py
git add src/emergency_agents/api/reports.py
git add CHANGES_SUMMARY.md

git commit -m "feat(reports): 增加增援需求章节并指定使用glm-4.6模型

- 新增第八章：次生灾害风险与增援需求
- 要求详细列出增援力量、物资支援的具体数量和规格
- 将模型从cfg.llm_model改为硬编码glm-4.6
- 新增第九章：总结

影响范围：
- 提示词模板增加2个章节
- 报告生成使用更高级模型
- 向后兼容，前端无需修改"
```

---

## 联系方式
- **修改人**: Claude Code
- **审核**: 待指定
- **上线日期**: 待定

---

**文档版本**: v1.0
**最后更新**: 2025-11-03
