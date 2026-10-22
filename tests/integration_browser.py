"""Verify a real Firefox web input through AT-SPI (run against the container)."""

import asyncio
import json
import os

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    load_dotenv()
    url = os.getenv("NEKO_MCP_URL", "http://127.0.0.1:8080/mcp")
    async with streamablehttp_client(
        url, headers={"Authorization": "Bearer " + os.environ["NEKO_TOKEN"]}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "desktop_launch",
                {
                    "argv": [
                        "firefox-esr",
                        "--new-window",
                        "file:///tmp/nekoworker-browser-fixture.html",
                    ]
                },
            )
            assert not result.isError
            for _ in range(40):
                await asyncio.sleep(0.5)
                result = await session.call_tool(
                    "desktop_tree", {"max_nodes": 1500, "max_depth": 30, "application": "firefox"}
                )
                assert not result.isError
                payload = json.loads(result.content[0].text)
                fields = [
                    n
                    for n in payload["nodes"]
                    if n["name"] == "Browser message" and n["role"] == "entry"
                ]
                if fields:
                    result = await session.call_tool(
                        "desktop_element",
                        {
                            "element_id": fields[-1]["id"],
                            "action": "set_text",
                            "text": "浏览器元素树验证",
                        },
                    )
                    assert not result.isError, result
                    for _ in range(20):
                        await asyncio.sleep(0.1)
                        result = await session.call_tool(
                            "desktop_tree",
                            {"max_nodes": 1500, "max_depth": 30, "application": "firefox"},
                        )
                        nodes = json.loads(result.content[0].text)["nodes"]
                        if any(n.get("text") == "浏览器元素树验证" for n in nodes):
                            break
                    else:
                        raise AssertionError("Firefox input did not change")
                    print("PASS: Firefox web input read and filled with Chinese via AT-SPI")
                    return
            raise AssertionError(
                f"Firefox input not exposed; nodes={len(payload['nodes'])}, warnings={payload['warnings']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
