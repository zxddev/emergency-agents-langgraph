from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import structlog

logger = structlog.get_logger(__name__)


def _normalize_token(text: str) -> str:
    """返回名称的规范化形式，统一去空格并转小写。"""
    return re.sub(r"\s+", "", text or "").strip().lower()


@dataclass(frozen=True, slots=True)
class VideoStreamEntry:
    """视频流目录条目，描述单台设备的基础信息。"""

    device_id: str
    display_name: str
    stream_url: str
    device_type: str | None
    aliases: Tuple[str, ...]

    def tokens(self) -> Tuple[str, ...]:
        """给出匹配用的所有规范化名称。"""
        base_tokens: List[str] = []
        base_tokens.append(_normalize_token(self.device_id))
        base_tokens.append(_normalize_token(self.display_name))
        for alias in self.aliases:
            base_tokens.append(_normalize_token(alias))
        unique = [token for token in base_tokens if token]
        seen: set[str] = set()
        filtered: List[str] = []
        for token in unique:
            if token in seen:
                continue
            seen.add(token)
            filtered.append(token)
        return tuple(filtered)

    def to_candidate(self) -> Dict[str, str]:
        """转换为候选列表项，供前端展示与澄清。"""
        return {
            "device_id": self.device_id,
            "label": self.display_name or self.device_id,
            "device_type": self.device_type or "",
        }


class VideoStreamCatalog:
    """视频流目录，替代数据库查询提供设备解析。"""

    def __init__(self, entries: Sequence[VideoStreamEntry]) -> None:
        if not entries:
            logger.warning("video_stream_catalog_empty")
        self._entries: Tuple[VideoStreamEntry, ...] = tuple(entries)
        self._index_by_id: Dict[str, VideoStreamEntry] = {
            entry.device_id: entry for entry in self._entries
        }
        token_map: Dict[str, List[VideoStreamEntry]] = {}
        for entry in self._entries:
            for token in entry.tokens():
                token_map.setdefault(token, []).append(entry)
        self._token_map = {token: tuple(items) for token, items in token_map.items()}

    @classmethod
    def from_raw_mapping(cls, raw: Mapping[str, object]) -> "VideoStreamCatalog":
        """根据配置构建目录，兼容纯字符串与结构化配置。"""
        entries: List[VideoStreamEntry] = []
        for raw_id, raw_value in raw.items():
            device_id = str(raw_id).strip()
            if not device_id:
                continue
            display_name: str = device_id
            device_type: str | None = None
            stream_url: str | None = None
            aliases: Tuple[str, ...] = ()

            if isinstance(raw_value, str):
                stream_url = raw_value.strip()
            elif isinstance(raw_value, Mapping):
                stream_candidate = raw_value.get("stream_url")
                if isinstance(stream_candidate, str):
                    stream_url = stream_candidate.strip()
                name_candidate = raw_value.get("display_name")
                if isinstance(name_candidate, str) and name_candidate.strip():
                    display_name = name_candidate.strip()
                type_candidate = raw_value.get("device_type")
                if isinstance(type_candidate, str) and type_candidate.strip():
                    device_type = type_candidate.strip()
                alias_raw = raw_value.get("aliases")
                if isinstance(alias_raw, (list, tuple)):
                    normalized_aliases: List[str] = []
                    for alias in alias_raw:
                        if isinstance(alias, str) and alias.strip():
                            normalized_aliases.append(alias.strip())
                    aliases = tuple(normalized_aliases)
            else:
                stream_url = str(raw_value).strip()

            if not stream_url:
                logger.warning(
                    "video_stream_missing_url",
                    device_id=device_id,
                    raw_value=raw_value,
                )
                stream_url = ""
            entries.append(
                VideoStreamEntry(
                    device_id=device_id,
                    display_name=display_name,
                    stream_url=stream_url,
                    device_type=device_type,
                    aliases=aliases,
                )
            )
        return cls(entries)

    def resolve(
        self,
        name: str,
        *,
        device_type: str | None = None,
    ) -> Tuple[VideoStreamEntry, ...]:
        """按名称解析目录，支持ID、展示名与别名匹配。"""
        normalized = _normalize_token(name)
        if not normalized:
            return ()
        candidates = self._token_map.get(normalized, ())
        if device_type is None or not candidates:
            return candidates
        normalized_type = device_type.strip().lower()
        filtered = tuple(
            entry
            for entry in candidates
            if entry.device_type is None or entry.device_type.lower() == normalized_type
        )
        if filtered:
            return filtered
        return ()

    def auto_select(self, *, device_type: str | None = None) -> VideoStreamEntry | None:
        """目录中只有一个匹配设备时直接返回，减少多轮追问。"""
        if device_type:
            normalized = device_type.strip().lower()
            filtered = [
                entry
                for entry in self._entries
                if entry.device_type and entry.device_type.strip().lower() == normalized
            ]
            if len(filtered) == 1:
                return filtered[0]
        if len(self._entries) == 1:
            return self._entries[0]
        return None

    def list_candidates(self) -> Tuple[Dict[str, str], ...]:
        """列出可用设备候选。"""
        return tuple(entry.to_candidate() for entry in self._entries)

    def list_display_names(self) -> Tuple[str, ...]:
        """返回所有可用设备名称，方便向用户展示。"""
        return tuple(entry.display_name or entry.device_id for entry in self._entries)

    def list_device_types(self) -> Tuple[str, ...]:
        """返回目录覆盖的设备类型集合。"""
        types = {
            entry.device_type.strip().lower()
            for entry in self._entries
            if entry.device_type and entry.device_type.strip()
        }
        return tuple(sorted(types))

    def get(self, device_id: str) -> VideoStreamEntry | None:
        """按ID直接获取条目。"""
        return self._index_by_id.get(device_id)

    def __iter__(self) -> Iterable[VideoStreamEntry]:
        return iter(self._entries)
