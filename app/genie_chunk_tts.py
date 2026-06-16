"""长文按标点/省略号拆段合成再拼 WAV（不用 Genie split_sentence）。"""
import io
import re
import wave
from typing import List

from app.genie_client import GenieClient, pcm_to_wav

CHUNK_THRESHOLD = 50
MAX_CHUNK = 36

_SPLIT_RE = re.compile(r"(?<=[。！？；\n])|(?<=[，、])|(?<=……)|(?<=…)")


def _normalize_ellipsis(text: str) -> str:
    return re.sub(r"……+", "……", text)


def split_text_for_genie(text: str) -> List[str]:
    text = _normalize_ellipsis((text or "").strip())
    if not text:
        return []
    if len(text) <= CHUNK_THRESHOLD:
        return [text]
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p and p.strip()]
    if not parts:
        parts = [text]
    chunks: List[str] = []
    buf = ""
    for p in parts:
        if len(p) > MAX_CHUNK:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(p), MAX_CHUNK):
                chunks.append(p[i : i + MAX_CHUNK])
            continue
        if not buf:
            buf = p
        elif len(buf) + len(p) <= MAX_CHUNK:
            buf += p
        else:
            chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks if chunks else [text]


def concat_wavs(wavs: List[bytes]) -> bytes:
    if not wavs:
        return b""
    if len(wavs) == 1:
        return wavs[0]
    out = io.BytesIO()
    params = None
    frames: List[bytes] = []
    for w in wavs:
        with wave.open(io.BytesIO(w), "rb") as wf:
            if params is None:
                params = wf.getparams()
            frames.append(wf.readframes(wf.getnframes()))
    with wave.open(out, "wb") as wo:
        wo.setparams(params)
        for fr in frames:
            wo.writeframes(fr)
    return out.getvalue()


async def synthesize_pcm_chunked(
    client: GenieClient,
    genie_name: str,
    text: str,
    *,
    split_sentence: bool,
) -> bytes:
    if split_sentence:
        pcm = await client.tts_pcm(genie_name, text, split_sentence=True)
        return pcm_to_wav(pcm)

    chunks = split_text_for_genie(text)
    if len(chunks) == 1:
        pcm = await client.tts_pcm(genie_name, chunks[0], split_sentence=False)
        wav = pcm_to_wav(pcm)
        if len(wav) < 1024:
            raise RuntimeError("Genie 合成结果为空或过短")
        return wav

    wavs: List[bytes] = []
    for i, ch in enumerate(chunks):
        pcm = await client.tts_pcm(genie_name, ch, split_sentence=False)
        wav = pcm_to_wav(pcm)
        if len(wav) < 1024:
            raise RuntimeError(
                f"第 {i + 1}/{len(chunks)} 段失败（过短）: {ch[:30]}…"
            )
        wavs.append(wav)
    out = concat_wavs(wavs)
    if len(out) < 1024:
        raise RuntimeError("拼接后音频过短")
    return out