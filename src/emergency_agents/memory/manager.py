# Copyright 2025 msq
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MemoryRecord:
    user_id: str
    run_id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime


class AuditedMemoryManager:
    """内存型审计记忆管理器（原型阶段）。

    本类提供最小的 add/search 能力，便于在未接通外部存储前完成流程联调。
    生产阶段应替换为 Mem0 封装，以获得向量与图记忆能力。
    """

    def __init__(self) -> None:
        self._store: List[MemoryRecord] = []

    def add(self, *, user_id: str, run_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """写入一条记忆记录（仅内存）。

        Args:
            user_id: 租户标识，强制隔离维度。
            run_id: 会话标识（与 rescue_id 对齐）。
            content: 记忆内容。
            metadata: 附加元信息，可选。
        """
        record = MemoryRecord(
            user_id=user_id,
            run_id=run_id,
            content=content,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        # audit log hook can be added here
        self._store.append(record)

    def search(self, *, user_id: str, run_id: Optional[str] = None, query: Optional[str] = None) -> List[MemoryRecord]:
        """按多租户维度检索内存记录。

        Args:
            user_id: 租户标识，强制过滤。
            run_id: 会话标识，可选。
            query: 关键字匹配内容，可选。

        Returns:
            匹配到的内存记录列表。
        """
        results: List[MemoryRecord] = []
        for rec in self._store:
            if rec.user_id != user_id:
                continue
            if run_id is not None and rec.run_id != run_id:
                continue
            if query and query not in rec.content:
                continue
            results.append(rec)
        return results
