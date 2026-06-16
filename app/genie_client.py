import io
import wave
from typing import Optional

import httpx

from app.config import get_settings

SAMPLE_RATE = 32000
_loaded: set[str] = set()
_ref_state: dict[str, tuple[str, str, str]] = {}


def pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


class GenieClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 600.0):
        self.base = (base_url or get_settings().genie_host).rstrip("/")
        self.timeout = timeout

    async def _post(self, path: str, body: dict) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(f"{self.base}{path}", json=body)

    async def ensure_character(self, genie_name: str, onnx_dir: str, language: str) -> None:
        if genie_name in _loaded:
            return
        r = await self._post(
            "/load_character",
            {
                "character_name": genie_name,
                "onnx_model_dir": onnx_dir,
                "language": language,
            },
        )
        r.raise_for_status()
        _loaded.add(genie_name)

    async def set_reference(
        self, genie_name: str, audio_path: str, audio_text: str, language: str
    ) -> None:
        state = (audio_path, audio_text, language)
        if _ref_state.get(genie_name) == state:
            return
        r = await self._post(
            "/set_reference_audio",
            {
                "character_name": genie_name,
                "audio_path": audio_path,
                "audio_text": audio_text,
                "language": language,
            },
        )
        r.raise_for_status()
        _ref_state[genie_name] = state

    async def tts_pcm(self, genie_name: str, text: str, split_sentence: bool = True) -> bytes:
        r = await self._post(
            "/tts",
            {
                "character_name": genie_name,
                "text": text,
                "split_sentence": split_sentence,
            },
        )
        r.raise_for_status()
        return r.content