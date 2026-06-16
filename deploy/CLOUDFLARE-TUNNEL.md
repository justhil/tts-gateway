# tts-gateway + Cloudflare HTTPS

VPS 上 Genie 与现有服务已用 **Cloudflare Tunnel**（`cloudflared`）提供 `*.justhil.uk` 证书，无需在机器上单独申请 Let’s Encrypt。

## 推荐域名

| 主机名 | 后端（docker_default 内） |
|--------|---------------------------|
| `tts-gw.justhil.uk` | `http://tts-gateway:8080` |

与现有 `tts.justhil.uk` → `tts-manager:3000`（旧中间件）并存。

## 一键（在 voice-flow 仓库）

```bash
export GENIE_VPS_PASS='...'
# 可选：export TTS_GW_HOSTNAME=tts-gw.justhil.uk
python deploy/vps_cloudflared_add_tts_gw.py
```

脚本会：

1. `docker network connect docker_default tts-gateway`
2. 在宿主机 `cloudflared` 的 `config.yml` **ingress** 首条插入上述主机名（并备份 config）
3. 重启 `cloudflared`

## compose（持久）

`docker-compose.yml` 已声明外部网络 `docker_default`，在 VPS 上 `docker compose up -d` 后会自动加入该网。

## Cloudflare 控制台（Remotely managed 隧道时）

若 ingress **不在** 本地 `config.yml` 管理，请在 **Zero Trust → Networks → Tunnels → Public Hostname** 添加：

- **Subdomain**: `tts-gw`（或你选的子域）
- **Domain**: `justhil.uk`
- **Service**: `http://tts-gateway:8080`
- 确保 `cloudflared` 容器在 **docker_default**，能解析 `tts-gateway`。

证书由 Cloudflare 边缘自动签发（浏览器访问为 HTTPS）。

## 验证

```bash
curl -sS https://tts-gw.justhil.uk/ping
# {"ok":true,"service":"tts-gateway"}
```

浏览器：`https://tts-gw.justhil.uk/ui/`