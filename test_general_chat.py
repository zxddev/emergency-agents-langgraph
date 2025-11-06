#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试通用对话功能。

测试场景：
1. 问候："你好"
2. 自我介绍询问："你是什么大模型"
3. 能力询问："你能做什么"
4. 测试语句："测试一下"
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from emergency_agents.config import AppConfig
from emergency_agents.llm.client import get_openai_client
from emergency_agents.intent.handlers.general_chat import GeneralChatHandler


async def test_general_chat():
    """测试通用对话功能。"""
    print("=" * 80)
    print("测试通用对话Handler")
    print("=" * 80)

    # 加载配置
    cfg = AppConfig.load_from_env()
    llm_client = get_openai_client(cfg)
    llm_model = cfg.llm_model

    # 创建Handler
    handler = GeneralChatHandler(llm_client, llm_model)

    # 测试用例
    test_cases = [
        {"text": "你好", "description": "问候"},
        {"text": "你是什么大模型", "description": "自我介绍询问"},
        {"text": "你能做什么", "description": "能力询问"},
        {"text": "测试一下", "description": "测试语句"},
        {"text": "在吗", "description": "简单问候"},
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试用例 {i}/{len(test_cases)}: {case['description']}")
        print(f"{'='*80}")
        print(f"用户输入: {case['text']}")
        print("-" * 80)

        # 构造payload
        payload = {
            "intent": {"raw_text": case["text"]},
            "raw_text": case["text"],
            "history": [],
        }

        # 调用Handler
        try:
            result = await handler.handle(payload)
            print(f"✅ 成功")
            print(f"回答:\n{result['answer']}")
            print(f"\n置信度: {result['confidence']}")
            print(f"来源: {result['source']}")
        except Exception as e:
            print(f"❌ 失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}")
    print("测试完成")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(test_general_chat())
