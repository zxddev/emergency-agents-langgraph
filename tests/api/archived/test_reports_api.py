#!/usr/bin/env python3
"""测试救援评估报告生成API"""

import requests
import json
from datetime import datetime

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
        },
        {
            "type": "滑坡",
            "risk_level": "中",
            "measures": "危险区域设置警戒"
        }
    ],
    "supplies": [
        {
            "name": "帐篷",
            "current": 500,
            "needed": 1000,
            "status": "紧缺"
        },
        {
            "name": "食品",
            "current": 2000,
            "needed": 5000,
            "status": "紧缺"
        }
    ]
}

def test_health():
    """测试健康检查端点"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)
    try:
        response = requests.get("http://localhost:8000/healthz", timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return True
    except requests.exceptions.Timeout:
        print("❌ 健康检查超时 - 服务可能在初始化中卡住")
        return False
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

def test_rescue_assessment():
    """测试救援评估报告生成"""
    print("\n" + "=" * 60)
    print("测试 2: 救援评估报告生成")
    print("=" * 60)
    try:
        print("发送请求...")
        response = requests.post(
            "http://localhost:8000/reports/rescue-assessment",
            json=test_payload,
            timeout=30  # LLM调用可能需要较长时间
        )

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("\n✅ 请求成功！")
            print(f"\n置信度评分: {result.get('confidence_score', 'N/A')}")
            print(f"数据源数量: {len(result.get('data_sources', []))}")
            print(f"引用规范数量: {len(result.get('referenced_specs', []))}")
            print(f"引用案例数量: {len(result.get('referenced_cases', []))}")
            print(f"装备推荐数量: {len(result.get('equipment_recommendations', []))}")
            print(f"错误数量: {len(result.get('errors', []))}")

            if result.get('errors'):
                print("\n⚠️ 执行中的错误:")
                for error in result['errors']:
                    print(f"  - {error}")

            print("\n数据源:")
            for source in result.get('data_sources', []):
                print(f"  - {source}")

            if result.get('equipment_recommendations'):
                print("\n装备推荐:")
                for eq in result.get('equipment_recommendations', [])[:5]:
                    print(f"  - {eq['name']}: {eq['score']:.3f} ({eq['source']})")

            print("\n关键要点:")
            for point in result.get('key_points', [])[:5]:
                print(f"  - {point}")

            print(f"\n报告文本长度: {len(result.get('report_text', ''))} 字符")
            print("\n报告预览（前300字符）:")
            print(result.get('report_text', '')[:300])

            return True
        else:
            print(f"❌ 请求失败")
            print(f"响应: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("开始测试救援评估报告生成API")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 测试1: 健康检查
    health_ok = test_health()

    if not health_ok:
        print("\n⚠️ 健康检查失败，建议检查:")
        print("  1. 服务是否正常启动")
        print("  2. 依赖服务(Neo4j/Qdrant/PostgreSQL)是否可访问")
        print("  3. 查看启动日志是否有错误")
        return

    # 测试2: 救援评估报告生成
    test_rescue_assessment()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
