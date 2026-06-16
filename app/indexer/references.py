import os
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.indexer.prompt import resolve_prompt_text

AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac", ".aiff", ".aif"}


def _iter_audio_files(refs_dir: Path):
    if not refs_dir.is_dir():
        return
    for entry in sorted(refs_dir.iterdir()):
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXT:
            yield entry
    for sub in (
        refs_dir / "emotions",
        refs_dir / "Chinese" / "emotions",
        refs_dir / "中文" / "emotions",
        refs_dir / "zh" / "emotions",
    ):
        if sub.is_dir():
            for entry in sorted(sub.iterdir()):
                if entry.is_file() and entry.suffix.lower() in AUDIO_EXT:
                    yield entry


def scan_references_for_folder(folder: str) -> list[dict[str, Any]]:
    refs_dir = get_settings().refs_root / folder
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for wav in _iter_audio_files(refs_dir):
        try:
            real = wav.resolve()
        except OSError:
            continue
        key = str(real).casefold()
        if key in seen:
            continue
        seen.add(key)
        prompt, emotion, psrc = resolve_prompt_text(real)
        rel = os.path.relpath(real, refs_dir).replace("\\", "/")
        items.append(
            {
                "id": rel,
                "filename": wav.name,
                "emotion": emotion,
                "path": str(real),
                "prompt_text": prompt,
                "prompt_source": psrc,
                "language": "zh",
            }
        )
    items.sort(key=lambda x: (x["emotion"], x["id"]))
    return items