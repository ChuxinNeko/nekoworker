#!/bin/sh
set -eu
: "${NEKO_TOKEN:?NEKO_TOKEN required}"
: "${NEKO_VNC_PASSWORD:?NEKO_VNC_PASSWORD required}"
[ "${#NEKO_TOKEN}" -ge 32 ] || { echo 'Token must be >=32 characters' >&2; exit 1; }
[ "${#NEKO_VNC_PASSWORD}" -ge 8 ] || { echo 'VNC password must be >=8 characters' >&2; exit 1; }
export NEKO_RESOLUTION="${NEKO_RESOLUTION:-1440x900}"
case "$NEKO_RESOLUTION" in *[!0-9x]*|'') echo 'Invalid resolution' >&2; exit 1;; esac
printf '%s' "$NEKO_RESOLUTION" | grep -Eq '^[0-9]{3,4}x[0-9]{3,4}$' || exit 1
mkdir -p "$XDG_RUNTIME_DIR" "$HOME/.vnc" "$HOME/.config/xfce4/xfconf/xfce-perchannel-xml"
chmod 700 "$XDG_RUNTIME_DIR" "$HOME/.vnc"
x11vnc -storepasswd "$NEKO_VNC_PASSWORD" "$HOME/.vnc/passwd" >/dev/null
chmod 600 "$HOME/.vnc/passwd"
# One D-Bus session shared by desktop, AT-SPI registry, MCP and applications.
exec dbus-run-session -- sh -c 'umask 077; printf "%s" "$DBUS_SESSION_BUS_ADDRESS" > "$XDG_RUNTIME_DIR/session-bus"; exec supervisord -c /etc/nekoworker-supervisord.conf'
