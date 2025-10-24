# Copyright 2025 msq
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Callable


def now_iso() -> str:
    """返回当前UTC时间的ISO8601字符串。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def deep_merge_non_null(base: Dict[str, Any], inc: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并：inc中的非空键覆盖或填充base；子字典递归合并。

    Args:
      base: 原始字典。
      inc: 增量字典（None值忽略，不覆盖）。

    Returns:
      合并后的新字典（不修改原始对象）。
    """
    out: Dict[str, Any] = dict(base or {})
    for k, v in (inc or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge_non_null(out[k], v)
        else:
            out[k] = v
    return out


def upsert_by_key(
    current: List[Dict[str, Any]],
    incoming: List[Dict[str, Any]],
    key: str,
    merge: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """根据key对列表做upsert；存在则合并，否则追加。

    Args:
      current: 现有列表。
      incoming: 新增或更新的列表。
      key: 用于匹配的键名（如"type"）。
      merge: 可选的合并函数，默认以incoming为准，补齐current缺失字段。

    Returns:
      合并后的列表，保序：优先保留current的次序，对应项更新。
    """
    idx = {item.get(key): i for i, item in enumerate(current or []) if item.get(key) is not None}
    out = list(current or [])

    def _merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        if merge:
            return merge(a, b)
        # 默认：以b为主，补齐a缺失字段
        res = dict(a or {})
        for k, v in (b or {}).items():
            res[k] = v if v is not None else res.get(k)
        return res

    for item in incoming or []:
        k = item.get(key)
        if k is None:
            continue
        if k in idx:
            out[idx[k]] = _merge(out[idx[k]], item)
        else:
            idx[k] = len(out)
            out.append(item)
    return out


def append_timeline(state: Dict[str, Any], event: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """向状态时间轴追加事件（不可变式返回）。"""
    tl = list(state.get("timeline") or [])
    tl.append({"time": now_iso(), "event": event, **(data or {})})
    return state | {"timeline": tl}




