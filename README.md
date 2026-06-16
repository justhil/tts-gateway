# TTS Gateway

轻量 **Genie TTS 中转**：目录扫描角色与参考音，标准 HTTP 合成 WAV + 简易测试页。

## 索引规则（无硬编码角色）

- **`CHARACTERS_ROOT`**：子目录含 `vits_fp32.onnx` → 自动列为角色。
- **`REFS_ROOT/<文件夹名>/`**：根目录、`emotions/`、`Chinese/emotions/` 等子目录下的音频。
- **文案**：同名 `.txt` → 文件名 `标签_正文` → stem；响应含 `prompt_source`。
- **`DATA_DIR/genie_character_models.json`**（可选 `{}`）：覆盖 `genie_character` / `onnx_model_dir`。
- **`DATA_DIR/character_mappings.json`**（可选 `{}`）：对外 ID → 文件夹名。
- 变更后：`POST /v1/index/refresh` 或依赖 mtime 自动重建。

详细 curl 见 **[docs/EXAMPLES.md](docs/EXAMPLES.md)**（仅用占位符）。

## API

| 方法 | 路径 |
|------|------|
| GET | `/ping` |
| GET | `/v1/index` |
| POST | `/v1/index/refresh` |
| GET | `/v1/characters` |
| GET | `/v1/characters/{id}/references` |
| POST | `/v1/tts` → `audio/wav` |
| GET | `/v1/tts` / `/tts_proxy` |
| GET | `/ui/` 测试页 |

## 环境变量

复制 `.env.example` → `.env`（**勿提交 `.env`**）：

| 变量 | 说明 |
|------|------|
| `GENIE_HOST` | Genie API 根地址 |
| `CHARACTERS_ROOT` | ONNX 角色根目录 |
| `REFS_ROOT` | 参考音根目录 |
| `DATA_DIR` | 可选 JSON 配置目录 |
| `API_KEY` | 非空则要求 `X-API-Key` |
| `REFS_SCAN_MAX_DEPTH` | 预留深度扫描参数 |

## 本地运行

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 指向本机目录与 Genie 地址
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

浏览器打开 `/ui/`。

## Docker

```bash
mkdir -p volumes/characters volumes/refs
# 将 ONNX 与 refs 放到 volumes 下，或改 compose 里的 GENIE_*_DIR
docker compose build && docker compose up -d
```

Compose 通过 **`GENIE_CHARACTERS_DIR` / `GENIE_REFS_DIR` / `GENIE_CONFIG_DIR`** 挂载宿主机路径，默认值见 `docker-compose.yml`。

## 镜像

`python:3.12-slim` + FastAPI + httpx，无 torch/ffmpeg。