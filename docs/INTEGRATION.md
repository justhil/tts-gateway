# TTS Gateway — 下游接入规范（Hermes / 任意 HTTP 客户端）

本文档描述 **tts-gateway** 的 HTTP API，用于将文本合成为 **WAV 音频**。网关背后为 **Genie TTS**（ONNX 推理）；客户端**只需调用网关**，无需直连 Genie。

---

## 1. 服务概览

| 项 | 说明 |
|----|------|
| 协议 | HTTP/1.1，JSON（合成接口除外） |
| 合成输出 | **`audio/wav`**，标准 RIFF WAV（32kHz 单声道 16-bit，由网关封装） |
| 角色来源 | 扫描 `CHARACTERS_ROOT` 下含 `vits_fp32.onnx` 的子目录 |
| 参考音来源 | `REFS_ROOT/<角色文件夹>/` 及常见子目录 `emotions/` 等 |
| 交互式文档 | `GET {BASE}/docs`（OpenAPI / Swagger） |
| 测试页 | `GET {BASE}/ui/` |

**占位符（部署时替换）：**

| 占位符 | 示例 |
|--------|------|
| `BASE` | `http://your-host:8088` |
| `CHAR` | 角色 ID（与扫描得到的 `characters[].id` 一致） |
| `KEY` | 服务端配置的 `API_KEY`（未配置则可省略） |

---

## 2. 鉴权

当服务端环境变量 **`API_KEY` 非空** 时，所有 **`/v1/*`** 路由必须携带下列请求头之一（值与 `API_KEY` 完全相同）：

```http
X-API-Key: <KEY>
```

或：

```http
X-TTS-API-Key: <KEY>
```

未配置 `API_KEY` 时，**不需要**鉴权头。

**不受鉴权约束：** `GET /ping`、`GET /health`、`GET /`、`GET /ui/*`（若未对静态资源单独加鉴权）。

---

## 3. 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ping`、`/health` | 存活探测 |
| GET | `/v1/index` | 索引快照（角色数、构建时间等） |
| POST | `/v1/index/refresh` | 强制重建目录索引 |
| GET | `/v1/characters` | 角色列表 |
| GET | `/v1/characters/{character_id}/references` | 某角色的参考音列表 |
| **POST** | **`/v1/tts`** | **推荐：JSON 合成 WAV** |
| GET | `/v1/tts` | Query 合成 WAV（`char_name` 参数） |
| GET | `/tts_proxy` | 兼容旧中间件（需完整 ref 路径与 prompt） |

---

## 4. 健康检查

**请求**

```http
GET {BASE}/ping
```

**响应** `200` `application/json`

```json
{
  "ok": true,
  "service": "tts-gateway"
}
```

---

## 5. 目录与索引

### 5.1 角色列表

```http
GET {BASE}/v1/characters
```

**响应** `200`

```json
{
  "characters": [
    {
      "id": "my-voice",
      "folder": "my-voice",
      "genie_character": "my_voice",
      "onnx_model_dir": "/data/characters/my-voice",
      "language": "zh",
      "reference_count": 11,
      "source": "scan"
    }
  ]
}
```

- **`id`**：合成时 `character_id` 应使用此值（或通过 `character_mappings.json` 映射后的对外名，见 §8）。
- **`genie_character`**：网关内部调用 Genie 用的名称，一般无需客户端指定。

### 5.2 参考音列表

```http
GET {BASE}/v1/characters/{character_id}/references
```

`character_id` 需 URL 编码（中文等）。

**响应** `200`

```json
{
  "character_id": "my-voice",
  "references": [
    {
      "id": "default_line.wav",
      "filename": "default_line.wav",
      "emotion": "default",
      "path": "/data/refs/my-voice/default_line.wav",
      "prompt_text": "与参考音频一致的文本",
      "prompt_source": "sidecar",
      "language": "zh"
    }
  ]
}
```

| 字段 | 含义 |
|------|------|
| `id` | 相对 refs 目录的路径，合成时可用 **`ref_id`** |
| `emotion` | 从文件名前缀解析（如 `angry_xxx.wav` → `angry`） |
| `prompt_text` | 传给 Genie 的参考文案（优先同名 `.txt`） |
| `prompt_source` | `sidecar` / `filename` / `stem` |

