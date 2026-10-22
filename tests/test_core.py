import asyncio
import subprocess

import httpx
import pytest
from starlette.responses import JSONResponse

from nekoworker.desktop import Desktop
from nekoworker.server import TokenGate
from nekoworker.worker import key, pointer, scroll, tree


def test_bearer_gate():
    async def app(scope, receive, send):
        await JSONResponse({"ok": True})(scope, receive, send)

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=TokenGate(app, "x" * 32)),
            base_url="http://testserver",
        ) as client:
            assert (await client.post("/mcp")).status_code == 401
            assert (
                await client.post("/mcp", headers={"Authorization": "Bearer wrong"})
            ).status_code == 401
            response = await client.post("/mcp", headers={"Authorization": "Bearer " + "x" * 32})
            assert response.json() == {"ok": True}

    asyncio.run(check())


def test_worker_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        Desktop().call("tree")


@pytest.mark.parametrize(
    "operation,args",
    [
        (key, {"keys": "--help"}),
        (pointer, {"x": -1, "y": 0}),
        (scroll, {"amount": 500}),
        (tree, {"max_nodes": 9000}),
    ],
)
def test_invalid_input_does_not_touch_desktop(operation, args):
    with pytest.raises(ValueError):
        operation(**args)
