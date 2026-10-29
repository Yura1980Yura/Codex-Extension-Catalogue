"""Run the pinned Meshy MCP package with a key read from Windows Credential Manager."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"skill-catalog/scripts"))
from platform_paths import codex_dir
import windows_credentials as vault


class BasicLimit(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]


class IOCount(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimit(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IOCount),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def child_job():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    api.SetInformationJobObject.restype = wintypes.BOOL
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.AssignProcessToJobObject.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    job = api.CreateJobObjectW(None, None)
    limits = ExtendedLimit()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    if not job or not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        if job:
            api.CloseHandle(job)
        raise RuntimeError("Cannot create Meshy process job")
    return api, job


def main():
    base = codex_dir()/"service-connectors/meshy"
    try:
        setup = json.loads((base/"connection.json").read_text("utf-8"))
        key = vault.read()
        if not key:
            print("Meshy API key is not configured. Open the local catalogue form.", file=sys.stderr)
            return 2
        runtime = base/"runtime/node_modules/@meshy-ai/meshy-mcp-server"
        package = json.loads((runtime/"package.json").read_text("utf-8"))
        if package.get("version") != "0.6.6":
            raise RuntimeError("Unexpected Meshy package version")
        environment = dict(os.environ)
        environment.pop("NODE_OPTIONS", None)
        environment.update(MESHY_API_KEY=key, MESHY_API_HOST="https://api.meshy.ai", TRANSPORT="stdio", DOTENV_CONFIG_QUIET="true")
        api, job = child_job()
        child = None
        try:
            child = subprocess.Popen([setup["node_path"], str(runtime/"dist/index.js")], cwd=base/"workspace", env=environment, stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            if not api.AssignProcessToJobObject(job, wintypes.HANDLE(int(child._handle))):
                raise RuntimeError("Cannot supervise Meshy child process")
            def errors():
                for line in child.stderr:
                    sys.stderr.buffer.write(line.replace(key.encode(), b"[REDACTED]"))
                    sys.stderr.buffer.flush()
            worker = threading.Thread(target=errors, daemon=True)
            worker.start()
            result = child.wait()
            worker.join(timeout=1)
            return result
        finally:
            api.CloseHandle(job)
            if child and child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
    except Exception:
        # A raw exception from a request or process can expose environment values.
        print("Meshy launcher failed. Check the connection in the local catalogue.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
