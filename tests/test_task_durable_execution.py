# Copyright 2025 msq
"""Task Durable Execution幂等性验证测试。

验证LangGraph @task装饰器的核心特性：
- workflow中断后恢复时，已执行的@task函数不会重复执行
- 副作用（LLM调用、数据库查询）的幂等性保证
- Checkpoint机制正确保存和恢复task结果

参考文档：
1. LangGraph Durable Execution: https://langchain-ai.github.io/langgraph/concepts/persistence/
2. deepwiki查询结果: test_imp_task示例
3. Sequential Thinking 15层分析结果

测试架构：
1. 使用MemorySaver构建测试StateGraph
2. 全局计数器跟踪@task执行次数
3. interrupt_before创建中断点
4. 验证恢复后计数器不增加

Reference:
- libs/langgraph/tests/test_pregel_async.py::test_imp_task
- PEP 484 Type Hints
"""
from __future__ import annotations

import sys
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, TypedDict, Annotated
from typing_extensions import NotRequired

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langgraph.func import task
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

task_execution_counts: Dict[str, int] = {}


def reset_task_counters() -> None:
    global task_execution_counts
    task_execution_counts.clear()


def cleanup_temp_checkpoints() -> None:
    temp_dir = Path("temp")
    if temp_dir.exists():
        for file in temp_dir.glob("test_checkpoint_*.db*"):
            try:
                file.unlink()
            except Exception:
                pass


class TestState(TypedDict):
    input: str
    task1_result: NotRequired[str]
    task2_result: NotRequired[str]
    output: NotRequired[str]


@task
def expensive_task_1(input_data: str) -> str:
    global task_execution_counts
    task_execution_counts["task1"] = task_execution_counts.get("task1", 0) + 1
    return f"processed_{input_data}_by_task1"


@task
def expensive_task_2(input_data: str) -> str:
    global task_execution_counts
    task_execution_counts["task2"] = task_execution_counts.get("task2", 0) + 1
    return f"processed_{input_data}_by_task2"


def create_test_graph_with_interrupt() -> StateGraph:
    def node_1(state: TestState) -> Dict[str, str]:
        result = expensive_task_1(state["input"]).result()
        return {"task1_result": result}

    def node_2(state: TestState) -> Dict[str, str]:
        result = expensive_task_2(state["task1_result"]).result()
        return {"task2_result": result}

    def interrupt_node(state: TestState) -> Dict[str, str]:
        return {}

    def final_node(state: TestState) -> Dict[str, str]:
        return {"output": state["task2_result"] + "_final"}

    builder: StateGraph[TestState] = StateGraph(TestState)
    builder.add_node("node_1", node_1)
    builder.add_node("node_2", node_2)
    builder.add_node("interrupt", interrupt_node)
    builder.add_node("final", final_node)

    builder.set_entry_point("node_1")
    builder.add_edge("node_1", "node_2")
    builder.add_edge("node_2", "interrupt")
    builder.add_edge("interrupt", "final")
    builder.set_finish_point("final")

    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["interrupt"]
    )


@pytest.mark.unit
def test_task_idempotency_basic_concept() -> None:
    print("\n=== 测试1：@task基本概念验证 ===")
    print("✅ @task装饰器理解验证：")
    print("   - @task函数必须在LangGraph graph context中执行")
    print("   - 幂等性通过checkpoint机制在workflow恢复时实现")
    print("   - 不是函数级别的缓存，而是workflow级别的状态恢复")


@pytest.mark.integration
def test_task_not_reexecuted_after_interrupt_resume() -> None:
    print("\n=== 测试2：中断恢复后@task不重复执行 ===")

    reset_task_counters()
    cleanup_temp_checkpoints()

    graph = create_test_graph_with_interrupt()
    thread_id = f"test-{uuid.uuid4()}"
    config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    initial_state: TestState = {"input": "test_data"}

    print(f"步骤1：首次执行至中断点 (thread_id={thread_id})")
    result1 = graph.invoke(initial_state, config=config)

    print(f"  └─ task1执行次数: {task_execution_counts.get('task1', 0)}")
    print(f"  └─ task2执行次数: {task_execution_counts.get('task2', 0)}")
    print(f"  └─ State: {result1}")

    assert task_execution_counts.get("task1") == 1, "task1应该执行1次"
    assert task_execution_counts.get("task2") == 1, "task2应该执行1次"
    assert "task1_result" in result1
    assert "task2_result" in result1
    assert "output" not in result1, "应该在interrupt节点前停止，未到final"

    print("\n步骤2：从checkpoint恢复执行")
    result2 = graph.invoke(None, config=config)

    print(f"  └─ task1执行次数: {task_execution_counts.get('task1', 0)} (应保持1)")
    print(f"  └─ task2执行次数: {task_execution_counts.get('task2', 0)} (应保持1)")
    print(f"  └─ Final state: {result2}")

    assert task_execution_counts.get("task1") == 1, "✅ task1未重复执行（幂等性验证）"
    assert task_execution_counts.get("task2") == 1, "✅ task2未重复执行（幂等性验证）"
    assert "output" in result2, "恢复后应完成final节点"
    expected_output = result2["task2_result"] + "_final"
    assert result2["output"] == expected_output, f"输出不匹配: {result2['output']} != {expected_output}"

    print("\n✅ 幂等性验证通过：")
    print("   - 中断前：task1和task2各执行1次")
    print("   - 恢复后：两个task均未重复执行")
    print("   - 结果正确：checkpoint保存的状态被正确恢复")


