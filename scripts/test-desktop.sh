#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# xvfb-run chooses a free display; dbus-run-session creates an isolated session bus.
neko_test_runtime=$(mktemp -d)
chmod 700 "$neko_test_runtime"
trap 'rm -rf "$neko_test_runtime"' EXIT
XDG_RUNTIME_DIR="$neko_test_runtime" xvfb-run -a -s '-screen 0 1280x800x24 -nolisten tcp' dbus-run-session -- bash -euo pipefail -c '
    export NEKO_TOKEN=integration-test-token-000000000000000
    export GTK_MODULES=gail:atk-bridge NO_AT_BRIDGE=0
    xfwm4 >/dev/null 2>&1 &
    wm_pid=$!
    .venv/bin/nekoworker --host 127.0.0.1 --port 18080 >"$XDG_RUNTIME_DIR/mcp.log" 2>&1 &
    server_pid=$!
    trap '\''kill "$server_pid" "$wm_pid" 2>/dev/null || true; cat "$XDG_RUNTIME_DIR/mcp.log"'\'' EXIT
    .venv/bin/python tests/integration_desktop.py
'
