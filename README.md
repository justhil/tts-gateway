# Genie TTS Gateway

独立 **Genie 中转 API**（无 SillyTavern / 权重切换 / 缓存臃肿逻辑），参考 `SillyTavern-GPT-SoVITS` 的 Genie 桥接方式。

## 索引规则（无硬编码角色）

- **`CHARACTERS_ROOT`**：子目录内含 `vits_fp32.onnx` → 自动列为角色。
- **`REFS_ROOT/<文件夹名>/`**：扫描 `*.wav` 等，`.txt` 或 `情绪_文案.wav` 解析 `prompt_text`。
- **`data/genie_character_models.json`**（可选）：仅**覆盖** `genie_character`、`onnx_model_dir`、`language`；默认可 `{}`。
- **`data/character_mappings.json`**（可选）：对外别名 → 文件夹名，如酒馆名；默认可 `{}`。
- 目录或 JSON 变更后：自动按 mtime 重建缓存，或 `POST /v1/index/refresh`。

## 功能

| 接口 | 说明 |
|------|------|
| `GET /ping` | 健康检查 |
| `GET /v1/index` | 当前扫描结果摘要 |
| `POST /v1/index/refresh` | 强制重扫目录 |
| `GET /v1/characters` | 角色列表（目录扫描） |
| `GET /v1/characters/{id}/references` | 参考 wav + `prompt_text` + `emotion` |
| `POST /v1/tts` | JSON 合成，响应 **WAV** |
| `GET /v1/tts` | 查询参数合成（`char_name` 兼容） |
| `GET /tts_proxy` | 与旧中间件参数兼容 |
| `/` 或 `/ui/` | 浏览器测试页（试听 + 下载） |

## 环境变量

见 `.env.example`：`GENIE_HOST`、`CHARACTERS_ROOT`、`REFS_ROOT`、`DATA_DIR`、`API_KEY`。

## 本地运行

```bash
cd genie-tts-gateway
pip install -e .
export GENIE_HOST=http://127.0.0.1:8429
export CHARACTERS_ROOT=/www/genie/characters
export REFS_ROOT=/www/genie/refs
export DATA_DIR=./data
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

打开 http://127.0.0.1:8088/ui/

## Docker（VPS）

```bash
docker compose build
docker compose up -d
```

默认映射 **8088→8080**，与 `tts-manager` 并存；Tunnel 可改指 `genie-tts-gateway:8080`。

## 示例

```bash
curl -s http://127.0.0.1:8088/v1/characters | jq .
curl -s "http://127.0.0.1:8088/v1/characters/<文件夹名>/references" | jq .
curl -X POST http://127.0.0.1:8088/v1/tts -H "Content-Type: application/json" \
  -d '{"text":"测试","character_id":"<文件夹名>","emotion":"default"}' -o out.wav
```

## 镜像体积

基于 `python:3.12-slim`，仅 FastAPI + httpx，无 torch/ffmpeg。