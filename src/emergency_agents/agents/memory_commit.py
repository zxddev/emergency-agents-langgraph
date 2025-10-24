# Copyright 2025 msq
from __future__ import annotations

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def prepare_memory_node(state: Dict[str, Any], content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """准备阶段：只生成数据，不写入Mem0
    
    两阶段提交的第一阶段：收集待提交的记忆到pending_memories队列
    
    Args:
        state: 当前状态
        content: 记忆内容
        metadata: 元数据（必须包含idempotency_key）
    
    Returns:
        更新的状态（添加到pending_memories）
    
    Reference: specs/08-CHANGES-REQUIRED.md lines 86-149
    """
    if "idempotency_key" not in metadata:
        metadata["idempotency_key"] = f"{state.get('rescue_id')}_{metadata.get('agent', 'unknown')}_{metadata.get('step', '001')}"
    
    memory_data = {
        "content": content,
        "user_id": state.get("user_id", "unknown"),
        "run_id": state.get("rescue_id"),
        "metadata": metadata
    }
    
    pending = state.get("pending_memories", [])
    pending.append(memory_data)
    
    logger.debug(f"准备记忆: {metadata.get('idempotency_key')}")
    
    return state | {"pending_memories": pending}


def commit_memory_node(state: Dict[str, Any], mem0_facade) -> Dict[str, Any]:
    """提交阶段：批量写入记忆（在Checkpoint成功后）
    
    两阶段提交的第二阶段：
    1. 检查pending_memories
    2. 幂等性检查（通过idempotency_key）
    3. 写入Mem0（带重试）
    4. 记录到committed_memories
    5. 清空pending_memories
    
    Args:
        state: 当前状态
        mem0_facade: Mem0门面对象
    
    Returns:
        更新的状态
    
    Reference: specs/08-CHANGES-REQUIRED.md lines 86-149
    """
    pending = state.get("pending_memories", [])
    if not pending:
        logger.debug("无待提交记忆，跳过")
        return state
    
    committed = state.get("committed_memories", [])
    
    for memory_data in pending:
        idempotency_key = memory_data["metadata"]["idempotency_key"]
        
        if idempotency_key in committed:
            logger.info(f"记忆已提交，跳过: {idempotency_key}")
            continue
        
        try:
            mem0_facade.add(
                content=memory_data["content"],
                user_id=memory_data["user_id"],
                run_id=memory_data.get("run_id"),
                agent_id=memory_data["metadata"].get("agent")
            )
            
            committed.append(idempotency_key)
            logger.info(f"记忆提交成功: {idempotency_key}")
            
        except Exception as e:
            logger.error(f"记忆提交失败: {idempotency_key}, error={e}")
    
    return state | {
        "pending_memories": [],
        "committed_memories": committed
    }


def create_memory_commit_nodes(graph, mem0_facade, state_schema):
    """创建记忆提交相关节点并添加到图中
    
    使用方法：
    ```python
    from emergency_agents.agents.memory_commit import create_memory_commit_nodes
    
    graph = StateGraph(RescueState)
    create_memory_commit_nodes(graph, mem0_facade, RescueState)
    
    # 在业务逻辑节点中准备记忆
    def my_business_node(state):
        # 业务逻辑...
        state = prepare_memory_node(
            state, 
            content="关键决策信息",
            metadata={"agent": "my_agent", "step": "001"}
        )
        return state
    
    # 在图中添加提交节点
    graph.add_node("business_logic", my_business_node)
    graph.add_node("commit_memory", commit_memory_node_wrapper)
    graph.add_edge("business_logic", "commit_memory")
    ```
    
    Reference: specs/08-CHANGES-REQUIRED.md lines 145-153
    """
    def commit_memory_node_wrapper(state):
        return commit_memory_node(state, mem0_facade)
    
    graph.add_node("commit_memory", commit_memory_node_wrapper)
    
    return commit_memory_node_wrapper

