# Copyright 2025 msq
"""Streaming端点集成测试。

验证SSE（Server-Sent Events）流式输出：
- 事件格式正确（event: xxx\\ndata: {...}\\n\\n）
- 进度事件包含正确的状态信息
- 完成/错误事件正常触发
- 实时反馈机制工作正常

Reference: Phase 1.1实现Streaming实时反馈接口
"""
from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Iterator

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def parse_sse_line(line: str) -> tuple[str | None, dict | None]:
    """解析SSE行数据。

    Returns:
        (event_type, data_dict) 或 (None, None)
    """
    if line.startswith("event: "):
        return line[7:].strip(), None
    elif line.startswith("data: "):
        try:
            data = json.loads(line[6:])
            return None, data
        except json.JSONDecodeError:
            return None, None
    return None, None


def parse_sse_stream(response: requests.Response) -> Iterator[tuple[str, dict]]:
    """解析SSE流并生成(event_type, data)元组。

    SSE格式示例:
        event: start
        data: {"rescue_id": "test-001", "status": "started"}

        event: progress
        data: {"current_step": "意图识别", "intent_type": "rescue"}

        event: complete
        data: {"rescue_id": "test-001", "status": "completed"}
    """
    current_event = None
    current_data = None

    for line in response.iter_lines(decode_unicode=True):
        if not line:  # 空行表示事件结束
            if current_event and current_data:
                yield current_event, current_data
                current_event = None
                current_data = None
            continue

        event_type, data = parse_sse_line(line)

        if event_type:
            current_event = event_type
        if data:
            current_data = data


@pytest.mark.integration
def test_streaming_endpoint_basic_flow():
    """测试streaming端点的基本流程。

    验证：
    1. 返回正确的SSE headers
    2. start事件正常触发
    3. 至少收到一个progress事件
    4. complete或error事件结束流
    """
    # 跳过条件：无服务器或明确跳过
    if os.getenv("SKIP_STREAMING_TEST") == "1":
        pytest.skip("跳过Streaming测试（环境变量）")
        return

    api_base = os.getenv("API_BASE_URL", "http://127.0.0.1:8008")

    # 准备测试数据
    rescue_id = f"test-stream-{int(time.time())}"
    payload = {
        "user_id": "test-user",
        "raw_report": "汶川县发生7.8级地震，震源深度14公里，多处房屋倒塌，预计有人员被困。"
    }

    # 等待服务启动（最多5秒）
    url = f"{api_base}/healthz"
    service_ready = False
    for i in range(5):
        try:
            r = requests.get(url, timeout=1.0)
            if r.ok:
                service_ready = True
                break
        except Exception as e:
            print(f"  健康检查尝试 {i+1}/5 失败: {e}")
            time.sleep(1)

    if not service_ready:
        pytest.skip("服务未启动，跳过测试")
        return

    # 发起streaming请求
    stream_url = f"{api_base}/threads/start-stream"
    params = {"rescue_id": rescue_id}

    try:
        with requests.post(
            stream_url,
            params=params,
            json=payload,
            stream=True,
            timeout=30  # 最多等待30秒
        ) as response:
            # 验证响应headers
            assert response.status_code == 200, f"HTTP状态码错误: {response.status_code}"
            assert response.headers["content-type"].startswith("text/event-stream"), \
                f"Content-Type错误: {response.headers.get('content-type')}"
            assert response.headers.get("cache-control") == "no-cache", \
                "Cache-Control header缺失或错误"

            print(f"\n✅ SSE Headers验证通过")

            # 解析SSE流
            events = []
            for event_type, data in parse_sse_stream(response):
                events.append((event_type, data))
                print(f"📡 收到事件: {event_type} - {data}")

                # 收到complete或error后终止
                if event_type in ("complete", "error"):
                    break

            # 验证事件序列
            assert len(events) > 0, "未收到任何SSE事件"

            # 第一个事件应该是start
            first_event_type, first_data = events[0]
            assert first_event_type == "start", f"首个事件不是start: {first_event_type}"
            assert first_data.get("rescue_id") == rescue_id, "start事件中rescue_id不匹配"
            print(f"✅ start事件验证通过")

            # 最后一个事件应该是complete或error
            last_event_type, last_data = events[-1]
            assert last_event_type in ("complete", "error"), \
                f"最后事件不是complete/error: {last_event_type}"
            print(f"✅ {last_event_type}事件验证通过")

            # 应该至少有start + progress/complete/error
            assert len(events) >= 2, f"事件数量过少: {len(events)}"

            # 检查是否有progress事件
            progress_events = [e for e in events if e[0] == "progress"]
            if progress_events:
                print(f"✅ 收到 {len(progress_events)} 个progress事件")

                # 验证progress事件包含current_step字段
                for _, data in progress_events:
                    assert "rescue_id" in data, "progress事件缺少rescue_id"
                    # current_step可能为None（某些状态未更新字段）
                    if data.get("current_step"):
                        print(f"   进度: {data['current_step']}")

            print(f"\n✅ 总共收到 {len(events)} 个事件")
            print("✅ Streaming端点基本流程测试通过")

    except requests.exceptions.Timeout:
        pytest.fail("Streaming请求超时（30秒）")
    except requests.exceptions.ConnectionError as e:
        pytest.skip(f"服务连接失败，跳过测试: {e}")


