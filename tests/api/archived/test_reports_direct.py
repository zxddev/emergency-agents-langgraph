#!/usr/bin/env python3
"""直接测试救援评估报告生成功能（绕过FastAPI服务）"""

import sys
import os
import json
from datetime import datetime

# 设置路径
sys.path.insert(0, 'src')

# 加载环境变量
from dotenv import load_dotenv
load_dotenv('config/dev.env')

# 导入必要的模块
from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
from emergency_agents.api.reports import RescueAssessmentInput, _calculate_input_completeness, _calculate_confidence_score
from emergency_agents.llm.prompts.rescue_assessment import build_rescue_assessment_prompt

print("=" * 60)
print("直接测试救援评估报告生成功能")
print("=" * 60)

# 测试数据
test_payload = {
    "basic": {
        "disaster_type": "地震",
        "location": "四川省阿坝州汶川县映秀镇",
        "datetime": "2025-01-02T14:28:00",
        "intensity": "里氏8.0级",
        "frontline_overview": "震中映秀镇建筑损毁严重，道路中断，通信受阻"
    },
    "casualties": {
        "dead": 100,
        "missing": 50,
        "injured": 300,
        "trapped": 200
    },
    "infrastructure": {
        "断路": ["映秀镇至汶川县城公路中断"],
        "断电": ["全镇电力系统瘫痪"],
        "断水": ["供水管网破裂"],
        "断网": ["通信基站损毁"]
    },
    "organization": {
        "指挥体系": "前线指挥部已建立",
        "工作组": ["救援组", "医疗组", "物资组", "通信保障组"]
    },
    "forces": [
        {
            "name": "消防救援队",
            "count": 200,
            "mission": "搜救被困人员"
        },
        {
            "name": "医疗队",
            "count": 50,
            "mission": "现场医疗救治"
        }
    ],
    "hazards": [
        {
            "type": "余震",
            "risk_level": "高",
            "measures": "实时监测，随时准备撤离"
        }
    ],
    "supplies": [
        {
            "name": "帐篷",
            "current": 500,
            "needed": 1000,
            "status": "紧缺"
        }
    ]
}

print("\n步骤1: 初始化配置和LLM客户端...")
try:
    cfg = AppConfig.load_from_env()
    llm_client = get_openai_client(cfg)
    print(f"✅ LLM配置: {cfg.openai_base_url}, 模型: {cfg.llm_model}")
except Exception as e:
    print(f"❌ 初始化失败: {e}")
    sys.exit(1)

print("\n步骤2: 解析输入数据...")
try:
    input_model = RescueAssessmentInput(**test_payload)
    print(f"✅ 输入数据解析成功")
    print(f"   灾害类型: {input_model.basic.disaster_type}")
    print(f"   地点: {input_model.basic.location}")
except Exception as e:
    print(f"❌ 输入数据解析失败: {e}")
    sys.exit(1)

print("\n步骤3: 计算输入完整性...")
try:
    input_completeness = _calculate_input_completeness(input_model)
    print(f"✅ 输入完整性: {input_completeness:.2%}")
except Exception as e:
    print(f"❌ 计算完整性失败: {e}")
    sys.exit(1)

print("\n步骤4: 构建Prompt（不使用外部参考资料）...")
try:
    # 转换为dict用于prompt生成
    prompt_payload = json.loads(input_model.model_dump_json())

    # 构建prompt（模拟无KG/RAG的场景）
    prompt = build_rescue_assessment_prompt(prompt_payload, reference_materials=None)
    print(f"✅ Prompt构建成功，长度: {len(prompt)} 字符")
    print(f"\nPrompt预览（前300字符）:")
    print(prompt[:300])
except Exception as e:
    print(f"❌ Prompt构建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤5: 调用LLM生成报告...")
try:
    completion = llm_client.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": "你是专业的应急救援指挥官，负责向上级汇报灾情。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,  # 稳定输出
        max_tokens=4000,
    )

    report_text = completion.choices[0].message.content
    print(f"✅ LLM生成成功，报告长度: {len(report_text)} 字符")

    # 提取关键要点（简单分割）
    lines = [line.strip() for line in report_text.split('\n') if line.strip()]
    key_points = [line for line in lines if line.startswith(('一、', '二、', '三、', '四', '五、', '六、', '七、', '-', '•'))][:10]

    print(f"\n关键要点:")
    for point in key_points[:5]:
        print(f"  {point}")

except Exception as e:
    print(f"❌ LLM调用失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n步骤6: 计算置信度评分（无外部数据支持）...")
try:
    confidence = _calculate_confidence_score(
        input_completeness=input_completeness,
        spec_count=0,  # 无规范检索
        case_count=0,  # 无案例检索
        equipment_count=0,  # 无装备推荐
    )
    print(f"✅ 置信度评分: {confidence:.3f}")
except Exception as e:
    print(f"❌ 置信度计算失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("测试结果摘要")
print("=" * 60)
print(f"✅ 输入完整性: {input_completeness:.2%}")
print(f"✅ 置信度评分: {confidence:.3f} (无外部数据支持)")
print(f"✅ 报告长度: {len(report_text)} 字符")
print(f"✅ 关键要点数: {len(key_points)}")
print(f"\n⚠️ 注意: 此测试未使用KG/RAG外部数据，仅验证核心功能")

print("\n" + "=" * 60)
print("完整报告内容")
print("=" * 60)
print(report_text)
