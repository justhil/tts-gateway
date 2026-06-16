import os
from pathlib import Path

ONNX_MARKER = "vits_fp32.onnx"


def has_onnx_model(model_dir: Path) -> bool:
    return resolve_onnx_dir(model_dir) is not None


def resolve_onnx_dir(model_dir: Path) -> Path | None:
    model_dir = model_dir.resolve()
    if not model_dir.is_dir():
        return None
    if (model_dir / ONNX_MARKER).is_file():
        return model_dir
    sub = model_dir / "onnx"
    if (sub / ONNX_MARKER).is_file():
        return sub
    for root, _, files in os.walk(model_dir):
        if ONNX_MARKER in files:
            return Path(root)
    return None