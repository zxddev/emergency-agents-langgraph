#!/usr/bin/env python3
"""测试救援评估报告生成API - 完整规范数据"""

import requests
import json
from datetime import datetime

# 符合API规范的完整测试数据
test_payload = {
    "basic": {
        "disaster_type": "地震灾害",  # 必须是枚举值
        "occurrence_time": "2025-01-02T14:28:00",
        "report_time": datetime.now().isoformat(),
        "location": "四川省阿坝州汶川县映秀镇",
        "command_unit": "前突侦察指挥组",
        "frontline_overview": "震中映秀镇建筑损毁严重，道路中断，通信受阻。现场天气晴朗，但余震频繁。",
        "communication_status": "卫星通信已建立，部分地面通信恢复",
        "weather_trend": "未来24小时晴转多云，气温10-18℃"
    },
    "casualties": {
        "affected_population": 50000,
        "deaths": 100,
        "missing": 50,
        "injured": 300,
        "emergency_evacuation": 5000,
        "emergency_resettlement": 3000,
        "urgent_life_support": 8000,
        "requiring_support": 10000,
        "casualty_notes": "伤员主要为建筑倒塌所致，多为骨折和软组织挫伤"
    },
    "disruptions": {
        "road_blocked_villages": 15,
        "power_outage_villages": 20,
        "water_outage_villages": 18,
        "telecom_outage_villages": 12,
        "infrastructure_notes": "主要干道已抢通，供电和供水正在恢复中"
    },
    "infrastructure": {
        "collapsed_buildings": 500,
        "severely_damaged_buildings": 1200,
        "mildly_damaged_buildings": 3000,
        "transport_damage": "映秀至汶川主干道中断3处，已抢通1处",
        "communication_damage": "3座通信基站损毁，卫星站已架设",
        "energy_damage": "2座变电站受损，紧急供电车已到位",
        "water_facility_damage": "主供水管网破裂，应急供水点已设立",
        "public_service_damage": "县医院受损，已建立野战医疗点",
        "direct_economic_loss": 50000.0,
        "other_critical_damage": "学校、政府办公楼等公共建筑受损严重"
    },
    "agriculture": {
        "farmland_damage_area": 5000.0,
        "agricultural_facilities_damage": "大棚损毁200个，灌溉设施受损",
        "livestock_losses": "猪500头、牛30头死亡",
        "forestry_damage": "部分林地因滑坡受损",
        "aquaculture_damage": "鱼塘决堤3处"
    },
    "resources": {
        "deployed_forces": [
            {"name": "消防救援队", "count": 200, "mission": "搜救被困人员"},
            {"name": "医疗队", "count": 50, "mission": "现场医疗救治"},
            {"name": "武警部队", "count": 500, "mission": "道路抢通和物资运输"},
            {"name": "民兵", "count": 300, "mission": "安置点管理"}
        ],
        "equipment_deployed": [
            {"name": "生命探测仪", "quantity": 10, "status": "已投入使用"},
            {"name": "挖掘机", "quantity": 5, "status": "道路抢通中"},
            {"name": "医疗急救车", "quantity": 8, "status": "待命"}
        ],
        "materials_inventory": [
            {"name": "帐篷", "current": 500, "needed": 1000, "status": "紧缺"},
            {"name": "食品", "current": 2000, "needed": 5000, "status": "紧缺"},
            {"name": "饮用水", "current": 3000, "needed": 8000, "status": "紧缺"}
        ],
        "command_structure": "已建立前线指挥部，设置救援组、医疗组、物资组、通信保障组"
    },
    "support_needs": {
        "personnel_needs": "需增援医疗队50人、搜救队100人",
        "equipment_needs": "需大型挖掘机10台、生命探测仪20台",
        "material_needs": "帐篷500顶、食品10吨、饮用水20吨",
        "technical_needs": "需地质专家评估次生灾害风险",
        "transport_needs": "需直升机2架用于物资投送和伤员转运",
        "other_support": "需协调周边县市医院接收重伤员"
    },
    "risk_outlook": {
        "secondary_disasters": [
            {"type": "余震", "risk_level": "高", "measures": "实时监测，随时准备撤离"},
            {"type": "滑坡", "risk_level": "中", "measures": "危险区域设置警戒，监测山体变化"},
            {"type": "堰塞湖", "risk_level": "低", "measures": "上游河道巡查"}
        ],
        "safety_precautions": "已设置安全警戒线，配备专职安全员",
        "weather_impact": "近期天气良好，有利于救援作业",
        "other_risks": "部分建筑物随时可能倒塌，需谨慎作业"
    },
    "operations": {
        "search_rescue_progress": "已搜救300人，仍有50人被困待救",
        "medical_treatment_progress": "已救治伤员200人，重伤员15人已转运",
        "shelter_progress": "已安置3000人，临时安置点5个",
        "infrastructure_recovery": "主干道已抢通，供电恢复30%",
        "communication_recovery": "卫星通信正常，地面通信恢复50%",
        "other_progress": "应急指挥系统已建立，信息报送通畅"
    }
}

