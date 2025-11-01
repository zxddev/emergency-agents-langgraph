#!/usr/bin/env python3
# Copyright 2025 msq
"""ASR服务使用示例。

演示如何使用ASR服务进行语音识别，包括：
1. 基本识别
2. 健康检查
3. 查看Provider状态
4. 自动降级演示
"""

import asyncio
import os
import sys

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
sys.path.insert(0, os.path.join(project_root, "src"))

from emergency_agents.voice.asr.service import ASRService
from emergency_agents.voice.asr.base import ASRConfig


async def example_basic_usage():
    """示例1：基本使用。"""
    print("\n" + "=" * 60)
    print("示例1：基本使用")
    print("=" * 60)

    # 创建ASR服务
    asr_service = ASRService()
    print(f"✓ ASR服务已创建，主Provider: {asr_service.provider_name}")

    # 创建测试音频（1秒静音）
    # 在实际应用中，这应该是从麦克风或文件读取的真实音频数据
    audio_data = b"\x00" * (16000 * 2)  # 16000 Hz * 1秒 * 2字节（16-bit）
    print(f"✓ 测试音频大小: {len(audio_data)} 字节")

    try:
        # 执行识别
        print("→ 开始识别...")
        result = await asr_service.recognize(audio_data)

        print(f"✓ 识别成功:")
        print(f"  - 文本: {result.text}")
        print(f"  - Provider: {result.provider}")
        print(f"  - 延迟: {result.latency_ms}ms")
        print(f"  - 置信度: {result.confidence}")

    except Exception as e:
        print(f"✗ 识别失败: {e}")


async def example_with_config():
    """示例2：使用自定义配置。"""
    print("\n" + "=" * 60)
    print("示例2：使用自定义配置")
    print("=" * 60)

    asr_service = ASRService()

    # 自定义配置
    config = ASRConfig(
        format="pcm",
        sample_rate=16000,
        channels=1,
        language="zh-CN",
        enable_punctuation=True,
    )
    print("✓ 自定义配置:")
    print(f"  - 格式: {config.format}")
    print(f"  - 采样率: {config.sample_rate}")
    print(f"  - 声道: {config.channels}")
    print(f"  - 语言: {config.language}")

    audio_data = b"\x00" * (16000 * 2)

    try:
        result = await asr_service.recognize(audio_data, config)
        print(f"✓ 识别成功，使用Provider: {result.provider}")
    except Exception as e:
        print(f"✗ 识别失败: {e}")


async def example_health_check():
    """示例3：健康检查。"""
    print("\n" + "=" * 60)
    print("示例3：健康检查")
    print("=" * 60)

    asr_service = ASRService()

    # 启动健康检查
    print("→ 启动健康检查...")
    await asr_service.start_health_check()
    print("✓ 健康检查已启动（后台任务）")

    # 等待几秒让健康检查执行
    print("→ 等待3秒...")
    await asyncio.sleep(3)

    # 查看Provider状态
    status = asr_service.provider_status
    print("✓ Provider健康状态:")
    for provider_name, is_healthy in status.items():
        status_str = "✓ 健康" if is_healthy else "✗ 不健康"
        print(f"  - {provider_name}: {status_str}")

    # 停止健康检查
    print("→ 停止健康检查...")
    await asr_service.stop_health_check()
    print("✓ 健康检查已停止")


async def example_failover_simulation():
    """示例4：模拟故障转移（需要配置环境）。"""
    print("\n" + "=" * 60)
    print("示例4：故障转移模拟")
    print("=" * 60)

    print("提示：此示例需要正确配置环境变量:")
    print("  - DASHSCOPE_API_KEY（阿里云）")
    print("  - VOICE_ASR_WS_URL（本地FunASR）")
    print()

    asr_service = ASRService()

    # 启动健康检查
    await asr_service.start_health_check()
    print("✓ 健康检查已启动")

    # 等待健康检查完成一次
    await asyncio.sleep(3)

    # 查看初始状态
    status = asr_service.provider_status
    print("✓ 初始Provider状态:")
    for provider_name, is_healthy in status.items():
        print(f"  - {provider_name}: {'健康' if is_healthy else '不健康'}")

    # 执行识别（会自动选择健康的Provider）
    audio_data = b"\x00" * (16000 * 2)

    try:
        print("\n→ 执行识别...")
        result = await asr_service.recognize(audio_data)
        print(f"✓ 识别成功:")
        print(f"  - 使用Provider: {result.provider}")
        print(f"  - 延迟: {result.latency_ms}ms")
    except Exception as e:
        print(f"✗ 识别失败: {e}")
        print("  提示：请检查环境配置和服务状态")

    # 停止健康检查
    await asr_service.stop_health_check()
    print("\n✓ 健康检查已停止")


async def main():
    """主函数。"""
    print("\n" + "=" * 60)
    print("ASR服务使用示例")
    print("=" * 60)
    print()
    print("注意：这些示例使用测试音频（静音），实际识别结果可能为空。")
    print("      在生产环境中，请使用真实的音频数据。")
    print()

    try:
        # 示例1：基本使用
        await example_basic_usage()

        # 示例2：自定义配置
        await example_with_config()

        # 示例3：健康检查
        await example_health_check()

        # 示例4：故障转移（需要环境配置）
        await example_failover_simulation()

        print("\n" + "=" * 60)
        print("✓ 所有示例执行完成！")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n✗ 用户中断")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())


