import os
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.catalog import list_characters, list_references, resolve_character
from app.config import Settings, get_settings, path_for_genie
from app.genie_client import GenieClient, clear_genie_session, pcm_to_wav

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="TTS Gateway", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if not settings.api_key:
        return
    key = request.headers.get("X-API-Key") or request.headers.get("X-TTS-API-Key")
    if key != settings.api_key:
        raise HTTPException(401, "Invalid API key")


class TtsBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    character_id: str = Field(..., description="角色 ID（与 characters 目录下文件夹名或 mappings 别名一致）")
    ref_path: str | None = Field(None, description="参考 wav 绝对路径")
    ref_id: str | None = Field(None, description="refs 目录下文件名")
    emotion: str | None = Field(None, description="按情绪选 ref")
    prompt_text: str | None = None
    language: str = "zh"
    split_sentence: bool = False


def _pick_ref(character_id: str, body: TtsBody) -> tuple[str, str]:
    refs = list_references(character_id)
    if not refs:
        raise HTTPException(404, f"角色 {character_id} 无参考音频")
    if body.ref_path:
        path = body.ref_path
        if not os.path.isfile(path):
            raise HTTPException(400, "ref_path 不存在")
        pt = body.prompt_text or ""
        for r in refs:
            if r["path"] == path:
                pt = pt or r["prompt_text"]
                break
        return path, pt or Path(path).stem
    if body.ref_id:
        for r in refs:
            if r["id"] == body.ref_id or r.get("filename") == body.ref_id:
                return r["path"], body.prompt_text or r["prompt_text"]
        raise HTTPException(400, "ref_id 无效")
    em = (body.emotion or "default").lower()
    for r in refs:
        if r["emotion"] == em:
            return r["path"], body.prompt_text or r["prompt_text"]
    for r in refs:
        if r["emotion"] == "default":
            return r["path"], body.prompt_text or r["prompt_text"]
    return refs[0]["path"], body.prompt_text or refs[0]["prompt_text"]


async def _run_genie_tts(
    client: GenieClient,
    genie_name: str,
    onnx_dir: str,
    language: str,
    ref_for_genie: str,
    prompt_text: str,
    body: TtsBody,
    *,
    force_load: bool = False,
) -> bytes:
    await client.ensure_character(genie_name, onnx_dir, language, force=force_load)
    await client.set_reference(genie_name, ref_for_genie, prompt_text, body.language)
    return await client.tts_pcm(genie_name, body.text, body.split_sentence)


async def _synthesize(body: TtsBody) -> bytes:
    info = resolve_character(body.character_id)
    if not info:
        raise HTTPException(404, f"未找到角色 {body.character_id}")
    ref_path, prompt_text = _pick_ref(body.character_id, body)
    if not os.path.isfile(ref_path):
        raise HTTPException(400, f"参考音频不可读: {ref_path}")
    client = GenieClient(timeout=get_settings().tts_timeout_sec)
    onnx_dir = path_for_genie(info["onnx_model_dir"])
    ref_for_genie = path_for_genie(ref_path)
    gname = info["genie_character"]
    try:
        pcm = await _run_genie_tts(
            client, gname, onnx_dir, info["language"], ref_for_genie, prompt_text, body
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            clear_genie_session(gname)
            try:
                pcm = await _run_genie_tts(
                    client,
                    gname,
                    onnx_dir,
                    info["language"],
                    ref_for_genie,
                    prompt_text,
                    body,
                    force_load=True,
                )
            except httpx.HTTPStatusError as e2:
                raise HTTPException(
                    502,
                    f"Genie 错误 {e2.response.status_code}: {e2.response.text[:300]}",
                ) from e2
        else:
            raise HTTPException(
                502, f"Genie 错误 {e.response.status_code}: {e.response.text[:300]}"
            ) from e
    except httpx.ReadTimeout as e:
        raise HTTPException(
            504,
            "Genie 合成超时（可能内存不足被 OOM，请释放 Hermes/其他服务后重试）",
        ) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    wav = pcm_to_wav(pcm)
    if len(wav) < 1024:
        raise HTTPException(
            502,
            "合成结果为空或过短（Genie 可能 OOM 或长文本未产出音频，可缩短文本或开启 split_sentence）",
        )
    return wav


@app.get("/health")
@app.get("/ping")
async def health():
    return {"ok": True, "service": "tts-gateway"}


@app.get("/v1/index")
async def api_index(_: None = Depends(verify_api_key)):
    from app.index_store import get_index

    idx = get_index()
    return {
        "built_at": idx.built_at,
        "characters_root": str(get_settings().characters_root),
        "refs_root": str(get_settings().refs_root),
        "character_count": len(idx.characters),
        "characters": idx.characters,
        "reference_counts": {k: len(v) for k, v in idx.references.items()},
    }


@app.post("/v1/index/refresh")
async def api_index_refresh(_: None = Depends(verify_api_key)):
    from app.index_store import get_index, invalidate_index

    invalidate_index()
    idx = get_index(force_rebuild=True)
    return {
        "ok": True,
        "built_at": idx.built_at,
        "character_count": len(idx.characters),
    }


@app.get("/v1/characters")
async def api_characters(_: None = Depends(verify_api_key)):
    return {"characters": list_characters()}


@app.get("/v1/characters/{character_id}/references")
async def api_references(character_id: str, _: None = Depends(verify_api_key)):
    refs = list_references(character_id)
    if not refs and not resolve_character(character_id):
        raise HTTPException(404, "角色不存在")
    return {"character_id": character_id, "references": refs}


@app.post("/v1/tts")
async def api_tts_post(body: TtsBody, _: None = Depends(verify_api_key)):
    wav = await _synthesize(body)
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="tts.wav"'},
    )


@app.get("/v1/tts")
async def api_tts_get(
    text: str = Query(...),
    character_id: str = Query(..., alias="char_name"),
    ref_audio_path: str | None = None,
    prompt_text: str | None = None,
    emotion: str | None = "default",
    text_lang: str = "zh",
    _: None = Depends(verify_api_key),
):
    body = TtsBody(
        text=text,
        character_id=character_id,
        ref_path=ref_audio_path,
        prompt_text=prompt_text,
        emotion=emotion,
        language=text_lang,
    )
    wav = await _synthesize(body)
    return Response(content=wav, media_type="audio/wav")


# 兼容旧中间件路径
@app.get("/tts_proxy")
async def tts_proxy_compat(
    text: str = Query(...),
    char_name: str = Query(...),
    ref_audio_path: str = Query(...),
    prompt_text: str = Query(...),
    prompt_lang: str = "zh",
    text_lang: str = "zh",
    emotion: str | None = "default",
    _: None = Depends(verify_api_key),
):
    body = TtsBody(
        text=text,
        character_id=char_name,
        ref_path=ref_audio_path,
        prompt_text=prompt_text,
        emotion=emotion,
        language=text_lang or prompt_lang,
    )
    wav = await _synthesize(body)
    return Response(content=wav, media_type="audio/wav")


if STATIC.is_dir():
    app.mount("/ui", StaticFiles(directory=str(STATIC), html=True), name="ui")


@app.get("/")
async def root():
    if (STATIC / "index.html").is_file():
        return FileResponse(STATIC / "index.html")
    return {"docs": "/docs", "ui": "/ui/"}