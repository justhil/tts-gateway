"""按目录 mtime 缓存角色/参考音索引，支持手动刷新。"""
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings


@dataclass
class CatalogIndex:
    characters: list[dict[str, Any]] = field(default_factory=list)
    references: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    mappings: dict[str, str] = field(default_factory=dict)
    built_at: float = 0.0
    sources_mtime: float = 0.0


_index: CatalogIndex | None = None


def _dir_latest_mtime(root: Path) -> float:
    if not root.is_dir():
        return 0.0
    latest = root.stat().st_mtime
    for dirpath, _, filenames in os.walk(root):
        try:
            latest = max(latest, Path(dirpath).stat().st_mtime)
        except OSError:
            pass
        for fn in filenames:
            try:
                latest = max(latest, (Path(dirpath) / fn).stat().st_mtime)
            except OSError:
                pass
    return latest


def _sources_mtime() -> float:
    s = get_settings()
    m = [
        _dir_latest_mtime(s.characters_root),
        _dir_latest_mtime(s.refs_root),
    ]
    for rel in (s.character_models_file, s.character_mappings_file):
        p = s.data_dir / rel
        if p.is_file():
            try:
                m.append(p.stat().st_mtime)
            except OSError:
                pass
    return max(m) if m else 0.0


def invalidate_index() -> None:
    global _index
    _index = None


def get_index(*, force_rebuild: bool = False) -> CatalogIndex:
    global _index
    sm = _sources_mtime()
    if (
        not force_rebuild
        and _index is not None
        and _index.sources_mtime >= sm
        and sm > 0
    ):
        return _index
    from app.catalog import build_catalog_index

    _index = build_catalog_index()
    _index.sources_mtime = sm
    _index.built_at = time.time()
    return _index