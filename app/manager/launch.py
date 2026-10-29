"""Open the existing loopback manager, or start its hidden process once."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT/".local/manager.json"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"skill-catalog/scripts"))
from platform_paths import codex_dir

DATA_ID = hashlib.sha256(str((codex_dir()/"skill-catalog").resolve()).encode()).hexdigest()


def running():
    try:
        state = json.loads(STATE.read_text("utf-8"))
        from urllib.parse import urlsplit
        parsed = urlsplit(state["url"])
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path or state.get("data_id") != DATA_ID:
            return None
        with urllib.request.urlopen(state["url"]+"/api/health", timeout=1) as response:
            health = json.load(response)
        if health.get("app") == "codex-skill-catalog-manager-v1" and health.get("data_id") == DATA_ID:
            return state["url"]
    except (OSError, ValueError, KeyError):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    url = running()
    if not url:
        STATE.parent.mkdir(exist_ok=True)
        with (STATE.parent/"manager.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, "-X", "utf8", "-B", str(ROOT/"manager/server.py")], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(60):
            url = running()
            if url: break
            if process.poll() is not None: break
            time.sleep(.15)
    if not url:
        raise SystemExit("Менеджер не запустился. Подробности в .local/manager.log")
    if not args.no_browser:
        webbrowser.open(url)
    print(url)
