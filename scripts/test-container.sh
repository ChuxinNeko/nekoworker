#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose cp tests/gtk_fixture.py desktop:/tmp/nekoworker-gtk-fixture.py
NEKO_FIXTURE_PATH=/tmp/nekoworker-gtk-fixture.py NEKO_MCP_URL="http://127.0.0.1:${NEKO_MCP_PORT:-8080}/mcp" \
    .venv/bin/python tests/integration_desktop.py
.venv/bin/python tests/check_novnc.py
docker compose cp tests/browser_fixture.html desktop:/tmp/nekoworker-browser-fixture.html
NEKO_MCP_URL="http://127.0.0.1:${NEKO_MCP_PORT:-8080}/mcp" .venv/bin/python tests/integration_browser.py