def test_rescue_assessment():
    """测试救援评估报告生成"""
    print("=" * 80)
    print("救援评估报告生成API测试")
    print("=" * 80)

    print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: http://localhost:8000/reports/rescue-assessment")

    try:
        print("\n发送请求...")
        response = requests.post(
            "http://localhost:8000/reports/rescue-assessment",
            json=test_payload,
            timeout=60  # LLM调用可能需要较长时间
        )

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            print("\n" + "=" * 80)
            print("✅ 请求成功！")
            print("=" * 80)

            # 1. 置信度评分
            print(f"\n【置信度评分】: {result.get('confidence_score', 'N/A'):.3f}")

            # 2. 数据源
            print(f"\n【数据源】({len(result.get('data_sources', []))}):")
            for i, source in enumerate(result.get('data_sources', []), 1):
                print(f"  {i}. {source}")

            # 3. 引用规范
            print(f"\n【引用规范文档】({len(result.get('referenced_specs', []))}):")
            for i, spec in enumerate(result.get('referenced_specs', []), 1):
                print(f"  {i}. {spec}")

            # 4. 引用案例
            print(f"\n【引用历史案例】({len(result.get('referenced_cases', []))}):")
            for i, case in enumerate(result.get('referenced_cases', []), 1):
                print(f"  {i}. {case}")

            # 5. 装备推荐
            print(f"\n【装备推荐】({len(result.get('equipment_recommendations', []))}):")
            for i, eq in enumerate(result.get('equipment_recommendations', []), 1):
                print(f"  {i}. {eq['name']}: {eq['score']:.3f} (来源: {eq['source']})")

            # 6. 错误信息
            if result.get('errors'):
                print(f"\n【执行错误】({len(result['errors'])}):")
                for i, error in enumerate(result['errors'], 1):
                    print(f"  {i}. ⚠️ {error}")
            else:
                print("\n【执行错误】: 无")

            # 7. 关键要点
            print(f"\n【关键要点】({len(result.get('key_points', []))}):")
            for i, point in enumerate(result.get('key_points', [])[:10], 1):
                print(f"  {i}. {point}")

            # 8. 报告统计
            report_text = result.get('report_text', '')
            print(f"\n【报告统计】:")
            print(f"  - 总字符数: {len(report_text)}")
            print(f"  - 总行数: {len(report_text.splitlines())}")

            # 9. 报告预览
            print(f"\n{'=' * 80}")
            print("【完整报告内容】")
            print("=" * 80)
            print(report_text)

            # 10. 总结
            print("\n" + "=" * 80)
            print("测试总结")
            print("=" * 80)
            print(f"✅ API调用成功")
            print(f"✅ 置信度评分: {result.get('confidence_score', 0):.3f}")
            print(f"✅ 数据源数量: {len(result.get('data_sources', []))}")
            print(f"✅ 外部数据支持: 规范{len(result.get('referenced_specs', []))}项 + 案例{len(result.get('referenced_cases', []))}项 + 装备{len(result.get('equipment_recommendations', []))}项")
            print(f"✅ 报告长度: {len(report_text)} 字符")

            if result.get('errors'):
                print(f"⚠️ 有{len(result['errors'])}个警告")

            return True

        else:
            print(f"\n❌ 请求失败 (状态码: {response.status_code})")
            print(f"响应内容: {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        print("❌ 请求超时（60秒）")
        return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rescue_assessment()
    exit(0 if success else 1)
