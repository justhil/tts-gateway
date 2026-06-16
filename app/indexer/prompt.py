from pathlib import Path

EMOTION_PREFIXES = frozenset(
    {
        "angry",
        "arousal",
        "climax",
        "happy",
        "sad",
        "surprise",
        "scare",
        "hate",
        "calm",
        "default",
    }
)


def emotion_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    if "_" not in stem:
        return "default"
    prefix = stem.split("_", 1)[0].lower()
    return prefix if prefix in EMOTION_PREFIXES else "default"


def read_sidecar_text(audio_path: Path) -> str | None:
    for ext in (".txt", ".text"):
        p = audio_path.with_suffix(ext)
        if p.is_file():
            raw = p.read_text(encoding="utf-8", errors="replace").strip()
            if raw:
                return raw[:500]
    return None


def prompt_from_filename_stem(stem: str) -> str | None:
    if "_" in stem:
        tail = stem.split("_", 1)[1].strip()
        return tail[:500] if tail else None
    s = stem.strip()
    return s[:500] if s else None


def resolve_prompt_text(audio_path: Path) -> tuple[str, str, str]:
    path = audio_path.resolve()
    emotion = emotion_from_filename(path.name)
    sidecar = read_sidecar_text(path)
    if sidecar:
        return sidecar, emotion, "sidecar"
    from_name = prompt_from_filename_stem(path.stem)
    if from_name:
        return from_name, emotion, "filename"
    return path.stem[:500], emotion, "stem"