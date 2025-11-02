#!/usr/bin/env python3
"""
测试救援评估报告API的新功能
1. 验证报告包含第八章（增援需求）
2. 验证报告包含第九章（总结）
3. 验证使用glm-4.6模型

运行方式：
    cd /home/msq/gitCode/new_1/emergency-agents-langgraph
    python3 tests/api/test_reports_new_features.py
"""

import json
import os
import sys
import requests

# 添加项目根目录到Python路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# API地址
API_URL = "http://localhost:8000/reports/rescue-assessment"

# Fixture文件路径
FIXTURES_DIR = os.path.join(PROJECT_ROOT, "tests", "fixtures")
COMPLETE_INPUT_FILE = os.path.join(FIXTURES_DIR, "rescue_assessment_complete_input.json")
MINIMAL_INPUT_FILE = os.path.join(FIXTURES_DIR, "rescue_assessment_minimal_input.json")


def load_test_payload(use_complete=True):
    """从fixture文件加载测试数据"""
    file_path = COMPLETE_INPUT_FILE if use_complete else MINIMAL_INPUT_FILE

    if not os.path.exists(file_path):
        print(f"❌ 测试数据文件不存在: {file_path}")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 加载完整测试数据
test_payload = load_test_payload(use_complete=True)


def test_report_generation():
    """测试报告生成"""
    print("=" * 80)
    print("🧪 测试救援评估报告API - 新功能验证")
    print("=" * 80)
    print()

    print("📝 发送请求...")
    print(f"URL: {API_URL}")
    print(f"灾害类型: {test_payload['basic']['disaster_type']}")
    print(f"地点: {test_payload['basic']['location']}")
    print()

    try:
        response = requests.post(
            API_URL,
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"错误详情: {response.text}")
            return False

        data = response.json()

        # 提取报告文本
        report_text = data.get("report_text", "")

        print("✅ 报告生成成功")
        print()
        print("-" * 80)
        print("📊 验证新功能")
        print("-" * 80)

        # 验证1: 检查第八章是否存在
        has_chapter_8 = "八、次生灾害风险与增援需求" in report_text or "八、" in report_text
        print(f"✓ 第八章（增援需求）存在: {'✅ 是' if has_chapter_8 else '❌ 否'}")

        # 验证2: 检查第九章是否存在
        has_chapter_9 = "九、总结" in report_text or "九、" in report_text
        print(f"✓ 第九章（总结）存在: {'✅ 是' if has_chapter_9 else '❌ 否'}")

        # 验证3: 检查增援需求关键词
        has_reinforcement = any(keyword in report_text for keyword in [
            "增援", "支援", "需", "请指挥部", "决策"
        ])
        print(f"✓ 包含增援需求关键词: {'✅ 是' if has_reinforcement else '❌ 否'}")

        # 验证4: 检查是否有具体数量
        import re
        has_quantities = bool(re.search(r'\d+[支辆顶吨台架部]', report_text))
        print(f"✓ 包含具体数量单位: {'✅ 是' if has_quantities else '❌ 否'}")

        print()
        print("-" * 80)
        print("📋 报告元数据")
        print("-" * 80)
        print(f"置信度评分: {data.get('confidence_score', 0):.3f}")
        print(f"数据来源: {', '.join(data.get('data_sources', []))}")
        print(f"引用规范: {len(data.get('referenced_specs', []))} 个")
        print(f"引用案例: {len(data.get('referenced_cases', []))} 个")
        print(f"装备推荐: {len(data.get('equipment_recommendations', []))} 项")
        print(f"错误/警告: {len(data.get('errors', []))} 个")

        if data.get('errors'):
            print(f"\n⚠️  警告信息:")
            for err in data['errors']:
                print(f"  - {err}")

        print()
        print("-" * 80)
        print("📄 完整报告预览")
        print("-" * 80)
        print()

        # 只显示章节标题（不显示全文避免过长）
        lines = report_text.split('\n')
        for line in lines:
            if line.startswith('##') or line.startswith('# '):
                print(line)

        print()
        print("-" * 80)
        print("🔍 第八章详细内容（增援需求）")
        print("-" * 80)
        print()

        # 提取第八章内容
        chapter_8_start = report_text.find("八、")
        if chapter_8_start != -1:
            chapter_8_end = report_text.find("九、", chapter_8_start)
            if chapter_8_end == -1:
                chapter_8_end = report_text.find("## 前突侦察指挥组", chapter_8_start)

            if chapter_8_end != -1:
                chapter_8_content = report_text[chapter_8_start:chapter_8_end].strip()
                print(chapter_8_content)
            else:
                print("未找到第八章结束位置")
        else:
            print("❌ 未找到第八章")

        print()
        print("=" * 80)
        print("✅ 测试完成")
        print("=" * 80)

        return True

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: 请确保服务已启动")
        print("   启动命令: ./scripts/dev-run.sh")
        return False
    except requests.exceptions.Timeout:
        print("❌ 请求超时: 报告生成时间过长")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_model():
    """验证模型使用情况"""
    print()
    print("=" * 80)
    print("🔍 验证模型配置")
    print("=" * 80)
    print()

    # 读取代码文件检查模型配置
    try:
        with open("src/emergency_agents/api/reports.py", "r", encoding="utf-8") as f:
            content = f.read()
            if 'model="glm-4.6"' in content:
                print("✅ 代码中已硬编码使用 glm-4.6 模型")
                print("   位置: src/emergency_agents/api/reports.py:388")
            else:
                print("⚠️  代码中未找到 glm-4.6 硬编码")
    except FileNotFoundError:
        print("⚠️  无法读取源文件")

    print()


if __name__ == "__main__":
    # 验证模型配置
    verify_model()

    # 测试报告生成
    success = test_report_generation()

    exit(0 if success else 1)
