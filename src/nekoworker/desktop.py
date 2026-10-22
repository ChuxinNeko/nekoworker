"""Bound each desktop operation in a separate process, including hung D-Bus calls."""

import json
import os
import subprocess
import sys
import threading


class Desktop:
    def __init__(self):
        self.lock = threading.Lock()

    def call(self, operation: str, **arguments):
        with self.lock:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "nekoworker.worker"],
                    input=json.dumps({"operation": operation, **arguments}),
                    text=True,
                    capture_output=True,
                    timeout=float(os.getenv("NEKO_OPERATION_TIMEOUT", "20")),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "Desktop operation timed out; refresh the tree and retry"
                ) from exc
            if result.returncode:
                raise RuntimeError(result.stderr[-2000:] or "Desktop worker failed")
            payload = json.loads(result.stdout)
            if "error" in payload:
                raise ValueError(payload["error"])
            return payload["result"]
