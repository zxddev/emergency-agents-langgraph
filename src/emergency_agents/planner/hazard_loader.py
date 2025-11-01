from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional

import jsonschema

from .models import HazardPack


class HazardPackLoader:
    """灾种知识包加载器。"""

    def __init__(
        self,
        base_path: Path | None = None,
        *,
        schema_path: Path | None = None,
        cache_ttl: float = 300.0,
    ) -> None:
        self._base_path = base_path or Path(__file__).resolve().parent.parent / "knowledge" / "hazard_packs"
        self._schema_path = schema_path or self._base_path / "schemas" / "hazard_pack_schema.json"
        self._cache_ttl = cache_ttl
        self._last_manifest_reload = 0.0
        self._manifest: Dict[str, Dict[str, str]] = {}
        self._schema = self._load_schema(self._schema_path)

    @staticmethod
    def _load_schema(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _load_manifest(self) -> None:
        manifest_path = self._base_path / "version_manifest.json"
        with manifest_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        packs = raw.get("packs") or {}
        normalized: Dict[str, Dict[str, str]] = {}
        for hazard, info in packs.items():
            current_version = info.get("current_version") or info.get("latest_stable")
            versions = info.get("versions") or []
            latest_file = None
            for item in versions:
                version = item.get("version")
                file_name = item.get("file")
                if version and file_name:
                    normalized.setdefault(hazard, {})
                    normalized[hazard][version] = file_name
                    if version == current_version:
                        latest_file = file_name
            if hazard not in normalized:
                continue
            if current_version and latest_file:
                normalized[hazard]["__current__"] = current_version
        self._manifest = normalized
        self._last_manifest_reload = time.monotonic()

    def _ensure_manifest(self) -> None:
        now = time.monotonic()
        if not self._manifest or now - self._last_manifest_reload > self._cache_ttl:
            self._load_manifest()

    def get_available_hazards(self) -> Iterable[str]:
        self._ensure_manifest()
        return list(self._manifest.keys())

    def _resolve_file(self, hazard_type: str, version: Optional[str]) -> tuple[str, Path]:
        self._ensure_manifest()
        mapping = self._manifest.get(hazard_type)
        if not mapping:
            raise KeyError(f"hazard pack not found: {hazard_type}")
        chosen_version = version
        if chosen_version is None:
            chosen_version = mapping.get("__current__")
            if chosen_version is None:
                raise KeyError(f"hazard pack missing current version: {hazard_type}")
        file_name = mapping.get(chosen_version)
        if not file_name:
            raise KeyError(f"hazard pack version not found: {hazard_type} v{chosen_version}")
        file_path = self._base_path / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"hazard pack file missing: {file_path}")
        return chosen_version, file_path

    @lru_cache(maxsize=32)
    def load_pack(self, hazard_type: str, version: Optional[str] = None) -> HazardPack:
        """加载指定灾种知识包。"""

        resolved_version, file_path = self._resolve_file(hazard_type, version)
        with file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        jsonschema.validate(instance=data, schema=self._schema)
        pack = HazardPack.model_validate(data)
        if pack.version != resolved_version:
            raise ValueError(
                f"hazard pack version mismatch: manifest={resolved_version}, payload={pack.version}"
            )
        return pack

    def invalidate_cache(self) -> None:
        """失效缓存，便于热更新知识包。"""

        self._last_manifest_reload = 0.0
        self._manifest.clear()
        self.load_pack.cache_clear()  # type: ignore[attr-defined]
