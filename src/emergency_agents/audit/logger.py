# Copyright 2025 msq
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """审计日志条目
    
    记录系统中的每个关键决策和动作
    
    Reference: 
        - docs/行动计划/ACTION-PLAN-DAY1.md (Day 11-12)
        - specs/08-CHANGES-REQUIRED.md lines 73-163
    """
    timestamp: str
    rescue_id: str
    user_id: str
    action: str
    actor: str
    data: Dict[str, Any]
    reversible: bool
    thread_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    error: Optional[str] = None


class AuditLogger:
    """审计日志系统
    
    提供结构化的审计日志记录能力，支持：
    - AI决策记录
    - 人工审批记录
    - 状态转换记录
    - 执行结果记录
    - 决策回溯查询
    
    设计原则：
    1. 只追加，不修改（append-only）
    2. 结构化存储（JSON格式）
    3. 关键字段索引（rescue_id, timestamp, action）
    4. 支持分布式追踪（thread_id, checkpoint_id）
    """
    
    def __init__(self):
        self._entries: List[AuditEntry] = []
    
    def log(
        self,
        *,
        rescue_id: str,
        user_id: str,
        action: str,
        actor: str,
        data: Dict[str, Any],
        reversible: bool = True,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """记录审计日志
        
        Args:
            rescue_id: 救援任务ID
            user_id: 用户ID
            action: 动作类型（如"ai_situation_analysis", "human_approval"）
            actor: 执行者（如"situation_agent", "user:admin"）
            data: 动作相关数据（如决策结果、审批意见）
            reversible: 是否可逆（不可逆动作需要特别标记）
            thread_id: LangGraph线程ID
            checkpoint_id: Checkpoint ID
            error: 错误信息（如果有）
        """
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            rescue_id=rescue_id,
            user_id=user_id,
            action=action,
            actor=actor,
            data=data,
            reversible=reversible,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            error=error
        )
        
        self._entries.append(entry)
        
        logger.info(
            f"[AUDIT] {action} by {actor} for rescue={rescue_id}",
            extra={
                "audit_entry": asdict(entry),
                "rescue_id": rescue_id,
                "action": action,
                "actor": actor
            }
        )
    
    def get_trail(self, rescue_id: str) -> List[Dict[str, Any]]:
        """获取特定救援任务的审计轨迹
        
        Args:
            rescue_id: 救援任务ID
        
        Returns:
            审计日志列表，按时间排序
        """
        entries = [
            asdict(entry) 
            for entry in self._entries 
            if entry.rescue_id == rescue_id
        ]
        return sorted(entries, key=lambda x: x["timestamp"])
    
    def get_by_actor(self, actor: str) -> List[Dict[str, Any]]:
        """获取特定执行者的所有动作
        
        Args:
            actor: 执行者标识
        
        Returns:
            审计日志列表
        """
        entries = [
            asdict(entry) 
            for entry in self._entries 
            if entry.actor == actor
        ]
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)
    
    def get_irreversible_actions(self) -> List[Dict[str, Any]]:
        """获取所有不可逆动作
        
        Returns:
            不可逆动作列表
        """
        entries = [
            asdict(entry) 
            for entry in self._entries 
            if not entry.reversible
        ]
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)
    
    def export_json(self, rescue_id: Optional[str] = None) -> str:
        """导出审计日志为JSON
        
        Args:
            rescue_id: 如果指定，只导出该救援任务的日志
        
        Returns:
            JSON字符串
        """
        if rescue_id:
            entries = self.get_trail(rescue_id)
        else:
            entries = [asdict(e) for e in self._entries]
        
        return json.dumps(entries, ensure_ascii=False, indent=2)


_global_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    return _global_audit_logger


def log_ai_decision(
    rescue_id: str,
    user_id: str,
    agent_name: str,
    decision_type: str,
    decision_data: Dict[str, Any],
    thread_id: Optional[str] = None
) -> None:
    """记录AI决策
    
    Args:
        rescue_id: 救援任务ID
        user_id: 用户ID
        agent_name: 智能体名称
        decision_type: 决策类型（如"situation_analysis", "risk_prediction"）
        decision_data: 决策结果数据
        thread_id: 线程ID
    """
    _global_audit_logger.log(
        rescue_id=rescue_id,
        user_id=user_id,
        action=f"ai_{decision_type}",
        actor=f"agent:{agent_name}",
        data=decision_data,
        reversible=True,
        thread_id=thread_id
    )


def log_human_approval(
    rescue_id: str,
    user_id: str,
    approved_ids: List[str],
    comment: Optional[str] = None,
    thread_id: Optional[str] = None
) -> None:
    """记录人工审批
    
    Args:
        rescue_id: 救援任务ID
        user_id: 用户ID
        approved_ids: 批准的提案ID列表
        comment: 审批意见
        thread_id: 线程ID
    """
    _global_audit_logger.log(
        rescue_id=rescue_id,
        user_id=user_id,
        action="human_approval",
        actor=f"user:{user_id}",
        data={
            "approved_ids": approved_ids,
            "comment": comment,
            "count": len(approved_ids)
        },
        reversible=False,
        thread_id=thread_id
    )


def log_execution(
    rescue_id: str,
    user_id: str,
    action_id: str,
    action_type: str,
    result: Dict[str, Any],
    success: bool,
    thread_id: Optional[str] = None
) -> None:
    """记录执行结果
    
    Args:
        rescue_id: 救援任务ID
        user_id: 用户ID
        action_id: 动作ID
        action_type: 动作类型
        result: 执行结果
        success: 是否成功
        thread_id: 线程ID
    """
    _global_audit_logger.log(
        rescue_id=rescue_id,
        user_id=user_id,
        action=f"execute_{action_type}",
        actor="system:executor",
        data={
            "action_id": action_id,
            "result": result,
            "success": success
        },
        reversible=False,
        thread_id=thread_id,
        error=None if success else result.get("error")
    )

