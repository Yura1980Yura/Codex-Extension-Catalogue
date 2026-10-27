"""Read-only Codex skills/list. No model turn, plugin mutation or cache guessing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time


def executable(explicit: str | None = None) -> str:
    if explicit:
        if not Path(explicit).is_file():
            raise FileNotFoundError(explicit)
        return explicit
    # Desktop's current PATH entry precedes the standalone CLI, where present.
    for name in ("codex.exe", "codex"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("Codex executable not found; set codex_executable in settings.json")


def request(method, params, explicit=None, timeout=35, codex_home=None, process_cwd=None):
    """One documented app-server request, without creating a model turn."""
    environment = dict(os.environ)
    if codex_home is not None:
        environment["CODEX_HOME"] = str(Path(codex_home).resolve())
    process = subprocess.Popen(
        [executable(explicit), "app-server", "--stdio"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        encoding="utf-8", env=environment, cwd=process_cwd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    messages: queue.Queue = queue.Queue()

    def reader():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                continue
        messages.put({"reader_closed": True})

    worker = threading.Thread(target=reader, daemon=True)
    worker.start()
    deadline = time.monotonic() + timeout

    def send(payload):
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()

    def call(number, method, params):
        send({"id": number, "method": method, "params": params})
        while True:
            message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if message.get("reader_closed"):
                raise RuntimeError("Codex discovery process closed")
            if message.get("id") == number:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message["result"]

    try:
        info = call(1, "initialize", {"clientInfo": {"name": "skill_catalog", "version": "1.0.0"}})
        send({"method": "initialized"})
        result = call(2, method, params)
        return result, info.get("userAgent")
    except queue.Empty as error:
        raise TimeoutError("Codex не ответил вовремя.") from error
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            stream.close()
        worker.join(timeout=1)


def discover(cwds: list[str], explicit: str | None = None, timeout: float = 35) -> dict:
    result, client = request("skills/list", {"cwds": cwds, "forceReload": True}, explicit, timeout)
    return {"data": result["data"], "client": client}