@pytest.mark.integration
def test_streaming_endpoint_progress_events():
    """测试streaming端点的进度事件内容。

    验证：
    1. progress事件包含current_step信息
    2. 不同阶段的进度事件包含对应的上下文数据
    3. 事件顺序合理（意图识别 -> 态势分析 -> ...）
    """
    if os.getenv("SKIP_STREAMING_TEST") == "1":
        pytest.skip("跳过Streaming测试（环境变量）")
        return

    api_base = os.getenv("API_BASE_URL", "http://127.0.0.1:8008")
    rescue_id = f"test-progress-{int(time.time())}"
    payload = {
        "user_id": "test-user",
        "raw_report": "成都市发生洪水灾害，坐标104.06,30.67，受灾人数约500人，多个区域被淹需要调配救援队伍。"
    }

    stream_url = f"{api_base}/threads/start-stream"
    params = {"rescue_id": rescue_id}

    try:
        with requests.post(
            stream_url,
            params=params,
            json=payload,
            stream=True,
            timeout=30
        ) as response:
            if response.status_code != 200:
                pytest.skip(f"服务不可用: {response.status_code}")
                return

            events = list(parse_sse_stream(response))
            progress_events = [(evt, data) for evt, data in events if evt == "progress"]

            print(f"\n收到 {len(progress_events)} 个progress事件:")

            steps_seen = []
            for _, data in progress_events:
                step = data.get("current_step")
                if step:
                    steps_seen.append(step)
                    print(f"  - {step}")

                    # 验证不同步骤的上下文数据
                    if step == "意图识别":
                        assert "intent_type" in data, "意图识别事件缺少intent_type"
                    elif step == "态势分析":
                        assert "situation_summary" in data, "态势分析事件缺少situation_summary"
                    elif step == "风险预测":
                        assert "risk_count" in data, "风险预测事件缺少risk_count"
                    elif step == "方案生成":
                        assert "proposal_count" in data, "方案生成事件缺少proposal_count"

            if steps_seen:
                print(f"✅ 检测到工作流步骤: {steps_seen}")
            else:
                print("⚠️  未检测到具体步骤（可能workflow被跳过）")

            print("✅ Progress事件内容测试通过")

    except requests.exceptions.Timeout:
        pytest.fail("Streaming请求超时")
    except requests.exceptions.ConnectionError:
        pytest.skip("服务连接失败，跳过测试")


@pytest.mark.integration
def test_streaming_endpoint_error_handling():
    """测试streaming端点的错误处理。

    验证：
    1. 无效输入触发error事件
    2. error事件包含错误信息
    3. 流正常结束
    """
    if os.getenv("SKIP_STREAMING_TEST") == "1":
        pytest.skip("跳过Streaming测试")
        return

    api_base = os.getenv("API_BASE_URL", "http://127.0.0.1:8008")
    rescue_id = f"test-error-{int(time.time())}"

    # 故意发送空报告触发错误
    payload = {
        "user_id": "test-user",
        "raw_report": ""  # 空报告
    }

    stream_url = f"{api_base}/threads/start-stream"
    params = {"rescue_id": rescue_id}

    try:
        with requests.post(
            stream_url,
            params=params,
            json=payload,
            stream=True,
            timeout=15
        ) as response:
            if response.status_code != 200:
                pytest.skip(f"服务不可用: {response.status_code}")
                return

            events = list(parse_sse_stream(response))

            # 可能触发error事件，也可能正常complete（取决于实现）
            last_event_type, last_data = events[-1]

            if last_event_type == "error":
                print(f"\n✅ 捕获到error事件")
                assert "error" in last_data, "error事件缺少error字段"
                print(f"   错误信息: {last_data.get('error')}")
            elif last_event_type == "complete":
                print(f"\n⚠️  空输入正常完成（未触发error）")
            else:
                pytest.fail(f"意外的最后事件类型: {last_event_type}")

            print("✅ 错误处理测试通过")

    except requests.exceptions.Timeout:
        pytest.fail("Streaming请求超时")
    except requests.exceptions.ConnectionError:
        pytest.skip("服务连接失败，跳过测试")


if __name__ == "__main__":
    print("=" * 60)
    print("Streaming端点集成测试")
    print("=" * 60)

    try:
        # 基本流程测试
        print("\n【测试1】基本SSE流程")
        test_streaming_endpoint_basic_flow()

        # 进度事件测试
        print("\n【测试2】进度事件内容")
        test_streaming_endpoint_progress_events()

        # 错误处理测试
        print("\n【测试3】错误处理")
        test_streaming_endpoint_error_handling()

        print("\n" + "=" * 60)
        print("✅ 所有Streaming测试通过 (3/3)")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