### 5.3 刷新索引

上传新 ONNX 或新 wav 后：

```http
POST {BASE}/v1/index/refresh
```

**响应** `200`

```json
{
  "ok": true,
  "built_at": 1718534400.0,
  "character_count": 1
}
```

---

## 6. 合成 TTS（核心）

### 6.1 POST `/v1/tts`（推荐）

**请求**

```http
POST {BASE}/v1/tts
Content-Type: application/json
X-API-Key: <KEY>    # 若启用
```

**Body（JSON）**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `text` | string | 是 | — | 待合成文本，1–2000 字符 |
| `character_id` | string | 是 | — | 角色 ID（§5.1） |
| `ref_id` | string | 否 | — | 参考音 `id`（§5.2），与 `ref_path`/`emotion` 互斥优先级见 §7 |
| `ref_path` | string | 否 | — | 参考 wav **绝对路径**（须网关容器/进程可读） |
| `emotion` | string | 否 | `default` | 无 `ref_id`/`ref_path` 时按情绪选 ref |
| `prompt_text` | string | 否 | — | 覆盖参考文案（应与 wav 内容一致，影响自然度） |
| `language` | string | 否 | `zh` | 传给 Genie 的 `text_lang` |
| `split_sentence` | boolean | 否 | **`false`** | `true` 按句切分多段合成；长文可开，短句建议关 |

**示例**

```json
{
  "text": "你好，这是测试一句。",
  "character_id": "my-voice",
  "ref_id": "angry_sample.wav",
  "language": "zh",
  "split_sentence": false
}
```

**成功响应** `200`

```http
Content-Type: audio/wav
Content-Disposition: attachment; filename="tts.wav"
```

Body 为 **完整 WAV 二进制**，可直接保存或播放。

**失败响应（JSON 或纯文本）**

| HTTP | 含义 |
|------|------|
| 400 | 参数无效、ref 不存在、参考文件不可读 |
| 401 | 缺少或错误的 API Key |
| 404 | 角色不存在 |
| 502 | Genie 返回错误或 load 失败（body 含简短说明） |
| 504 | 合成超时（常见于 Genie OOM 或负载高，建议重试前释放内存） |

客户端应使用 **较长读超时**（建议 **120–300s**），首次加载模型可能较慢。

### 6.2 GET `/v1/tts`

Query 参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `text` | 是 | 待合成文本 |
| `char_name` | 是 | 等同 `character_id` |
| `ref_audio_path` | 否 | 参考 wav 绝对路径 |
| `prompt_text` | 否 | 参考文案 |
| `emotion` | 否 | 默认 `default` |
| `text_lang` | 否 | 默认 `zh` |

**响应**：同 POST，`audio/wav`。

### 6.3 GET `/tts_proxy`（兼容）

与旧 SillyTavern 中间件类似，**必须**提供：

- `text`、`char_name`、`ref_audio_path`、`prompt_text`

可选：`prompt_lang`、`text_lang`、`emotion`。

`ref_audio_path` 必须是 **Genie 进程能读的路径**（网关会按部署做路径映射，一般客户端用 POST + `ref_id` 更简单）。

---

## 7. 参考音选择优先级

网关按下列顺序决定使用哪条参考音（及 `prompt_text`）：

1. **`ref_path`**（若提供且文件存在）  
2. **`ref_id`**（匹配 `references[].id` 或 `filename`）  
3. **`emotion`**（匹配 `references[].emotion`，先 exact，再 `default`，再列表第一条）  

`prompt_text`：请求体显式提供 > 索引中的 `prompt_text` > 文件名 stem。

**集成建议（Hermes）：**

1. 启动或定时 `GET /v1/characters` 缓存角色。  
2. 对每个角色 `GET .../references`，按 `emotion` 或业务标签建本地映射。  
3. 合成时优先传 **`ref_id`** + 可选 **`prompt_text` 覆盖**（与 wav 听写一致时效果最好）。  
4. 台词情绪与参考音情绪尽量一致（生气台词配 `angry` 类 ref）。

---

## 8. 可选配置（服务端，非请求字段）

部署方在 `DATA_DIR` 下可提供：

**`character_mappings.json`** — 对外 ID → 扫描文件夹名

