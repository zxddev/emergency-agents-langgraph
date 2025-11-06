#!/usr/bin/env python
"""测试system-data-query实际效果

模拟语音识别后的查询处理流程。
"""

import asyncio
import json
from datetime import datetime

from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
from emergency_agents.intent.classifier import intent_classifier_node


async def test_classify():
    """测试意图分类"""

    # 初始化配置
    cfg = AppConfig.load_from_env()
    llm_client = get_openai_client(cfg)
    llm_model = cfg.llm_model or "glm-4-flash"

    # 测试用例
    test_cases = [
        "查看所有携带设备",
        "显示所有车载设备",
        "查询无人机A的状态",
        "查看任务TASK-001的进度",
        "火灾现场的位置在哪里",
    ]

    print("=" * 60)
    print("测试意图分类器对system-data-query的识别")
    print("=" * 60)

    for text in test_cases:
        print(f"\n输入: {text}")

        # 模拟state
        state = {
            "raw_text": text,
            "thread_id": f"test-{datetime.now().timestamp()}",
            "user_id": "test_user"
        }

        # 分类
        result = intent_classifier_node(state, llm_client, llm_model)

        intent = result.get("intent", {})
        intent_type = intent.get("intent_type")
        slots = intent.get("slots", {})
        meta = intent.get("meta", {})

        print(f"意图: {intent_type}")
        print(f"置信度: {meta.get('confidence', 0):.2f}")
        print(f"槽位: {json.dumps(slots, ensure_ascii=False, indent=2)}")

        # 检查是否正确识别为system-data-query
        if "设备" in text or "携带" in text:
            if intent_type in ["system_data_query", "system-data-query"]:
                print("✅ 正确识别为系统数据查询")
                # 检查query_type是否正确
                query_type = slots.get("query_type")
                if "所有" in text and query_type == "carried_devices":
                    print("✅ 正确识别为查询所有携带设备")
                elif "无人机" in text and query_type == "device_by_name":
                    print("✅ 正确识别为按名称查询设备")
            else:
                print(f"❌ 错误：应该识别为system-data-query，实际为{intent_type}")


async def test_full_flow():
    """测试完整流程（包括Handler）"""
    from psycopg_pool import AsyncConnectionPool
    from psycopg.rows import dict_row
    from emergency_agents.db.dao import DeviceDAO
    from emergency_agents.intent.handlers.system_data_query import SystemDataQueryHandler
    from emergency_agents.intent.schemas import SystemDataQuerySlots

    # 初始化配置
    cfg = AppConfig.load_from_env()

    # 创建数据库连接池
    pool = AsyncConnectionPool(
        cfg.postgres_dsn,
        min_size=1,
        max_size=5,
        kwargs={"row_factory": dict_row}
    )

    # 创建DAO
    device_dao = DeviceDAO(pool)

    # 创建Handler（只使用device_dao，其他用None）
    handler = SystemDataQueryHandler(
        device_dao=device_dao,
        task_dao=None,
        event_dao=None,
        poi_dao=None,
        rescuer_dao=None
    )

    print("\n" + "=" * 60)
    print("测试完整流程：查询所有携带设备")
    print("=" * 60)

    # 创建槽位
    slots = SystemDataQuerySlots(
        query_type="carried_devices"
    )

    # 模拟state
    state = {
        "thread_id": "test-full-flow",
        "user_id": "test_user"
    }

    try:
        # 执行查询
        result = await handler.handle(slots, state)

        print(f"\n响应文本：\n{result.get('response_text')}")
        print(f"\n查询结果：")
        query_result = result.get("query_result")
        if query_result:
            for device in query_result:
                print(f"  - {device['name']}: {device['weather_capability']}")
        else:
            print("  无数据")
        print(f"\n耗时: {result.get('elapsed_ms')}ms")

    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        await pool.close()


async def main():
    """主函数"""
    # 测试意图分类
    await test_classify()

    # 测试完整流程
    print("\n是否测试数据库查询？(需要数据库连接)")
    choice = input("输入 y 继续，其他键跳过: ")
    if choice.lower() == 'y':
        await test_full_flow()


if __name__ == "__main__":
    asyncio.run(main())