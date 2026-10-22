#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || { echo '请先执行 ./scripts/install-native.sh' >&2; exit 1; }
exec .venv/bin/python -m nekoworker.native "$@"
