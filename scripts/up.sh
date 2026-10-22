#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo '请先安装 Docker Engine 和 Docker Compose v2。' >&2; exit 1; }
docker compose version >/dev/null
docker info >/dev/null 2>&1 || { echo '无法访问 Docker 守护进程：请确认 Docker 已启动，当前用户有 socket 权限，或使用 sudo ./scripts/up.sh。' >&2; exit 1; }
if [ ! -f .env ]; then
    (umask 077; python3 - <<'PY'
import secrets
from pathlib import Path
Path('.env').write_text('NEKO_TOKEN=' + secrets.token_hex(32) + '\nNEKO_VNC_PASSWORD=' + secrets.token_urlsafe(6) + '\n')
PY
    )
fi
docker compose up --build -d --wait --wait-timeout 180
printf '\n桌面端口: %s\nMCP 端口: %s\n桌面路径 /vnc.html，MCP 路径 /mcp。密码和 Token 保存在 .env。\n' "$(docker compose port desktop 6080)" "$(docker compose port desktop 8080)"
