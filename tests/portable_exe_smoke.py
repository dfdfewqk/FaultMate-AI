"""Validate the compiled Windows EXE, not a Python source launch.

The executable is started from a separate working directory with no DeepSeek
key. This test checks loopback-only service responses and that unapproved ML
and external AI execution remain off. It does not start ML training.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch(base: str, path: str, payload: dict | None = None):
    raw = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(base + path, data=raw,
                      headers={"Content-Type": "application/json"} if raw is not None else {})
    with urlopen(request, timeout=4) as res:
        return res.status, res.read(), res.headers


def check(exe: Path):
    if os.name != "nt":
        raise AssertionError("Compiled Windows EXE check requires Windows")
    if not exe.is_file():
        raise AssertionError("Compiled executable not found")
    installed = exe.parent
    if not (installed / "_internal").is_dir():
        raise AssertionError("PyInstaller one-directory dependencies missing")
    for pattern in ("*.rar", "*.mat", ".env", "bearing_validated.json"):
        forbidden = list(installed.rglob(pattern))
        if forbidden:
            raise AssertionError(f"Forbidden raw data/key/model bundled: {pattern}")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    env["FAULTMATE_PORT"] = str(port)
    env["FAULTMATE_NO_BROWSER"] = "1"
    with tempfile.TemporaryDirectory(prefix="faultmate-compiled-smoke-") as work:
        log_path = Path(work) / "app.log"
        with log_path.open("wb") as output:
            proc = subprocess.Popen([str(exe)], cwd=work, env=env,
                                    stdout=output, stderr=subprocess.STDOUT)
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    if proc.poll() is not None:
                        raise AssertionError(f"EXE exited before server ready: {proc.returncode}")
                    try:
                        status, body, _ = fetch(base, "/api/status")
                        data = json.loads(body)
                        if status == 200 and data.get("app") == "FaultMate AI":
                            break
                    except (OSError, URLError, ValueError):
                        pass
                    time.sleep(.4)
                else:
                    raise AssertionError("Compiled EXE did not serve the local API")
                assert data["ui_release"] == "P7.2-Final"
                assert data["external_transfer"] is False
                for path, marker in (
                    ("/", b"triage-submit"),
                    ("/assets/app.js", b"agentPreviewButton"),
                    ("/assets/style.css", b"triage"),
                ):
                    code, body, _ = fetch(base, path)
                    assert code == 200 and marker in body, path
                code, body, _ = fetch(base, "/api/knowledge/cases")
                assert code == 200 and len(json.loads(body)["cases"]) >= 1
                code, body, _ = fetch(base, "/api/diagnostics/options")
                assert code == 200 and body
                code, body, _ = fetch(base, "/api/integration/capabilities")
                assert code == 200
                capabilities = json.loads(body)
                assert capabilities["ml"]["inference_enabled"] is False
                assert capabilities["agent"]["configured"] is False
                assert capabilities["agent"]["connected"] is False
                triage = {"case_id": "CONV-001", "emergency_hazard": "yes"}
                code, body, headers = fetch(base, "/api/diagnostics/evaluate", triage)
                assert code == 200
                decision = json.loads(body)
                assert decision["state"] == "safety_hold"
                assert decision.get("confirmed_fault") is not True
                assert decision.get("safe_to_work") is not True
                assert "no-store" in headers.get("Cache-Control", "")
                code, body, _ = fetch(base, "/api/agent/review",
                                      {"triage": triage, "consent": True})
                ai = json.loads(body)
                assert code == 200 and ai["status"] == "blocked"
                assert ai["external_transfer_performed"] is False
                print("PORTABLE_EXE_PASS: local UI/API, case catalog, ML gate, hazard hold, no external transfer")
            except Exception:
                output.flush()
                print(log_path.read_text(encoding="utf-8", errors="replace")[-9000:],
                      file=sys.stderr)
                raise
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--exe", required=True, type=Path)
    args = p.parse_args()
    check(args.exe.absolute())
