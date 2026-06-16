"""对外 API：角色解析与参考音列表（基于目录索引）。"""
from typing import Any

from app.index_store import CatalogIndex, get_index


def list_characters() -> list[dict[str, Any]]:
    return get_index().characters


def list_references(character_id: str) -> list[dict[str, Any]]:
    idx = get_index()
    folder = _resolve_folder(character_id, idx)
    if not folder:
        return []
    return idx.references.get(folder, [])


def resolve_character(char_name: str) -> dict[str, Any] | None:
    idx = get_index()
    folder = _resolve_folder(char_name, idx)
    if not folder:
        return None
    c = next((x for x in idx.characters if x["folder"] == folder), None)
    if not c:
        return None
    return {
        "char_name": char_name,
        "folder": folder,
        "genie_character": c["genie_character"],
        "onnx_model_dir": c["onnx_model_dir"],
        "language": c["language"],
    }


def _resolve_folder(character_id: str, idx: CatalogIndex) -> str | None:
    mappings = idx.mappings or {}
    folder = mappings.get(character_id, character_id)
    known = {c["folder"] for c in idx.characters}
    if folder in known:
        return folder
    if character_id in known:
        return character_id
    return None