#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Ubuntu/Debian only. Install packages as root; create the venv as the invoking user.
if [ "$(id -u)" -eq 0 ]; then
    echo '请以普通用户执行此脚本；脚本会使用 sudo 安装系统依赖。' >&2
    exit 1
fi
sudo apt-get update
sudo apt-get install -y python3-venv python3-pyatspi python3-gi gir1.2-gtk-3.0 \
    at-spi2-core dbus-x11 xvfb xauth xfce4 xfce4-terminal mousepad x11vnc \
    novnc websockify supervisor xdotool xclip wmctrl x11-utils fonts-noto-cjk
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
printf '\n安装完成，执行 ./scripts/native.sh up 启动。\n'
