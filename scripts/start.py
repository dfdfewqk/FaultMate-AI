"""Single-host launcher: handles CWD, port conflicts, readiness and browser opening."""
from __future__ import annotations
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"

def load_app():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from faultmate.app import app
    return app

def choose_port(preferred: int = 8787) -> int:
    if not 1 <= preferred <= 65535:
        raise ValueError("Invalid local port")
    for candidate in (preferred, 0):
        with socket.socket() as sock:
            try:
                sock.bind((HOST, candidate))
                return sock.getsockname()[1]
            except OSError:
                if candidate == 0:
                    raise
    raise RuntimeError("No free loopback port")

def open_when_ready(url: str, attempts=60, interval=.25):
    for _ in range(attempts):
        try:
            with urlopen(url + "/api/status", timeout=.6) as resp:
                if resp.status == 200 and b'"app":"FaultMate AI"' in resp.read(4096):
                    webbrowser.open(url)
                    return True
        except OSError:
            pass
        time.sleep(interval)
    print("[INFO] Browser not opened automatically. Visit " + url, flush=True)
    return False

def main():
    try:
        preferred = int(os.getenv("FAULTMATE_PORT", "8787"))
        port = choose_port(preferred)
        application = load_app()
    except (ValueError, OSError, RuntimeError) as exc:
        print("[ERROR] Failed to prepare local server: " + str(exc), file=sys.stderr)
        return 2
    url = f"http://{HOST}:{port}"
    print("[FaultMate AI / P7.2 local diagnostics + optional AI-ML] " + url, flush=True)
    print("[INFO] Press Ctrl+C to stop the server.", flush=True)
    if os.getenv("FAULTMATE_NO_BROWSER") != "1":
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(application, host=HOST, port=port, reload=False, access_log=False)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
