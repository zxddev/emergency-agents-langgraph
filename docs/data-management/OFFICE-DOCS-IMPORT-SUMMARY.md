# Office文档导入RAG总结报告

**日期**: 2025-10-28
**任务**: 将 docs/data-management 目录下的应急案例和预案文档导入到RAG系统

---

## ✅ 已完成工作

### 1. 文档提取与转换

创建了智能提取脚本 `scripts/import_office_docs_to_rag.py`，成功提取:

- **预案.xlsx**: 6个应急处置预案
  - 地震灾害应急处置预案
  - 洪涝灾害应急处置预案
  - 山体滑坡与泥石流灾害应急处置预案
  - 龙卷风灾害应急处置预案
  - 草原火灾应急处置预案
  - 城市内涝灾害应急处置预案

- **应急案例(1).docx**: 24个历史灾害案例
  - 2023年京津冀特大暴雨洪水
  - 2022年四川泸定6.8级地震
  - 2021年河南"7·20"特大暴雨
  - 2024年广东梅大高速茶阳段塌方灾害
  - ...等共24个案例

**输出**: `temp/emergency_docs.jsonl` (147.96 KB, 30个文档)

### 2. 智能分块策略

采用**语义分块**而非固定文本长度:
- 预案: 1行 = 1个文档 (包含完整的预案所有章节)
- 案例: 1个案例 = 1个文档 (标题 + 关联表格数据)

**优势**:
- 保持上下文完整性
- 便于精确检索
- 符合用户查询习惯

### 3. 元数据提取

每个文档包含丰富的元数据:
```json
{
  "id": "case_2023_flood_1",
  "text": "完整文本内容...",
  "meta": {
    "source": "应急管理部案例库",
    "document_type": "disaster_case",
    "year": 2023,
    "location": "京津冀",
    "disaster_type": "flood",
    "case_title": "案例一：2023年京津冀特大暴雨洪水",
    "extracted_date": "2025-10-28T15:04:48.016689"
  },
  "domain": "案例"
}
```

### 4. 修复embedding批量大小问题

**问题**: 智谱GLM API限制embedding批量最大64条
**错误**: `Error code: 400 - {'error': {'code': '1214', 'message': 'input数组最大不得超过64条'}}`

**解决方案**: 修改 `src/emergency_agents/rag/pipe.py:75`
```python
Settings.embed_model = OpenAIEmbedding(
    model_name=self.embedding_model,
    api_key=self.openai_api_key,
    api_base=self.openai_base_url,
    http_client=custom_http_client,
    embed_batch_size=32,  # 智谱GLM API限制：最大64条，设置32保守处理
)
```

---

## ⚠️ 当前状态

### 导入状态: 未确认成功

通过 Qdrant API 检查，当前只有 `mem0_collection` 集合，未发现预期的:
- `rag_规范` (应包含6个预案)
- `rag_案例` (应包含24个案例)

### 可能原因

1. **导入进程异常退出**: embedding batch size 32仍可能超出限制
2. **网络问题**: 到Qdrant服务器 8.147.130.215:6333 的连接问题
3. **权限问题**: Qdrant API密钥或集合创建权限
4. **LlamaIndex版本兼容性**: embed_batch_size参数可能不生效

---

## 🔧 下一步行动

### 方案A: 手动分批导入（推荐）

将30个文档分成更小的批次手动导入:

```bash
# 1. 拆分JSONL文件为小批次
head -n 10 temp/emergency_docs.jsonl > temp/batch1.jsonl
tail -n +11 temp/emergency_docs.jsonl | head -n 10 > temp/batch2.jsonl
tail -n +21 temp/emergency_docs.jsonl > temp/batch3.jsonl

# 2. 逐批导入
python -m emergency_agents.rag.cli temp/batch1.jsonl
python -m emergency_agents.rag.cli temp/batch2.jsonl
python -m emergency_agents.rag.cli temp/batch3.jsonl
```

### 方案B: 调试embedding问题

