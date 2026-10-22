"""NEKO_TOKEN=... python examples/client.py"""
import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client(
        os.getenv("NEKO_MCP_URL", "http://127.0.0.1:8080/mcp"),
        headers={"Authorization": f"Bearer {os.environ['NEKO_TOKEN']}"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("desktop_tree", {"max_nodes": 200})
            for block in result.content:
                if block.type == "text":
                    print(block.text)


asyncio.run(main())
