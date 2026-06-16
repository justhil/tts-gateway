# API 示例（占位符，请替换为你的环境）

将下列占位符换成实际值：

| 占位符 | 含义 |
|--------|------|
| `BASE` | 网关根 URL，如 `http://localhost:8088` |
| `CHAR` | 角色 ID（扫描得到的文件夹名） |
| `KEY` | 若启用 `API_KEY`，请求头 `X-API-Key` |

## 健康检查

```bash
curl -s "${BASE}/ping"
```

## 索引与刷新

```bash
curl -s "${BASE}/v1/index"
curl -s -X POST "${BASE}/v1/index/refresh"
```

## 角色与参考音

```bash
curl -s "${BASE}/v1/characters"
curl -s "${BASE}/v1/characters/${CHAR}/references"
```

参考音条目含：`path`、`prompt_text`、`emotion`、`prompt_source`（sidecar / filename / stem）。

## 合成 WAV

```bash
curl -s -X POST "${BASE}/v1/tts" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"你好，测试一句。\",\"character_id\":\"${CHAR}\",\"emotion\":\"default\"}" \
  -o out.wav
```

按参考文件：

```bash
curl -s -X POST "${BASE}/v1/tts" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"台词\",\"character_id\":\"${CHAR}\",\"ref_id\":\"angry_sample.wav\"}" \
  -o out.wav
```

## 兼容 GET（旧中间件风格）

```bash
curl -G "${BASE}/tts_proxy" \
  --data-urlencode "text=测试" \
  --data-urlencode "char_name=${CHAR}" \
  --data-urlencode "ref_audio_path=/data/references/${CHAR}/default_ref.wav" \
  --data-urlencode "prompt_text=与参考音频一致的文本" \
  --data-urlencode "text_lang=zh" \
  --data-urlencode "prompt_lang=zh" \
  -o out.wav
```

`ref_audio_path` 必须是 **Genie 进程可读** 的路径（容器内路径需与 Genie 挂载一致）。

## 目录布局示例（无真实数据）

```text
/data/characters/
  my-voice/
    vits_fp32.onnx
    ...

/data/references/
  my-voice/
    default_opening.wav
    default_opening.txt          # 可选，优先于文件名解析
    angry_line.wav               # 或 angry_台词内容.wav

/data/config/
  genie_character_models.json    # 可选 {}
  character_mappings.json        # 可选 {}
```

可选覆盖 `genie_character_models.json`：

```json
{
  "my-voice": {
    "genie_character": "my_voice_api_name",
    "language": "zh"
  }
}
```

可选别名 `character_mappings.json`：

```json
{
  "st_card_display_name": "my-voice"
}
```