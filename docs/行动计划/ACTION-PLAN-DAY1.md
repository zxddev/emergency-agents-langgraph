# 立即行动计划 - Day 1
> **目标**：证明AI能工作，建立最小可用原型  
> **时间**：1天（8小时）  
> **人员**：1-2人  

---

## 上午（4小时）

### Task 1.1：修复interrupt语法错误（5分钟）

**文件**：`src/emergency_agents/graph/app.py`

**当前代码（错误）**：
```python
graph.add_node("await", lambda s: {}, interrupt_before=True)  # ❌ 错误语法
```

**修改为**：
```python
# 定义节点（不带interrupt参数）
graph.add_node("await", lambda s: {})

# 在compile时配置中断点
app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["await"]  # ✅ 正确语法
)
```

**验证**：
```bash
python -m pytest tests/ -k test_interrupt -v
```

---

### Task 1.2：配置LLM客户端（1小时）

**选项A：使用智谱API（推荐，快速）**

1. 获取智谱API Key（https://open.bigmodel.cn/）

2. 修改 `config/dev.env`：
```bash
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_API_KEY=your_zhipu_api_key
LLM_MODEL=glm-4  # 或 glm-4-plus
```

3. 测试连接：
```python
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig

cfg = AppConfig.load_from_env()
client = get_openai_client(cfg)

response = client.chat.completions.create(
    model=cfg.llm_model,
    messages=[{"role": "user", "content": "你好"}],
    temperature=0
)
print(response.choices[0].message.content)
```

**选项B：使用本地vLLM（需要GPU）**

1. 部署vLLM服务（另一台机器或容器）
```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 8000
```

2. 修改配置指向vLLM：
```bash
OPENAI_BASE_URL=http://your-vllm-server:8000/v1
LLM_MODEL=Qwen2.5-7B-Instruct
```

---

### Task 1.3：实现态势感知AI智能体（3小时）

**创建文件**：`src/emergency_agents/agents/situation.py`

```python
#!/usr/bin/env python3
"""态势感知智能体 - 从非结构化报告提取结构化信息"""
import json
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def safe_json_parse(text: str, max_retries: int = 2) -> Dict[str, Any]:
    """安全的JSON解析，带容错和重试"""
    # 尝试1：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试2：提取代码块
    match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试3：提取{}之间的内容
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 失败：返回默认值
    logger.error(f"JSON解析失败: {text[:200]}...")
    return {
        "disaster_type": "unknown",
        "magnitude": 0.0,
        "epicenter": {"lat": 0.0, "lng": 0.0},
        "parse_error": True
    }


def situation_agent(state: Dict[str, Any], llm_client) -> Dict[str, Any]:
    """
    态势感知智能体
    
    输入：state["raw_report"] - 非结构化文本报告
    输出：state["situation"] - 结构化JSON数据
    """
    raw_report = state.get("raw_report", "")
    
    if not raw_report:
        return state | {"situation": {"error": "无输入报告"}}
    
    # 构造提示词
    prompt = f"""从以下灾情报告中提取结构化信息：

{raw_report}

请以JSON格式返回：
{{
  "disaster_type": "earthquake/flood/fire/...",
  "magnitude": 7.8,
  "epicenter": {{"lat": 31.0, "lng": 103.4}},
  "depth_km": 14,
  "time": "2025-01-15T14:28:00Z",
  "affected_area": "汶川县",
  "nearby_facilities": ["水库", "化工厂", ...],
  "initial_casualties": {{"estimated": 1000}}
}}

只返回JSON，不要有任何其他文字。如果某些信息缺失，使用null或空数组。"""
    
    # 调用LLM
    try:
        response = llm_client.chat.completions.create(
            model="glm-4",  # 或从config读取
            messages=[{"role": "user", "content": prompt}],
            temperature=0  # 确定性输出
        )
        
        llm_output = response.choices[0].message.content
        structured = safe_json_parse(llm_output)
        
        logger.info(f"态势感知成功: {structured.get('disaster_type')}, magnitude={structured.get('magnitude')}")
        
        return state | {"situation": structured}
        
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return state | {
            "situation": {"error": str(e)},
            "last_error": {"agent": "situation", "error": str(e)}
        }
```

**集成到LangGraph**：修改 `src/emergency_agents/graph/app.py`

```python
from emergency_agents.agents.situation import situation_agent
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig

# 在build_app中
cfg = AppConfig.load_from_env()
llm_client = get_openai_client(cfg)

def situation_node(state: RescueState) -> dict:
    """态势感知节点"""
    return situation_agent(state, llm_client)

# 替换原来的start_node
graph.add_node("situation", situation_node)
graph.set_entry_point("situation")
graph.add_edge("situation", "plan")
```

---

## 下午（4小时）

### Task 1.4：编写测试（2小时）

**创建文件**：`tests/test_situation_agent.py`