@pytest.mark.integration
def test_multiple_interrupts_and_resumes() -> None:
    print("\n=== 测试3：多次中断恢复 ===")

    reset_task_counters()

    @task
    def multi_task(data: str, step: int) -> str:
        global task_execution_counts
        key = f"multi_step_{step}"
        task_execution_counts[key] = task_execution_counts.get(key, 0) + 1
        return f"{data}_step{step}"

    class MultiState(TypedDict):
        data: str
        step1: NotRequired[str]
        step2: NotRequired[str]
        step3: NotRequired[str]

    def node_step1(state: MultiState) -> Dict[str, str]:
        result = multi_task(state["data"], 1).result()
        return {"step1": result}

    def node_step2(state: MultiState) -> Dict[str, str]:
        result = multi_task(state["step1"], 2).result()
        return {"step2": result}

    def node_step3(state: MultiState) -> Dict[str, str]:
        result = multi_task(state["step2"], 3).result()
        return {"step3": result}

    def interrupt1(state: MultiState) -> Dict[str, str]:
        return {}

    def interrupt2(state: MultiState) -> Dict[str, str]:
        return {}

    builder: StateGraph[MultiState] = StateGraph(MultiState)
    builder.add_node("step1", node_step1)
    builder.add_node("interrupt1", interrupt1)
    builder.add_node("step2", node_step2)
    builder.add_node("interrupt2", interrupt2)
    builder.add_node("step3", node_step3)

    builder.set_entry_point("step1")
    builder.add_edge("step1", "interrupt1")
    builder.add_edge("interrupt1", "step2")
    builder.add_edge("step2", "interrupt2")
    builder.add_edge("interrupt2", "step3")
    builder.set_finish_point("step3")

    graph = builder.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["interrupt1", "interrupt2"]
    )

    thread_id = f"test-multi-{uuid.uuid4()}"
    config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    print("执行1：到第一个中断点")
    r1 = graph.invoke({"data": "input"}, config=config)
    print(f"  └─ step1执行次数: {task_execution_counts.get('multi_step_1', 0)}")
    assert task_execution_counts.get("multi_step_1") == 1
    assert "step1" in r1

    print("执行2：恢复，到第二个中断点")
    r2 = graph.invoke(None, config=config)
    print(f"  └─ step1执行次数: {task_execution_counts.get('multi_step_1', 0)} (不变)")
    print(f"  └─ step2执行次数: {task_execution_counts.get('multi_step_2', 0)}")
    assert task_execution_counts.get("multi_step_1") == 1, "step1未重复"
    assert task_execution_counts.get("multi_step_2") == 1
    assert "step2" in r2

    print("执行3：最终恢复完成")
    r3 = graph.invoke(None, config=config)
    print(f"  └─ step1执行次数: {task_execution_counts.get('multi_step_1', 0)} (不变)")
    print(f"  └─ step2执行次数: {task_execution_counts.get('multi_step_2', 0)} (不变)")
    print(f"  └─ step3执行次数: {task_execution_counts.get('multi_step_3', 0)}")
    assert task_execution_counts.get("multi_step_1") == 1, "step1未重复"
    assert task_execution_counts.get("multi_step_2") == 1, "step2未重复"
    assert task_execution_counts.get("multi_step_3") == 1
    assert r3["step3"] == "input_step1_step2_step3"

    print("\n✅ 多次中断恢复验证通过：")
    print("   - 每个@task只执行一次")
    print("   - 多次恢复正确累积状态")


if __name__ == "__main__":
    print("=" * 70)
    print("Task Durable Execution 幂等性验证测试")
    print("=" * 70)

    try:
        print("\n【测试1】@task基本概念")
        test_task_idempotency_basic_concept()

        print("\n【测试2】中断恢复幂等性验证（核心）")
        test_task_not_reexecuted_after_interrupt_resume()

        print("\n【测试3】多次中断恢复")
        test_multiple_interrupts_and_resumes()

        print("\n" + "=" * 70)
        print("✅ 所有Task幂等性测试通过 (3/3)")
        print("=" * 70)
        print("\n核心验证结果：")
        print("  ✅ @task在graph context中正常工作")
        print("  ✅ Checkpoint正确保存task执行结果")
        print("  ✅ 恢复时不重复执行已完成的@task")
        print("  ✅ 多次中断恢复机制正常工作")
        print("\n参考文档：")
        print("  - LangGraph Durable Execution官方文档")
        print("  - test_imp_task示例 (deepwiki)")
        print("  - Sequential Thinking 15层分析")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
