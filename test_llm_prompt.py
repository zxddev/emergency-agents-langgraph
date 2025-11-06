#!/usr/bin/env python
"""直接测试LLM意图识别提示词"""

import json
from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
from emergency_agents.intent.providers.llm import _build_prompt

# 初始化配置
cfg = AppConfig.load_from_env()
llm_client = get_openai_client(cfg)
llm_model = cfg.llm_model or "glm-4-flash"

# 构建提示
test_text = "查看所有携带设备"
prompt = _build_prompt(test_text)

print("=" * 60)
print("LLM收到的完整提示:")
print("=" * 60)
print(prompt)
print()
print("=" * 60)

# 测试LLM响应
messages = [
    {"role": "system", "content": "你是应急救援指挥车的意图识别专家，需要判断指挥员的语音或文本请求属于哪个业务意图。请严格输出JSON，不要包含额外解释。"},
    {"role": "user", "content": prompt}
]

print("正在调用LLM...")
response = llm_client.chat.completions.create(
    model=llm_model,
    messages=messages,
    temperature=0.0
)

content = response.choices[0].message.content
print("LLM响应:")
print(content)
print()

# 尝试解析
try:
    # 提取JSON（可能包含markdown代码块）
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content

    result = json.loads(json_str)
    print("解析结果:")
    print(f"意图类型: {result.get('intent_type')}")
    print(f"槽位: {json.dumps(result.get('slots', {}), ensure_ascii=False, indent=2)}")
    print(f"置信度: {result.get('meta', {}).get('confidence', 0)}")

    # 检查是否包含系统数据查询相关
    if 'SYSTEM' in str(result.get('intent_type', '')).upper():
        print("✅ 包含SYSTEM相关意图")
    else:
        print("❌ 没有识别为SYSTEM相关意图")

    # 显示排名
    ranking = result.get('ranking', [])
    if ranking:
        print("\n意图排名:")
        for r in ranking:
            print(f"  - {r.get('intent')}: {r.get('confidence', 0)}")

except Exception as e:
    print(f"解析失败: {e}")