"""Run a separate local desktop session without Docker (no filesystem isolation)."""

import argparse
import fcntl
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SESSION_KEYS = (
    "DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "HOME",
    "GTK_MODULES",
    "QT_ACCESSIBILITY",
    "QT_LINUX_ACCESSIBILITY_ALWAYS_ON",
    "NO_AT_BRIDGE",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_CURRENT_DESKTOP",
)


def control(state, *args):
    return subprocess.run(
        ["supervisorctl", "-c", str(state / "supervisord.conf"), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def occupied(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return True
    return False


def start(state, args):
    if os.geteuid() == 0:
        raise ValueError("Start the desktop as a regular user, without sudo")
    required = (
        "Xvfb",
        "xvfb-run",
        "xauth",
        "dbus-run-session",
        "xfce4-session",
        "x11vnc",
        "websockify",
        "supervisord",
        "supervisorctl",
        "xdotool",
        "xclip",
        "wmctrl",
    )
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise ValueError(f"Missing programs: {', '.join(missing)}. Run scripts/install-native.sh")
    if (state / "supervisord.conf").exists() and control(state, "pid").returncode == 0:
        print("Desktop already running\n" + control(state, "status").stdout)
        return
    if args.vnc_port == 0:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            args.vnc_port = sock.getsockname()[1]
    if len({args.mcp_port, args.desktop_port, args.vnc_port}) != 3:
        raise ValueError("MCP, desktop and VNC ports must differ")
    for port in (args.mcp_port, args.desktop_port, args.vnc_port):
        if not 1 <= port <= 65535 or occupied(port):
            raise ValueError(f"Port {port} unavailable; select another port")
    width, height = args.resolution.split("x")
    if not (320 <= int(width) <= 7680 and 200 <= int(height) <= 4320):
        raise ValueError("Resolution must be between 320x200 and 7680x4320")
    novnc = Path(args.novnc_web).resolve()
    if not (novnc / "vnc.html").is_file():
        raise ValueError(f"noVNC not found at {novnc}")
    for directory in (state / "home", state / "runtime", state / "workspace"):
        directory.mkdir(exist_ok=True, mode=0o700)
    credentials = state / "credentials.json"
    if not credentials.exists():
        credentials.write_text(
            json.dumps({"token": secrets.token_hex(32), "vnc_password": secrets.token_urlsafe(6)})
        )
        credentials.chmod(0o600)
    values = json.loads(credentials.read_text())
    if len(values["token"]) < 32 or len(values["vnc_password"]) != 8:
        raise ValueError(
            "Invalid credentials.json: require token >=32 and VNC password 8 characters"
        )
    password_file = state / "runtime" / "vnc-passwd"
    subprocess.run(
        ["x11vnc", "-storepasswd", values["vnc_password"], str(password_file)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    password_file.chmod(0o600)

    # Supervisor interpolation needs literal percent signs escaped.
    def quote(value):
        import shlex

        return shlex.quote(str(value)).replace("%", "%%")

    config = f"""[unix_http_server]
file={state}/control.sock
chmod=0600
[supervisord]
nodaemon=true
logfile={state}/supervisor.log
pidfile={state}/supervisor.pid
childlogdir={state}
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[supervisorctl]
serverurl=unix://{state}/control.sock
"""
    commands = {
        "desktop": "xfce4-session",
        "vnc": f"x11vnc -display %(ENV_DISPLAY)s -rfbport {args.vnc_port} -listen 127.0.0.1 "
        f"-forever -shared -rfbauth {quote(password_file)}",
        "novnc": f"websockify --web={quote(novnc)} 127.0.0.1:{args.desktop_port} "
        f"127.0.0.1:{args.vnc_port}",
        "mcp": f"{quote(sys.executable)} -m nekoworker.server --host 127.0.0.1 "
        f"--port {args.mcp_port}",
    }
    for name, command in commands.items():
        config += f"""
[program:{name}]
command={command}
directory={state}/workspace
autorestart=true
stopasgroup=true
killasgroup=true
stopwaitsecs=5
"""
    (state / "supervisord.conf").write_text(config)
    (state / "settings.json").write_text(
        json.dumps(
            {
                "mcp_port": args.mcp_port,
                "desktop_port": args.desktop_port,
                "vnc_port": args.vnc_port,
            }
        )
    )
    env = os.environ.copy()
    for name in (
        "SESSION_MANAGER",
        "DBUS_SESSION_BUS_ADDRESS",
        "DBUS_STARTER_ADDRESS",
        "DBUS_STARTER_BUS_TYPE",
        "WAYLAND_DISPLAY",
        "AT_SPI_BUS_ADDRESS",
    ):
        env.pop(name, None)
    env.update(
        {
            "HOME": str(state / "home"),
            "XDG_RUNTIME_DIR": str(state / "runtime"),
            "XDG_CONFIG_HOME": str(state / "home/.config"),
            "XDG_CACHE_HOME": str(state / "home/.cache"),
            "XDG_DATA_HOME": str(state / "home/.local/share"),
            "XDG_CURRENT_DESKTOP": "XFCE",
            "GTK_MODULES": "gail:atk-bridge",
            "QT_ACCESSIBILITY": "1",
            "QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "1",
            "NO_AT_BRIDGE": "0",
            "NEKO_TOKEN": values["token"],
        }
    )
    with (state / "launcher.log").open("ab") as log:
        process = subprocess.Popen(
            [
                "xvfb-run",
                "-a",
                "-s",
                f"-screen 0 {args.resolution}x24 -nolisten tcp",
                "dbus-run-session",
                "--",
                sys.executable,
                "-m",
                "nekoworker.native",
                "--state-dir",
                str(state),
                "session",
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    try:
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError(f"Desktop exited; inspect {state}/launcher.log")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{args.mcp_port}/healthz", timeout=1
                ) as response:
                    healthy = response.status == 200
                if healthy and control(state, "status").stdout.count("RUNNING") == 4:
                    print(
                        f"Desktop: http://127.0.0.1:{args.desktop_port}/vnc.html\n"
                        f"MCP: http://127.0.0.1:{args.mcp_port}/mcp\n"
                        f"Credentials: {credentials}"
                    )
                    return
            except OSError:
                pass
            time.sleep(0.25)
        raise RuntimeError(f"Startup timed out; inspect {state}/launcher.log")
    except BaseException:
        # Kill only the new session started by this invocation.
        import signal

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", default=os.getenv("NEKO_NATIVE_STATE", ".native"))
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up")
    up.add_argument("--mcp-port", type=int, default=8081)
    up.add_argument("--desktop-port", type=int, default=6081)
    up.add_argument("--vnc-port", type=int, default=0, help="0 selects a free local port")
    up.add_argument("--resolution", default="1440x900")
    up.add_argument("--novnc-web", default="/usr/share/novnc")
    for name in ("down", "status", "stdio", "session"):
        sub.add_parser(name)
    args = parser.parse_args()
    state = Path(args.state_dir).resolve()
    # Keep supervisor socket under UNIX path-length limits and reject config injection.
    if len(str(state)) > 80 or any(c in str(state) for c in "\n\r%"):
        parser.error("Use a shorter state path without newline or percent characters")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    if args.command == "session":
        (state / "session.json").write_text(
            json.dumps({k: os.environ[k] for k in SESSION_KEYS if k in os.environ})
        )
        os.execvp("supervisord", ["supervisord", "-c", str(state / "supervisord.conf")])
    if args.command == "stdio":
        if control(state, "pid").returncode:
            parser.error("Desktop is not running")
        os.environ.update(json.loads((state / "session.json").read_text()))
        os.chdir(state / "workspace")
        os.execv(
            sys.executable, [sys.executable, "-m", "nekoworker.server", "--transport", "stdio"]
        )
    with (state / "manager.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == "up":
            start(state, args)
        elif not (state / "supervisord.conf").exists():
            print("Desktop not running")
        else:
            result = control(state, "shutdown" if args.command == "down" else "status")
            print(result.stdout or result.stderr, end="")
            if args.command == "down" and result.returncode == 0:
                settings = json.loads((state / "settings.json").read_text())
                for _ in range(200):
                    ports_closed = all(not occupied(port) for port in settings.values())
                    if not (state / "control.sock").exists() and ports_closed:
                        print("Desktop stopped; files retained")
                        return
                    time.sleep(0.1)
                raise RuntimeError("Shutdown timed out; inspect supervisor.log")


if __name__ == "__main__":
    main()
