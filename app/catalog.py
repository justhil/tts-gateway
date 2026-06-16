import json
import os
import re
from pathlib import Path
from typing import Any

from app.catalog_cache import CatalogIndex
from app.config import get_settings

AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac"}


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _has_onnx(model_dir: Path) -> bool:
    if not model_dir.is_dir():
        return False
    if (model_dir / "vits_fp32.onnx").is_file():
        return True
    if (model_dir / "onnx" / "vits_fp32.onnx").is_file():
        return True
    for root, _, files in os.walk(model_dir):
        if "vits_fp32.onnx" in files:
            return True
    return False


def resolve_onnx_dir(model_dir: Path) -> Path:
    model_dir = model_dir.resolve()
    if (model_dir / "vits_fp32.onnx").is_file():
        return model_dir
    sub = model_dir / "onnx"
    if (sub / "vits_fp32.onnx").is_file():
        return sub
    for root, _, files in os.walk(model_dir):
        if "vits_fp32.onnx" in files:
            return Path(root)
    return model_dir


def _prompt_text_for_wav(wav: Path) -> str:
    txt = wav.with_suffix(".txt")
    if txt.is_file():
        return txt.read_text(encoding="utf-8", errors="replace").strip()[:500]
    stem = wav.stem
    if "_" in stem:
        return stem.split("_", 1)[1][:500]
    return stem[:500]


def _emotion_from_name(filename: str) -> str:
    stem = Path(filename).stem
    if "_" in stem:
        return stem.split("_")[0].lower()
    return "default"


def _default_genie_name(folder: str) -> str:
    """Genie API 常用小写 id；无覆盖时用文件夹名规范化。"""
    return re.sub(r"[^a-z0-9_-]+", "_", folder.lower()).strip("_") or folder


def _scan_references_for_folder(folder: str) -> list[dict[str, Any]]:
    s = get_settings()
    refs_dir = s.refs_root / folder
    if not refs_dir.is_dir():
        return []
    items = []
    for fn in sorted(os.listdir(refs_dir)):
        if Path(fn).suffix.lower() not in AUDIO_EXT:
            continue
        wav = refs_dir / fn
        if not wav.is_file():
            continue
        real = wav.resolve()
        items.append(
            {
                "id": fn,
                "emotion": _emotion_from_name(fn),
                "path": str(real),
                "prompt_text": _prompt_text_for_wav(real),
                "language": "zh",
            }
        )
    return items


def build_catalog_index() -> CatalogIndex:
    """仅扫描 CHARACTERS_ROOT / REFS_ROOT；JSON 只做可选覆盖。"""
    s = get_settings()
    overrides = _load_json(s.data_dir / s.character_models_file)
    mappings = _load_json(s.data_dir / s.character_mappings_file)

    characters: list[dict[str, Any]] = []
    references: dict[str, list[dict[str, Any]]] = {}

    root = s.characters_root
    if root.is_dir():
        for name in sorted(os.listdir(root)):
            path = root / name
            if not path.is_dir() or not _has_onnx(path):
                continue
            ov = overrides.get(name, {})
            onnx_dir = ov.get("onnx_model_dir") or str(resolve_onnx_dir(path))
            characters.append(
                {
                    "id": name,
                    "folder": name,
                    "genie_character": ov.get("genie_character") or _default_genie_name(name),
                    "onnx_model_dir": onnx_dir,
                    "language": ov.get("language", "zh"),
                    "source": "scan",
                }
            )
            references[name] = _scan_references_for_folder(name)

    return CatalogIndex(characters=characters, references=references, mappings=mappings)


def _get_mappings(idx: CatalogIndex) -> dict:
    return idx.mappings or {}


def list_characters() -> list[dict[str, Any]]:
    from app.catalog_cache import get_index

    return get_index().characters


def list_references(character_id: str) -> list[dict[str, Any]]:
    from app.catalog_cache import get_index

    idx = get_index()
    folder = _folder_for_id(character_id, idx)
    if not folder:
        return []
    return idx.references.get(folder, _scan_references_for_folder(folder))


def _folder_for_id(character_id: str, idx: CatalogIndex) -> str | None:
    mappings = _get_mappings(idx)
    folder = mappings.get(character_id, character_id)
    known = {c["folder"] for c in idx.characters}
    if folder in known:
        return folder
    if character_id in known:
        return character_id
    return None


def resolve_character(char_name: str) -> dict[str, Any] | None:
    from app.catalog_cache import get_index

    idx = get_index()
    folder = _folder_for_id(char_name, idx)
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