```json
{
  "hermes_speaker_alias": "my-voice"
}
```

**`genie_character_models.json`** — 覆盖 Genie 名与 ONNX 目录

```json
{
  "my-voice": {
    "genie_character": "my_voice",
    "onnx_model_dir": "/data/characters/my-voice",
    "language": "zh"
  }
}
```

客户端仍只使用 **`character_id`**（映射后的别名或文件夹名均可，以索引为准）。

---

## 9. Hermes 推荐接入流程

```text
1. GET  {BASE}/ping
2. GET  {BASE}/v1/characters
3. GET  {BASE}/v1/characters/{id}/references   # 按需缓存
4. POST {BASE}/v1/tts
        → 保存 response body 为 .wav 或送播放器/管道
```

**伪代码（Python）**

```python
import httpx

BASE = "http://your-host:8088"
HEADERS = {"X-API-Key": "your-key"}  # 可选

def synthesize(text: str, character_id: str, ref_id: str | None = None) -> bytes:
    payload = {
        "text": text,
        "character_id": character_id,
        "language": "zh",
        "split_sentence": False,
    }
    if ref_id:
        payload["ref_id"] = ref_id
    with httpx.Client(timeout=300.0) as client:
        r = client.post(f"{BASE}/v1/tts", json=payload, headers=HEADERS)
        r.raise_for_status()
        return r.content  # WAV bytes
```

**伪代码（curl）**

```bash
curl -sS -m 300 -X POST "${BASE}/v1/tts" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${KEY}" \
  -d '{"text":"你好","character_id":"my-voice","ref_id":"default_line.wav","split_sentence":false}' \
  -o speech.wav
```

---

## 10. 与「直连 Genie」的区别

| 项目 | 直连 Genie `:8429` | tts-gateway |
|------|-------------------|-------------|
| 输出格式 | 裸 PCM（32kHz） | 标准 **WAV** |
| 角色/ref | 自行 load/set_reference | **扫描目录 + 自动选 ref** |
| 路径 | 须 Genie 宿主机路径 | 客户端用 **`ref_id`** 即可 |
| 鉴权 | 通常无 | 可选 **API_KEY** |

网关内部等价于：`load_character` → `set_reference_audio` → `POST /tts` → PCM 转 WAV。

---

## 11. 自然度与质量提示（给调用方）

1. **`prompt_text` 应与参考 wav 逐字一致**（标点、语气词）；有同名 `.txt` 时优先使用。  
2. **台词情绪与 `ref_id` / `emotion` 匹配**，避免生气台词配 surprise 参考。  
3. **`split_sentence` 默认 `false`**，短句更连贯；超长文可设为 `true`。  
4. 合成失败 **504**：多为后端 Genie 内存不足，稍后重试或降低同机其它服务负载。  
5. 失败 **502**：查看响应正文中的 Genie 错误摘要。

---

## 12. 错误处理清单

| 场景 | 建议 |
|------|------|
| 401 | 配置 `X-API-Key` |
| 404 角色 | 检查 `character_id`，或 `POST /v1/index/refresh` |
| 400 ref | 检查 `ref_id` 是否在 references 列表中 |
| 502 | 记录 body，检查 Genie 服务与 ONNX/refs |
| 504 | 延长超时重试；避免并发多条合成 |
| 空 WAV / 极小 body | 按错误响应处理，勿当成功 |

---

## 13. 版本与仓库

- 实现：FastAPI，`OpenAPI` 见 `{BASE}/docs`  
- 源码：https://github.com/justhil/tts-gateway  
- 更多占位符示例：`docs/EXAMPLES.md`

---

## 14. 变更记录（接入方关注）

| 日期 | 说明 |
|------|------|
| 2026-06 | `split_sentence` 默认改为 **`false`** |
| 2026-06 | Genie 404 时网关自动重试 load；502/504 替代裸 500 |
| 2026-06 | 容器部署支持 `GENIE_PATH_PREFIX` / `GENIE_PATH_REPLACE` 路径映射（运维项，客户端无感） |

---

**文档用途**：可将本文全文或链接发给 Hermes 配置「自定义工具 / HTTP 插件」，仅需 **BASE URL、可选 API Key、character_id、ref_id/emotion** 即可完成语音合成。