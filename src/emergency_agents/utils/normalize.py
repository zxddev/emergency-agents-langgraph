# Copyright 2025 msq
from __future__ import annotations

from typing import Optional


_DISASTER_ALIAS = {
    # Chinese -> canonical
    "地震": "earthquake",
    "洪水": "flood",
    "山体滑坡": "landslide",
    "滑坡": "landslide",
    "化工泄漏": "chemical_leak",
    "化学泄漏": "chemical_leak",
    "化学泄露": "chemical_leak",
    "化工泄露": "chemical_leak",
    "火灾": "fire",
    # English canonical passthrough
    "earthquake": "earthquake",
    "flood": "flood",
    "landslide": "landslide",
    "chemical_leak": "chemical_leak",
    "fire": "fire",
}


def normalize_disaster_name(name: Optional[str]) -> Optional[str]:
    """标准化灾害名称为知识图谱中的规范枚举。

    Args:
      name: 原始灾害名称（中英文皆可）。

    Returns:
      规范英文名（如 "earthquake"），未知时返回原值或None。
    """
    if not name:
        return name
    key = str(name).strip().lower()
    # 原始字典包含中文键，这里双查：原样与小写
    return _DISASTER_ALIAS.get(name) or _DISASTER_ALIAS.get(key) or name


