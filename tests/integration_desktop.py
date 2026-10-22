"""Run through scripts/test-desktop.sh in an isolated desktop session."""

import asyncio
import json
import os

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    load_dotenv()
    url = os.getenv("NEKO_MCP_URL", "http://127.0.0.1:18080/mcp")
    async with httpx.AsyncClient() as http:
        for _ in range(80):
            try:
                health = await http.get(url.replace("/mcp", "/healthz"))
                if health.status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            await asyncio.sleep(0.25)
        else:
            raise AssertionError("MCP server never became healthy")
        assert (await http.post(url)).status_code == 401
    async with streamablehttp_client(
        url, headers={"Authorization": "Bearer " + os.environ["NEKO_TOKEN"]}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 11

            async def call(name, **arguments):
                result = await session.call_tool(name, arguments)
                assert not result.isError, result
                return json.loads(result.content[0].text)

            await call(
                "desktop_launch",
                argv=[
                    os.environ.get("NEKO_FIXTURE_PYTHON", "/usr/bin/python3"),
                    os.getenv("NEKO_FIXTURE_PATH", os.path.abspath("tests/gtk_fixture.py")),
                ],
            )

            async def get_nodes():
                for _ in range(40):
                    result = await call("desktop_tree")
                    if any(n["name"] == "Message" for n in result["nodes"]):
                        return result["nodes"]
                    await asyncio.sleep(0.25)
                raise AssertionError("GTK app never appeared in AT-SPI tree")

            nodes = await get_nodes()
            entry = next(n for n in nodes if n["name"] == "Message")
            await call(
                "desktop_element", element_id=entry["id"], action="set_text", text="你好 NekoWorker"
            )
            nodes = await get_nodes()
            button = next(n for n in nodes if n["name"] == "Submit")
            assert button["actions"]
            await call("desktop_element", element_id=button["id"], action=button["actions"][0])
            for _ in range(20):
                nodes = await get_nodes()
                if any(n["name"] == "Received: 你好 NekoWorker" for n in nodes):
                    break
                await asyncio.sleep(0.1)
            else:
                raise AssertionError("Native button action did not update label")
            stale = await session.call_tool(
                "desktop_element", {"element_id": entry["id"], "action": "focus"}
            )
            assert stale.isError
            entry = next(n for n in nodes if n["name"] == "Message")
            await call("desktop_element", element_id=entry["id"], action="focus")
            await call("desktop_key", keys="ctrl+a")
            await call("desktop_type_text", text="剪贴板验证")
            await asyncio.sleep(0.3)
            nodes = await get_nodes()
            assert any(n.get("text") == "剪贴板验证" for n in nodes), nodes
            shot = await session.call_tool("desktop_screenshot", {})
            assert not shot.isError and shot.content[0].type == "image"
            windows = await call("desktop_windows")
            window = next(w for w in windows["windows"] if "NekoWorker Integration" in w)
            await call("desktop_focus_window", window_id=window.split()[0])
            await call("desktop_drag", x1=600, y1=400, x2=700, y2=450)
            await call("desktop_scroll", direction="down", amount=1)
            # Pointer fallback also triggers the GTK button.
            button = next(n for n in nodes if n["name"] == "Submit")
            x, y, width, height = button["bounds"]
            await call("desktop_click", x=x + width // 2, y=y + height // 2)
            await asyncio.sleep(0.3)
            nodes = await get_nodes()
            assert any(n["name"] == "Received: 剪贴板验证" for n in nodes)
            print(
                "PASS: auth, 11 MCP tools, native tree, Unicode set_text, semantic action, stale IDs, clipboard paste, PNG, windows, pointer click"
            )


if __name__ == "__main__":
    asyncio.run(main())
