"""Verify noVNC serves HTML and its websocket reaches a password-protected RFB server."""

import base64
import os
import socket
import struct
import urllib.request


def main():
    port = int(os.getenv("NEKO_DESKTOP_PORT", "6080"))
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/vnc.html", timeout=5) as response:
        assert response.status == 200
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET /websockify HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: binary\r\n\r\n"
        )
        connection.sendall(request.encode())
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += connection.recv(1)
        assert b"101 Switching Protocols" in header, header

        def read_exact(size):
            data = b""
            while len(data) < size:
                chunk = connection.recv(size - len(data))
                if not chunk:
                    raise AssertionError("Unexpected websocket close")
                data += chunk
            return data

        def receive():
            first, length = read_exact(2)
            assert first & 0x0F == 2, "Expected binary websocket frame"
            length &= 0x7F
            if length == 126:
                length = struct.unpack("!H", read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", read_exact(8))[0]
            return read_exact(length)

        assert receive() == b"RFB 003.008\n"
        payload = b"RFB 003.008\n"
        mask = os.urandom(4)
        connection.sendall(
            bytes([0x82, 0x80 | len(payload)])
            + mask
            + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        )
        security = receive()
        assert security == b"\x01\x02", f"Expected VNC password security only: {security!r}"
    print("PASS: noVNC HTML, websocket proxy, RFB handshake, password authentication required")


if __name__ == "__main__":
    main()
