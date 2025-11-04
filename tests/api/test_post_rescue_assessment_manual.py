#!/usr/bin/env python3
"""手动测试救援评估报告API（事后总结）

Usage:
    python tests/api/test_post_rescue_assessment_manual.py [--minimal|--complete]
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

import httpx

# 测试配置
API_BASE_URL = "http://localhost:8008"
TIMEOUT = 120.0  # 增加超时时间,因为LLM调用可能较慢


def load_fixture(fixture_name: str) -> Dict[str, Any]:
    """加载测试数据fixture"""
    fixture_path = Path(__file__).parent.parent / "fixtures" / fixture_name
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_section(title: str, content: str = ""):
    """打印章节"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)
    if content:
        print(content)


def test_minimal_input():
    """测试最小输入数据"""
    print_section("测试1: 最小输入数据")

    payload = load_fixture("post_rescue_assessment_minimal_input.json")
    print(f"\n📥 输入数据概要:")
    print(f"  - 灾害: {payload['disaster_overview']['disaster_name']}")
    print(f"  - 响应级别: {payload['response_activation']['response_level']}")
    print(f"  - 救援人数: {payload['rescue_statistics']['total_rescued']}")

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_BASE_URL}/reports/post-rescue-assessment",
                json=payload
            )
            response.raise_for_status()
            result = response.json()

        print_section("✅ 测试通过", f"HTTP {response.status_code}")

        # 打印关键指标
        print_section("📊 计算的关键指标")
        for key, value in result["key_metrics"].items():
            print(f"  - {key}: {value}")

        # 打印置信度
        print_section("🎯 置信度评分")
        print(f"  - 综合得分: {result['confidence_score']:.2f}")

        # 打印报告前50行
        print_section("📄 生成的报告（前50行）")
        report_lines = result["report_text"].split("\n")
        for i, line in enumerate(report_lines[:50], 1):
            print(f"{i:3d}: {line}")

        if len(report_lines) > 50:
            print(f"\n... (共 {len(report_lines)} 行，只显示前50行)")

        # 打印数据源
        print_section("📚 数据来源")
        print(f"  - 参考规范: {len(result['data_sources']['referenced_specs'])} 个")
        print(f"  - 历史案例: {len(result['data_sources']['referenced_cases'])} 个")

        return True

    except httpx.HTTPStatusError as e:
        print_section("❌ HTTP错误", f"状态码: {e.response.status_code}")
        print(f"错误响应: {e.response.text}")
        return False
    except httpx.TimeoutException:
        print_section("❌ 超时错误", f"请求超过 {TIMEOUT} 秒")
        return False
    except Exception as e:
        print_section("❌ 未知错误", str(e))
        import traceback
        traceback.print_exc()
        return False


def test_complete_input():
    """测试完整输入数据（雅安地震案例）"""
    print_section("测试2: 完整输入数据（雅安7.0级地震）")

    payload = load_fixture("post_rescue_assessment_complete_input.json")
    print(f"\n📥 输入数据概要:")
    print(f"  - 灾害: {payload['disaster_overview']['disaster_name']}")
    print(f"  - 响应级别: {payload['response_activation']['response_level']}")
    print(f"  - 时间线事件: {len(payload['timeline'])} 个")
    print(f"  - 投入力量: {len(payload['forces_deployed'])} 支")
    print(f"  - 救援人数: {payload['rescue_statistics']['total_rescued']}")
    print(f"  - 最终伤亡: {payload['disaster_overview']['final_deaths']}死 {payload['disaster_overview']['final_injured']}伤")

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_BASE_URL}/reports/post-rescue-assessment",
                json=payload
            )
            response.raise_for_status()
            result = response.json()

        print_section("✅ 测试通过", f"HTTP {response.status_code}")

        # 打印关键指标
        print_section("📊 计算的关键指标")
        for key, value in result["key_metrics"].items():
            print(f"  - {key}: {value}")

        # 打印置信度
        print_section("🎯 置信度评分")
        print(f"  - 综合得分: {result['confidence_score']:.2f}")

        # 打印完整性评分
        if "completeness" in result["key_metrics"]:
            print(f"  - 数据完整性: {result['key_metrics']['completeness']:.2%}")

        # 打印报告前100行（完整案例可能更长）
        print_section("📄 生成的报告（前100行）")
        report_lines = result["report_text"].split("\n")
        for i, line in enumerate(report_lines[:100], 1):
            print(f"{i:3d}: {line}")

        if len(report_lines) > 100:
            print(f"\n... (共 {len(report_lines)} 行，只显示前100行)")

        # 打印数据源详情
        print_section("📚 数据来源详情")
        print(f"  参考规范 ({len(result['data_sources']['referenced_specs'])} 个):")
        for spec in result['data_sources']['referenced_specs'][:3]:
            print(f"    - {spec}")

        print(f"\n  历史案例 ({len(result['data_sources']['referenced_cases'])} 个):")
        for case in result['data_sources']['referenced_cases'][:3]:
            print(f"    - {case}")

        return True

    except httpx.HTTPStatusError as e:
        print_section("❌ HTTP错误", f"状态码: {e.response.status_code}")
        print(f"错误响应: {e.response.text}")
        return False
    except httpx.TimeoutException:
        print_section("❌ 超时错误", f"请求超过 {TIMEOUT} 秒")
        return False
    except Exception as e:
        print_section("❌ 未知错误", str(e))
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print_section("🧪 救援评估报告API测试", "POST /reports/post-rescue-assessment")

    # 检查服务是否运行
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{API_BASE_URL}/healthz")
            response.raise_for_status()
            print("\n✅ API服务运行正常")
    except Exception as e:
        print(f"\n❌ 无法连接到API服务: {e}")
        print(f"请确保服务已启动: ./scripts/dev-run.sh")
        sys.exit(1)

    # 解析命令行参数
    test_mode = "both"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--minimal", "-m"]:
            test_mode = "minimal"
        elif arg in ["--complete", "-c"]:
            test_mode = "complete"

    # 运行测试
    results = []

    if test_mode in ["both", "minimal"]:
        results.append(("最小输入", test_minimal_input()))

    if test_mode in ["both", "complete"]:
        results.append(("完整输入", test_complete_input()))

    # 打印总结
    print_section("📋 测试总结")
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  - {name}: {status}")

    all_passed = all(success for _, success in results)
    print(f"\n总体结果: {'✅ 全部通过' if all_passed else '❌ 有失败'}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
