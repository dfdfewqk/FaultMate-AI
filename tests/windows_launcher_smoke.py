"""Windows-only launch smoke: real .bat -> Python -> localhost API.

Exercise the existing P7.2 launcher, not a new startup implementation.
No DeepSeek network call, ML training, model activation, or persistent data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def api(base: str, path: str, payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(base + path, data=data,
                  headers={"Content-Type": "application/json"} if data else {})
    with urlopen(req, timeout=3) as response:
        return response.status, response.read(), response.headers


def run() -> None:
    if os.name != "nt":
        raise SystemExit("This test must be run on Windows.")
    launcher = ROOT / "start_windows.bat"
    if not launcher.is_file():
        raise AssertionError("Windows launch batch missing")
    if not (ROOT / ".venv" / "Scripts" / "python.exe").is_file():
        raise AssertionError("Prepare the isolated test .venv with setup_windows.bat first")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    env.update({"FAULTMATE_PORT": str(port), "FAULTMATE_NO_BROWSER": "1"})
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="faultmate-windows-smoke-") as tmp:
        log_path = Path(tmp) / "launch.log"
        with log_path.open("wb") as output:
            process = subprocess.Popen(
                ["cmd.exe", "/d", "/c", str(launcher)],
                cwd=tmp, env=env, stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise AssertionError(f"Launcher exited unexpectedly: {process.returncode}")
                    try:
                        code, body, _ = api(base, "/api/status")
                        if code == 200:
                            status = json.loads(body)
                            if status.get("app") == "FaultMate AI":
                                break
                    except (OSError, ValueError, URLError):
                        pass
                    time.sleep(0.2)
                else:
                    raise AssertionError("Windows batch did not start a responsive local server")

                assert status["ui_release"] == "P7.2-Final", status
                assert status["phase"] == "P2", status
                code, html, _ = api(base, "/")
                assert code == 200 and b"triage-submit" in html

                code, raw, _ = api(base, "/api/integration/capabilities")
                assert code == 200
                caps = json.loads(raw)
                assert caps["ml"]["inference_enabled"] is False
                assert caps["agent"]["configured"] is False

                emergency = {"case_id": "CONV-001", "emergency_hazard": "yes"}
                code, raw, headers = api(base, "/api/diagnostics/evaluate", emergency)
                assert code == 200
                assert json.loads(raw)["state"] == "safety_hold"
                assert "no-store" in headers.get("Cache-Control", "")

                code, raw, _ = api(base, "/api/agent/review",
                                   {"triage": emergency, "consent": True})
                assert code == 200
                blocked = json.loads(raw)
                assert blocked["status"] == "blocked"
                assert blocked["external_transfer_performed"] is False

                print("WINDOWS_BATCH_LAUNCH_PASS: P7.2 status, UI, ML gate, safety hold, no AI transfer")
            except Exception:
                output.flush()
                print("Windows launcher failure; process output:\n" +
                      log_path.read_text(encoding="utf-8", errors="replace")[-6000:],
                      file=sys.stderr)
                raise
            finally:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, check=False, timeout=10)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)


if __name__ == "__main__":
    run()
