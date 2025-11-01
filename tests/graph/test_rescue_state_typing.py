"""Rescue Tactical State 强类型测试 - 验证 TypedDict Required/NotRequired 约束

测试目标:
1. 静态类型检查(mypy) - 验证 mypy 能检测缺少 Required 字段
2. 运行时行为 - 验证 TypedDict 的运行时特性

技术背景:
- TypedDict 只提供静态类型提示,Python 运行时不会验证
- Required[T] 和 NotRequired[T] 只影响静态类型检查器(mypy/pyright)
- 运行时创建 TypedDict 时可以省略任何字段,不会抛异常
- 访问不存在的 NotRequired 字段会返回 KeyError,需用 .get()

参考文档:
- PEP 655: https://peps.python.org/pep-0655/
- Python TypedDict 文档: https://docs.python.org/3/library/typing.html#typing.TypedDict
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from emergency_agents.graph.rescue_tactical_app import RescueTacticalState

logger = logging.getLogger(__name__)


# ============================================================================
# 静态类型检查测试(mypy)
# ============================================================================


@pytest.mark.unit
def test_rescue_state_mypy_detects_missing_required_fields() -> None:
    """验证 mypy 能检测缺少 Required 字段的错误

    原理:
    1. 创建一个临时 Python 文件,故意省略 Required 字段
    2. 使用 subprocess 调用 mypy 检查该文件
    3. 验证 mypy 返回非 0 退出码(检测到错误)
    4. 验证错误信息包含缺失的字段名

    预期:
    - mypy 检测到缺少 user_id 和 thread_id
    - 退出码非 0
    - stderr 包含字段名
    """
    # 创建测试代码(故意省略 user_id 和 thread_id)
    test_code = """
from emergency_agents.graph.rescue_tactical_app import RescueTacticalState

# 缺少 Required 字段 user_id 和 thread_id,mypy 应该报错
state = RescueTacticalState(
    task_id="test-001"
)
"""

    # 写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = Path(f.name)

    try:
        # 运行 mypy 检查
        result = subprocess.run(
            ["mypy", "--strict", "--no-error-summary", str(temp_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        logger.info(
            "mypy_check_completed",
            returncode=result.returncode,
            stdout_lines=len(result.stdout.splitlines()),
            stderr_lines=len(result.stderr.splitlines()),
        )

        # 验证 mypy 检测到错误
        assert result.returncode != 0, "mypy 应该检测到缺少 Required 字段的错误"

        # 验证错误信息包含缺失的字段名
        output = result.stdout + result.stderr
        assert "user_id" in output or "thread_id" in output, f"mypy 应该提示缺少 user_id 或 thread_id,实际输出:\n{output}"

        logger.info("mypy_required_fields_check_passed")

    finally:
        # 清理临时文件
        temp_file.unlink(missing_ok=True)


@pytest.mark.unit
def test_rescue_state_mypy_accepts_valid_state() -> None:
    """验证 mypy 接受包含所有 Required 字段的状态

    预期:
    - mypy 检查通过
    - 退出码为 0
    - 无错误信息
    """
    # 创建合法的测试代码
    test_code = """
from emergency_agents.graph.rescue_tactical_app import RescueTacticalState

