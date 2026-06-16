import os
import re
from typing import Any

from app.config import get_settings
from app.indexer.onnx import has_onnx_model, resolve_onnx_dir
from app.indexer.references import scan_references_for_folder
from app.storage.json_store import load_optional_json


def default_genie_character_id(folder: str) -> str:
    ascii_fold = folder.encode("ascii", "ignore").decode("ascii").strip()
    if ascii_fold:
        slug = re.sub(r"[^a-z0-9_-]+", "_", ascii_fold.lower()).strip("_")
        return slug or ascii_fold
    return folder


def scan_characters() -> list[dict[str, Any]]:
    s = get_settings()
    overrides = load_optional_json(s.data_dir / s.character_models_file)
    root = s.characters_root
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for name in sorted(os.listdir(root)):
        path = root / name
        if not path.is_dir() or not has_onnx_model(path):
            continue
        ov = overrides.get(name, {})
        if not isinstance(ov, dict):
            ov = {}
        onnx = resolve_onnx_dir(path)
        onnx_dir = ov.get("onnx_model_dir") or (str(onnx) if onnx else "")
        refs = scan_references_for_folder(name)
        out.append(
            {
                "id": name,
                "folder": name,
                "genie_character": ov.get("genie_character") or default_genie_character_id(name),
                "onnx_model_dir": onnx_dir,
                "language": ov.get("language", "zh"),
                "reference_count": len(refs),
                "source": "scan",
            }
        )
    return out