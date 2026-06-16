"""目录索引缓存（mtime 驱动 + 手动 refresh）。"""
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


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _tree_mtime(root: Path) -> float:
    if not root.is_dir():
        return 0.0
    latest = _path_mtime(root)
    for dirpath, _, filenames in os.walk(root):
        latest = max(latest, _path_mtime(Path(dirpath)))
        for fn in filenames:
            latest = max(latest, _path_mtime(Path(dirpath) / fn))
    return latest


def compute_sources_mtime() -> float:
    s = get_settings()
    parts = [
        _tree_mtime(s.characters_root),
        _tree_mtime(s.refs_root),
        _path_mtime(s.data_dir / s.character_models_file),
        _path_mtime(s.data_dir / s.character_mappings_file),
    ]
    return max(parts)


def invalidate_index() -> None:
    global _index
    _index = None


def get_index(*, force_rebuild: bool = False) -> CatalogIndex:
    global _index
    sm = compute_sources_mtime()
    if not force_rebuild and _index is not None and _index.sources_mtime >= sm and sm > 0:
        return _index
    from app.index_builder import build_index

    _index = build_index()
    _index.sources_mtime = sm
    _index.built_at = time.time()
    return _index