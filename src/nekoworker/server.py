"""Authenticated Streamable HTTP and stdio MCP transports."""

import argparse
import asyncio
import base64
import hmac
import os

import uvicorn
from mcp.server.fastmcp import FastMCP, Image
from starlette.responses import JSONResponse

from .desktop import Desktop

INSTRUCTIONS = """You control a Linux desktop as its regular user. Prefer desktop_tree and
 desktop_element for semantic interactions. Refresh the tree after UI changes: IDs belong
 to the latest snapshot and path validation is best effort, not a stable application ID.
 If an app exposes no useful accessibility nodes, use screenshot and keyboard/mouse tools.
 GUI effects are asynchronous: observe the result before the next action. Password text
 is omitted from the tree; screenshots can still contain sensitive information.
 type_text pastes Unicode via clipboard (changes the clipboard); use desktop_key for terminals
 requiring Ctrl+Shift+V. Apps can be launched with desktop_launch argv, without a shell.
 One desktop is shared by all connected clients; use one controlling agent per instance.
"""


def build_server():
    mcp = FastMCP("NekoWorker", instructions=INSTRUCTIONS, stateless_http=True, json_response=True)
    desktop = Desktop()

    @mcp.tool()
    def desktop_tree(max_depth: int = 12, max_nodes: int = 500, application: str = "") -> dict:
        """Read native AT-SPI elements: id, parent, role, name, text, states, bounds, actions.
        Optional application substring filter. Refresh invalidates previous snapshot IDs.
        max_depth: 1..30, max_nodes: 1..3000. If truncated, increase budgets or filter
        by application; web apps often require max_depth=30. Empty nodes mean
        unsupported accessibility or no matching applications.
        """
        return desktop.call(
            "tree", max_depth=max_depth, max_nodes=max_nodes, application=application
        )

    @mcp.tool()
    def desktop_element(element_id: str, action: str = "click", text: str = "") -> dict:
        """Invoke an advertised element action, 'focus', or 'set_text' (editable elements).
        Use exact action names from desktop_tree; refresh after UI changes.
        set_text falls back to focus/select-all/paste if the native API does not apply text.
        """
        return desktop.call("element", element_id=element_id, action=action, text=text)

    @mcp.tool()
    def desktop_screenshot() -> Image:
        """Capture the entire X11 desktop as a PNG image, for visual fallback."""
        return Image(data=base64.b64decode(desktop.call("screenshot")), format="png")

    @mcp.tool()
    def desktop_click(x: int, y: int, button: int = 1, clicks: int = 1) -> dict:
        """Click screen coordinates; button 1=left, 2=middle, 3=right; clicks 1..3."""
        return desktop.call("pointer", x=x, y=y, button=button, clicks=clicks)

    @mcp.tool()
    def desktop_drag(x1: int, y1: int, x2: int, y2: int) -> dict:
        """Drag with the left mouse button between screen coordinates."""
        return desktop.call("drag", x1=x1, y1=y1, x2=x2, y2=y2)

    @mcp.tool()
    def desktop_scroll(direction: str = "down", amount: int = 3) -> dict:
        """Scroll up/down/left/right by 1..50 wheel steps at the current pointer."""
        return desktop.call("scroll", direction=direction, amount=amount)

    @mcp.tool()
    def desktop_key(keys: str) -> dict:
        """Press an X11 key chord, e.g. ctrl+l, Return, alt+F4, ctrl+shift+v."""
        return desktop.call("key", keys=keys)

    @mcp.tool()
    def desktop_type_text(text: str, paste_keys: str = "ctrl+v") -> dict:
        """Paste Unicode into the focused app. Use paste_keys=ctrl+shift+v for terminals."""
        return desktop.call("type_text", text=text, paste_keys=paste_keys)

    @mcp.tool()
    def desktop_windows() -> dict:
        """List X11 windows with hexadecimal IDs, PID, geometry and titles."""
        return desktop.call("windows")

    @mcp.tool()
    def desktop_focus_window(window_id: str) -> dict:
        """Activate a window by hexadecimal ID returned by desktop_windows."""
        return desktop.call("focus_window", window_id=window_id)

    @mcp.tool()
    def desktop_launch(argv: list[str]) -> dict:
        """Launch a desktop application using argv, e.g. ['mousepad'] or ['firefox', URL].
        Executes as the desktop user. This tool can also execute arbitrary programs.
        """
        return desktop.call("launch", argv=argv)

    return mcp


class TokenGate:
    """ASGI bearer authentication for MCP HTTP; health is read-only."""

    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            if scope["path"] == "/healthz":
                try:
                    from .worker import run

                    await asyncio.to_thread(run, "xdpyinfo")
                    response = JSONResponse({"status": "ok"})
                except Exception:
                    response = JSONResponse({"status": "desktop_unavailable"}, status_code=503)
                await response(scope, receive, send)
                return
            headers = dict(scope.get("headers", []))
            expected = f"Bearer {self.token}".encode()
            if not hmac.compare_digest(headers.get(b"authorization", b""), expected):
                await JSONResponse({"error": "Bearer token required"}, status_code=401)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["http", "stdio"], default="http")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    mcp = build_server()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        token = os.getenv("NEKO_TOKEN", "")
        if len(token) < 32:
            parser.error("NEKO_TOKEN must have at least 32 characters for HTTP transport")
        uvicorn.run(TokenGate(mcp.streamable_http_app(), token), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