```bash
# 测试单个文档导入
head -n 1 temp/emergency_docs.jsonl > temp/test_single.jsonl
python -m emergency_agents.rag.cli temp/test_single.jsonl 2>&1 | tee temp/import_debug.log

# 检查详细错误信息
```

### 方案C: 使用更小的batch size

进一步降低batch size到16或8:
```python
# src/emergency_agents/rag/pipe.py:75
embed_batch_size=16,  # 更保守的批量大小
```

### 方案D: 检查Qdrant服务器配置

```bash
# 检查Qdrant服务器状态
curl -H "api-key: qdrantzmkj123456" http://8.147.130.215:6333/collections

# 检查磁盘空间
ssh user@8.147.130.215 "df -h"

# 检查Qdrant日志
ssh user@8.147.130.215 "docker logs qdrant 2>&1 | tail -n 100"
```

---

## 📊 数据统计

| 类别 | 数量 | 文件大小 | Domain |
|------|------|----------|---------|
| 应急预案 | 6个 | ~7.5KB | 规范 |
| 历史案例 | 24个 | ~140KB | 案例 |
| 总计 | 30个 | 147.96KB | - |

### 灾害类型分布

- 地震: 6个案例 + 1个预案
- 洪涝/暴雨: 8个案例 + 2个预案
- 滑坡/泥石流: 4个案例 + 1个预案
- 其他: 6个案例 + 2个预案

---

## 📝 使用说明

### 重新运行提取脚本

```bash
cd /home/msq/gitCode/new_1/emergency-agents-langgraph
source .venv/bin/activate
python scripts/import_office_docs_to_rag.py
```

### 查看提取的JSONL文件

```bash
# 查看文档数量
wc -l temp/emergency_docs.jsonl

# 查看第一个文档
head -n 1 temp/emergency_docs.jsonl | python3 -m json.tool

# 查看所有文档ID
jq -r '.id' temp/emergency_docs.jsonl
```

### 手动导入到Qdrant

```bash
# 方式1: 使用现有CLI工具
python -m emergency_agents.rag.cli temp/emergency_docs.jsonl

# 方式2: 通过API端点
curl -X POST http://localhost:8008/rag/index \
  -H "Content-Type: application/json" \
  -d @temp/emergency_docs.jsonl
```

---

## 🎯 成功标准

导入成功后，应该满足:

1. ✅ Qdrant中存在 `rag_规范` 和 `rag_案例` 两个集合
2. ✅ `rag_规范` 包含6个向量（预案）
3. ✅ `rag_案例` 包含24个向量（案例）
4. ✅ 可以通过RAG检索到相关文档
5. ✅ 检索返回的文档包含完整的元数据

### 验证命令

```bash
# 检查集合
curl -s -H "api-key: qdrantzmkj123456" \
  http://8.147.130.215:6333/collections | python3 -m json.tool

# 检查文档数量
curl -s -H "api-key: qdrantzmkj123456" \
  http://8.147.130.215:6333/collections/rag_案例 | python3 -m json.tool

# 测试检索
curl -X POST http://localhost:8008/rag/query \
  -H "Content-Type: application/json" \
  -d '{"domain":"案例","query":"四川地震救援案例","top_k":3}'
```

---

## 📚 相关文档

- [RAG-KG-DATA-GUIDE.md](./RAG-KG-DATA-GUIDE.md) - RAG和知识图谱数据管理完整指南
- [scripts/import_office_docs_to_rag.py](../../scripts/import_office_docs_to_rag.py) - 提取脚本源码
- [src/emergency_agents/rag/pipe.py](../../src/emergency_agents/rag/pipe.py) - RAG Pipeline实现
- [src/emergency_agents/rag/cli.py](../../src/emergency_agents/rag/cli.py) - CLI导入工具

---

**报告生成时间**: 2025-10-28 15:30
**生成工具**: Claude Code (Sequential Thinking Analysis)
**分析深度**: Linus式5层思考