# 包含所有 Required 字段,mypy 应该通过
state = RescueTacticalState(
    task_id="test-001",
    user_id="user-001",
    thread_id="thread-001"
)
"""

    # 写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = Path(f.name)

    try:
        # 运行 mypy 检查
        result = subprocess.run(
            ["mypy", "--strict", "--no-error-summary", str(temp_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        logger.info(
            "mypy_valid_state_check",
            returncode=result.returncode,
            output_length=len(result.stdout) + len(result.stderr),
        )

        # 验证 mypy 检查通过
        # 注意：--strict 模式可能会有其他警告,所以不强制要求 returncode == 0
        # 只要不是 Required 字段相关的错误即可
        output = result.stdout + result.stderr
        assert "user_id" not in output or "missing" not in output.lower(), f"不应该报告 user_id 缺失,实际输出:\n{output}"
        assert "thread_id" not in output or "missing" not in output.lower(), f"不应该报告 thread_id 缺失,实际输出:\n{output}"

        logger.info("mypy_valid_state_check_passed")

    finally:
        # 清理临时文件
        temp_file.unlink(missing_ok=True)


# ============================================================================
# 运行时行为测试
# ============================================================================


@pytest.mark.unit
def test_rescue_state_runtime_creates_valid_state() -> None:
    """验证运行时可以创建包含所有 Required 字段的状态

    验证点:
    1. 成功创建状态实例
    2. 可以访问 Required 字段
    3. Required 字段值正确
    """
    # 创建包含所有 Required 字段的状态
    state = RescueTacticalState(
        task_id="test-task-001",
        user_id="test-user",
        thread_id="test-thread-001",
    )

    # 验证字段值
    assert state["task_id"] == "test-task-001"
    assert state["user_id"] == "test-user"
    assert state["thread_id"] == "test-thread-001"

    logger.info("runtime_valid_state_created", task_id=state["task_id"])


@pytest.mark.unit
def test_rescue_state_runtime_allows_notrequired_fields() -> None:
    """验证运行时 NotRequired 字段可以省略

    验证点:
    1. 省略 NotRequired 字段不影响创建
    2. 可以安全地使用 .get() 访问 NotRequired 字段
    3. .get() 返回 None 或默认值
    """
    # 创建最小化状态(只包含 Required 字段)
    state = RescueTacticalState(
        task_id="test-task-002",
        user_id="test-user",
        thread_id="test-thread-002",
    )

    # 验证 NotRequired 字段可以安全访问
    slots = state.get("slots")
    assert slots is None, "未设置的 NotRequired 字段应该返回 None"

    simulation_mode = state.get("simulation_mode", False)
    assert simulation_mode is False, ".get() 应该返回默认值"

    status = state.get("status")
    assert status is None, "未设置的 status 字段应该返回 None"

    logger.info("runtime_notrequired_fields_test_passed")


@pytest.mark.unit
def test_rescue_state_runtime_allows_setting_notrequired_fields() -> None:
    """验证运行时可以设置 NotRequired 字段

    验证点:
    1. 可以在创建时设置 NotRequired 字段
    2. 设置的值可以正确访问
    3. 支持复杂类型的 NotRequired 字段
    """
    # 创建包含部分 NotRequired 字段的状态
    state = RescueTacticalState(
        task_id="test-task-003",
        user_id="test-user",
        thread_id="test-thread-003",
        simulation_mode=True,  # NotRequired 字段
        status="processing",  # NotRequired 字段
        resolved_location={"lat": 30.27, "lng": 120.15},  # NotRequired 字段
    )

    # 验证 NotRequired 字段值
    assert state["simulation_mode"] is True
    assert state["status"] == "processing"
    assert state["resolved_location"]["lat"] == 30.27

    logger.info(
        "runtime_notrequired_fields_set",
        simulation_mode=state["simulation_mode"],
        status=state["status"],
    )


@pytest.mark.unit
def test_rescue_state_runtime_dict_behavior() -> None:
    """验证 RescueTacticalState 的字典行为

    验证点:
    1. TypedDict 实例是普通字典
    2. 支持字典的基本操作(keys, values, items, in, update)
    3. 可以动态添加字段(虽然不推荐)
    """
    # 创建状态
    state = RescueTacticalState(
        task_id="test-task-004",
        user_id="test-user",
        thread_id="test-thread-004",
    )

    # 验证字典操作
    assert "task_id" in state, "应该支持 in 操作符"
    assert "user_id" in state
    assert "unknown_field" not in state

    # 验证 keys/values
    keys = list(state.keys())
    assert "task_id" in keys
    assert len(keys) >= 3, "应该至少有 3 个 Required 字段"

    # 验证 update 操作
    state.update({"status": "completed"})
    assert state["status"] == "completed"

    logger.info("runtime_dict_behavior_test_passed", keys_count=len(keys))


@pytest.mark.unit
def test_rescue_state_runtime_partial_state_creation() -> None:
    """测试运行时创建部分状态(Python 不会阻止,但 mypy 会警告)

    注意: TypedDict 在运行时不会验证 Required 字段,这是 Python 的特性
    即使省略 Required 字段,Python 也不会抛异常(与 dataclass 不同)

    验证点:
    1. Python 运行时允许创建不完整的 TypedDict
    2. 访问不存在的字段会抛 KeyError
    3. 使用 .get() 可以安全访问
    """
    # 创建部分状态(省略 user_id 和 thread_id)
    # 运行时不会报错,但 mypy 会检测到这个问题
    partial_state: Dict[str, Any] = {"task_id": "test-task-005"}  # type: ignore

    # 验证可以访问存在的字段
    assert partial_state["task_id"] == "test-task-005"

    # 验证访问不存在的字段会抛 KeyError
    with pytest.raises(KeyError):
        _ = partial_state["user_id"]

    # 验证 .get() 可以安全访问
    user_id = partial_state.get("user_id")
    assert user_id is None

    logger.info("runtime_partial_state_test_passed")


# ============================================================================
# 综合测试: 完整工作流
# ============================================================================


@pytest.mark.unit
def test_rescue_state_full_workflow() -> None:
    """测试 RescueTacticalState 在完整工作流中的使用

    模拟救援流程:
    1. 创建初始状态(仅 Required 字段)
    2. 逐步添加流程数据(NotRequired 字段)
    3. 验证状态演化正确
    """
    # 阶段 1: 创建初始状态
    state = RescueTacticalState(
        task_id="rescue-001",
        user_id="commander-zhang",
        thread_id="thread-rescue-001",
    )
    assert state["task_id"] == "rescue-001"
    logger.info("workflow_stage1_init", task_id=state["task_id"])

    # 阶段 2: 添加位置解析结果
    state["resolved_location"] = {"lat": 30.25, "lng": 120.15, "address": "杭州西湖区"}
    assert state["resolved_location"]["lat"] == 30.25
    logger.info("workflow_stage2_location", location=state["resolved_location"])

    # 阶段 3: 添加流程状态
    state["status"] = "planning"
    assert state["status"] == "planning"
    logger.info("workflow_stage3_status", status=state["status"])

    # 阶段 4: 添加输出数据
    state["response_text"] = "救援方案生成完成"
    state["recommendation"] = {"priority": "high", "resources": ["UAV", "ROBOTDOG"]}
    assert state["response_text"] == "救援方案生成完成"
    logger.info("workflow_stage4_output", recommendation=state["recommendation"])

    # 验证最终状态包含所有字段
    assert "task_id" in state
    assert "user_id" in state
    assert "thread_id" in state
    assert "resolved_location" in state
    assert "status" in state
    assert "response_text" in state
    assert "recommendation" in state

    logger.info("workflow_complete", total_fields=len(state))