```python
#!/usr/bin/env python3
import pytest
from emergency_agents.agents.situation import situation_agent, safe_json_parse
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig


def test_safe_json_parse_direct():
    """测试直接JSON解析"""
    text = '{"key": "value"}'
    result = safe_json_parse(text)
    assert result == {"key": "value"}


def test_safe_json_parse_code_block():
    """测试代码块中的JSON"""
    text = '```json\n{"key": "value"}\n```'
    result = safe_json_parse(text)
    assert result == {"key": "value"}


def test_safe_json_parse_invalid():
    """测试无效JSON的容错"""
    text = 'this is not json'
    result = safe_json_parse(text)
    assert "parse_error" in result


@pytest.mark.integration
def test_situation_agent_earthquake():
    """测试地震报告的态势感知"""
    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    
    state = {
        "rescue_id": "test_001",
        "raw_report": "四川汶川发生7.8级地震，震中位于北纬31.0度、东经103.4度，震源深度14公里。"
    }
    
    result = situation_agent(state, client)
    
    # 验证基本结构
    assert "situation" in result
    sit = result["situation"]
    
    # 验证关键字段
    assert sit.get("disaster_type") in ["earthquake", "地震"]
    assert 7.5 <= sit.get("magnitude", 0) <= 8.0  # 允许一定误差
    
    # 验证位置
    epicenter = sit.get("epicenter", {})
    assert 30.0 <= epicenter.get("lat", 0) <= 32.0
    assert 103.0 <= epicenter.get("lng", 0) <= 104.0
    
    print(f"✅ 态势感知测试通过: {sit}")


@pytest.mark.integration
def test_situation_agent_with_facilities():
    """测试识别附近设施"""
    cfg = AppConfig.load_from_env()
    client = get_openai_client(cfg)
    
    state = {
        "raw_report": "汶川7.8级地震，震中附近有紫坪铺水库和多家化工厂。"
    }
    
    result = situation_agent(state, client)
    sit = result["situation"]
    
    # 应该识别出附近设施
    facilities = sit.get("nearby_facilities", [])
    assert len(facilities) > 0
    
    # 应该包含"水库"或"化工厂"
    facilities_str = str(facilities).lower()
    assert "水库" in facilities_str or "化工" in facilities_str
    
    print(f"✅ 设施识别测试通过: {facilities}")


if __name__ == "__main__":
    # 直接运行集成测试
    test_situation_agent_earthquake()
    test_situation_agent_with_facilities()
```

**运行测试**：
```bash
# 运行所有测试
pytest tests/test_situation_agent.py -v

# 只运行集成测试
pytest tests/test_situation_agent.py -m integration -v

# 查看详细输出
pytest tests/test_situation_agent.py -v -s
```

---

### Task 1.5：端到端验证（2小时）

**目标**：从API调用到AI响应的完整流程

**测试脚本**：
```bash
# 1. 启动API服务（新终端）
python -m uvicorn emergency_agents.api.main:app --reload --port 8008

# 2. 测试健康检查
curl http://localhost:8008/healthz

# 3. 测试态势感知（新终端）
curl -X POST "http://localhost:8008/threads/start?rescue_id=test_day1" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_report": "四川汶川发生7.8级地震，震中位于北纬31.0度、东经103.4度，震源深度14公里。震中附近有紫坪铺水库。"
  }'

# 4. 检查响应
# 应该看到：{"rescue_id": "test_day1", "state": {"situation": {...}}}
```

**修改API以支持raw_report**：`src/emergency_agents/api/main.py`

```python
from pydantic import BaseModel

class StartThreadRequest(BaseModel):
    raw_report: str

@app.post("/threads/start")
async def start_thread(rescue_id: str, req: StartThreadRequest):
    init_state = {
        "rescue_id": rescue_id,
        "raw_report": req.raw_report
    }
    result = _graph_app.invoke(
        init_state,
        config={"configurable": {"thread_id": f"rescue-{rescue_id}"}}
    )
    return {"rescue_id": rescue_id, "state": result}
```

---

## Day 1 结束检查清单

### 必须完成（P0）
- [ ] interrupt语法错误已修复
- [ ] LLM客户端能正常调用（测试通过）
- [ ] 态势感知智能体实现完成
- [ ] 至少2个测试通过（JSON解析 + 基本态势感知）

### 验收标准
```bash
# 运行这个命令，应该看到AI提取的结构化数据
python -c "
from emergency_agents.agents.situation import situation_agent
from emergency_agents.llm.client import get_openai_client
from emergency_agents.config import AppConfig
import json

cfg = AppConfig.load_from_env()
client = get_openai_client(cfg)

state = {'raw_report': '四川汶川发生7.8级地震，震中位于北纬31.0度、东经103.4度'}
result = situation_agent(state, client)

print(json.dumps(result['situation'], ensure_ascii=False, indent=2))
"
```

**期望输出**：
```json
{
  "disaster_type": "earthquake",
  "magnitude": 7.8,
  "epicenter": {
    "lat": 31.0,
    "lng": 103.4
  },
  ...
}
```

### 如果Day 1失败

**失败场景1：LLM连接失败**
- 检查API Key是否正确
- 检查网络连接
- 尝试使用curl直接调用LLM API验证

**失败场景2：JSON解析总是失败**
- 检查prompt是否清晰（"只返回JSON"）
- 降低temperature到0
- 在prompt末尾加上"不要有任何解释，只返回JSON对象"

**失败场景3：提取的数据不准确**
- 增加few-shot示例
- 调整prompt格式
- 考虑换用更强的模型（glm-4-plus）

### 失败则停止

如果Day 1结束时AI还不能工作：
1. **不要继续往下走**
2. 专注解决基础设施问题
3. 寻求帮助（LLM配置、网络问题）
4. 考虑换一个LLM服务商

---

## 成功则继续

如果Day 1成功（AI能工作）：
- ✅ 明天开始Phase 2：风险预测AI
- ✅ 你已经证明了技术可行性
- ✅ 团队信心建立

---

**关键原则**：
> "First, make it work. Then, make it right. Then, make it fast."  
> "先让它能跑，再让它跑对，最后让它跑快。"

**Linus的忠告**：
> "Don't waste time on perfect code. Write code that works, then improve it."

---

**文档版本**：v1.0  
**目标**：Day 1 - 证明AI能工作  
**下一步**：Day 2-3 - 风险预测AI + KG集成

