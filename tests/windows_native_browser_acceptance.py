"""Native Windows localhost end-to-end acceptance: ACTUAL .bat and Chromium.

Unlike Linux's in-process Playwright/TestClient browser checks, the browser
here loads the REAL uvicorn server over TCP after the ORIGINAL start_windows.bat
runs on Windows. This is an unattended GitHub Windows runner acceptance test,
NOT evidence that the user's personal PC has run it.

- Temporary process/log only; no source files, SQLite, install or packaging.
- Never uses DEEPSEEK_API_KEY; agent remains unconfigured, no paid AI call.
- Real local triage, optional AI preview+consent (no-transfer), ML no-go,
  emergency hold, knowledge navigation, cross-origin HTTP rejection, shutdown.
- Test-only Playwright/Chromium may be installed on a clean CI runner.

Usage on a Windows runner after setup_windows.bat and playwright installation:
    .venv\Scripts\python.exe tests/windows_native_browser_acceptance.py
"""
from __future__ import annotations

import asyncio
from contextlib import closing
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

ROOT = Path(__file__).resolve().parents[1]
# Running this script directly from tests/ does not put the repository's
# scripts/ package on sys.path; keep source fixtures and production isolated.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def available_local_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request_json(base: str, path: str, *, body: dict | None = None,
                 extra_headers: dict | None = None) -> tuple[int, dict]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if raw is not None else {}
    headers.update(extra_headers or {})
    req = Request(base + path, data=raw, headers=headers)
    try:
        with urlopen(req, timeout=3) as res:
            return res.status, json.loads(res.read(50_000))
    except HTTPError as exc:
        with exc:
            return exc.code, json.loads(exc.read(5000))


def wait_for_live_server(process, base: str) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise AssertionError(f"original Windows batch terminated: {process.returncode}")
        try:
            status, report = request_json(base, "/api/status")
            if (status == 200 and report.get("app") == "FaultMate AI"
                and report.get("ui_release") == "P7.2-Final"):
                return
        except (OSError, URLError, ValueError):
            pass
        time.sleep(0.2)
    raise AssertionError("original Windows batch did not serve a real TCP localhost app")


async def exercise_real_windows_chromium(base: str) -> dict:
    from playwright.async_api import async_playwright

    issues: list[str] = []
    touched: list[tuple[str, str]] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                accept_downloads=False,
                service_workers="block",
            )
            page = await context.new_page()
            page.set_default_timeout(12_000)
            page.on("pageerror", lambda err: issues.append(str(err)))
            page.on("request", lambda req: touched.append((req.method, req.url)))
            response = await page.goto(base + "/", wait_until="domcontentloaded",
                                       timeout=20_000)
            assert response is not None and response.status == 200
            await page.wait_for_function(
                "document.querySelector('#status').textContent.includes('로컬 서버 연결 정상')")

            assert await page.title() == "FaultMate AI · 설비 고장 진단"
            await page.locator("#triage-equipment").select_option("컨베이어")
            await page.locator("#triage-symptom").fill(
                "PRIVATE_WIN_NATIVE_SYMPTOM_NEVER_SEND")
            await page.locator("#triage-more summary").click()
            await page.locator("#triage-model").fill("PRIVATE_EQUIPMENT_ID")
            await page.locator("#triage-alarm").fill("PRIVATE_ALARM_LOG")
            await page.locator("#triage-case").select_option("CONV-001")
            await page.locator('select[data-key="visible_jam"]').select_option("yes")
            await page.locator("#triage-submit").click()
            await page.locator("#triage-result .result-cause").first.wait_for()
            diagnosis_text = await page.locator("#triage-result").inner_text()
            assert "고장 원인을 확정하지 않았습니다" in diagnosis_text

            await page.locator("#integration-panel summary").click()
            assert "미연결" in await page.locator("#integration-ml").inner_text()
            assert await page.locator("#agent-run").is_disabled()
            await page.locator("#agent-preview").click()
            await page.locator("#agent-preview-content:not([hidden])").wait_for()
            preview = await page.locator("#agent-preview-content").inner_text()
            assert "CONV-001" in preview
            for forbidden in ("PRIVATE_WIN_NATIVE_SYMPTOM_NEVER_SEND",
                              "PRIVATE_EQUIPMENT_ID", "PRIVATE_ALARM_LOG"):
                assert forbidden not in preview, "private input reached external preview"
            assert await page.locator("#agent-run").is_disabled()

            # Even with an explicit per-request UI consent, NO API key exists.
            # The local app must report no external transfer and clear consent.
            await page.locator("#agent-consent").check()
            assert await page.locator("#agent-run").is_enabled()
            await page.locator("#agent-run").click()
            await page.wait_for_function(
                "document.querySelector('#agent-feedback').textContent.includes('외부 AI 전송 없음')")
            assert "API 키" in await page.locator("#agent-result").inner_text()
            assert await page.locator("#agent-run").is_disabled()
            assert not await page.locator("#agent-consent").is_checked()

            await page.locator("#ml-upload").set_input_files({
                "name": "synthetic_shape_sample.csv", "mimeType": "text/csv",
                "buffer": (
                    b"asset_id,trial_id,source_id,vibration_rms_m_s2,"
                    b"vibration_peak_m_s2,current_rms_a\n"
                    b"K001,T1,paderborn-bearing-datacenter,1.0,2.0,0.5\n"
                ),
            })
            await page.locator("#ml-run").click()
            await page.wait_for_function(
                "document.querySelector('#ml-feedback').textContent.includes('검증된')")
            assert "모델이 없으므로" in await page.locator("#ml-feedback").inner_text()
            assert not (await page.locator("#ml-result").inner_text()).strip()

            # Separate EXPERIMENTAL ML path: synthetic 4x20 unitless features
            # exercise a real model score in the actual Windows web browser.
            # This fixture is NOT independently verified original sensor data;
            # the real original K001 source is checked by its own CI job.
            from test_experimental_paderborn_real_inference import fake_source_feature_report
            await page.locator("#research-json-advanced summary").click()
            await page.locator("#research-upload").set_input_files({
                "name": "synthetic_80_record_research.json",
                "mimeType": "application/json",
                "buffer": json.dumps(fake_source_feature_report()).encode("utf-8"),
            })
            assert await page.locator("#research-run").is_enabled()
            await page.locator("#research-run").click()
            await page.wait_for_function(
                "document.querySelector('#research-result').textContent.includes('미승인 실험 결과')")
            research_text = await page.locator("#research-result").inner_text()
            assert "손상 판별 점수" in research_text
            assert "원본 측정파일의 진위를 검증할 수 없습니다" in research_text
            assert "현장 고장 확률" in research_text

            # Direct original RAR route is separate and no fake small upload
            # can be presented as verified original Paderborn sensor data.
            await page.locator("#raw-rar-upload").set_input_files({
                "name": "K001.rar", "mimeType": "application/octet-stream",
                "buffer": b"NOT_AN_ORIGINAL_100_MB_RAR",
            })
            assert await page.locator("#raw-rar-run").is_enabled()
            await page.locator("#raw-rar-run").click()
            await page.wait_for_function(
                "document.querySelector('#raw-rar-feedback').textContent.includes('100MB')")
            assert not (await page.locator("#raw-rar-result").inner_text()).strip()

            # Safety-hold must hide stale results and disable both optional AI/ML.
            await page.locator("#triage-hazard").select_option("yes")
            assert await page.locator("#agent-preview").is_disabled()
            assert await page.locator("#agent-run").is_disabled()
            assert await page.locator("#ml-run").is_disabled()
            assert await page.locator("#research-run").is_disabled()
            assert await page.locator("#raw-rar-run").is_disabled()
            assert not (await page.locator("#raw-rar-result").inner_text()).strip()
            assert not (await page.locator("#research-result").inner_text()).strip()
            assert "긴급 위험 징후" in await page.locator("#triage-result").inner_text()

            await page.locator("#knowledge-panel summary").click()
            await page.wait_for_function(
                "document.querySelectorAll('button.knowledge-item').length===7")
            assert await page.locator("button.knowledge-item").count() == 7

            # Actual browser used the HTTP listener, not an in-process TestClient.
            assert any(method == "POST" and url.endswith("/api/diagnostics/evaluate")
                       for method, url in touched)
            assert any(method == "POST" and url.endswith("/api/agent/review")
                       for method, url in touched)
            assert any(method == "POST" and url.endswith("/api/ml/inspect")
                       for method, url in touched)
            assert any(method == "POST" and url.endswith("/api/ml/experimental-unitless-report")
                       for method, url in touched)
            assert all(url.startswith(base + "/") for _, url in touched), touched
            assert not issues, issues
            await context.close()
        finally:
            await browser.close()

    return {
        "browser": "native_windows_playwright_chromium",
        "live_localhost_http": True,
        "frontend_real_http_post_calls": len([
            m for m, _ in touched if m == "POST"
        ]),
        "user_data_transferred_to_paid_provider": False,
        "unapproved_bearing_ml_inference": False,
        "safety_hold_verified": True,
        "js_errors": len(issues),
    }


def run() -> dict:
    if os.name != "nt":
        raise RuntimeError("Windows native acceptance must run on Windows")
    launcher = ROOT / "start_windows.bat"
    interpreter = ROOT / ".venv" / "Scripts" / "python.exe"
    assert launcher.is_file() and interpreter.is_file()
    port = available_local_port()
    base = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.pop("DEEPSEEK_API_KEY", None)
    environment.pop("FAULTMATE_LIVE_TEST_APPROVED", None)
    environment["FAULTMATE_NO_BROWSER"] = "1"
    environment["FAULTMATE_PORT"] = str(port)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    with tempfile.TemporaryDirectory(prefix="faultmate-win-native-") as tmp:
        # A child process starts from a completely unrelated working directory,
        # so the original batch must resolve paths from its own location.
        log = Path(tmp) / "windows_server.log"
        with log.open("wb") as stream:
            proc = subprocess.Popen(
                ["cmd.exe", "/d", "/c", str(launcher)],
                cwd=tmp, env=environment,
                stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            try:
                wait_for_live_server(proc, base)
                code, caps = request_json(base, "/api/integration/capabilities")
                assert code == 200 and caps["agent"]["configured"] is False
                assert caps["ml"]["inference_enabled"] is False

                # Cross-site and DNS-rebinding guard checked over the *real*
                # HTTP listener rather than mocked request headers in TestClient.
                attacker_code, attacker = request_json(
                    base, "/api/integration/evidence-preview",
                    body={"triage": {"case_id": "CONV-001"}},
                    extra_headers={"Origin": "http://attacker.invalid"},
                )
                assert attacker_code == 403
                assert attacker["detail"] == "local_same_origin_required"
                host_code, host_report = request_json(
                    base, "/api/status",
                    extra_headers={"Host": "attacker.invalid"},
                )
                assert host_code == 403
                assert host_report["detail"] == "local_same_origin_required"

                browser_report = asyncio.run(exercise_real_windows_chromium(base))
                report = {
                    "schema": "faultmate_windows_runner_native_browser_acceptance_v1",
                    "status": "WINDOWS_NATIVE_BROWSER_E2E_PASS",
                    "actual_windows_batch_started": True,
                    "original_server_bound_loopback": True,
                    "original_windows_user_pc_tested": False,
                    "native_browser": browser_report,
                    "foreign_origin_post_blocked_http403": True,
                    "foreign_host_blocked_http403": True,
                    "deepseek_key_unset": True,
                    "paid_deepseek_requests_performed": 0,
                    "user_records_changed": False,
                    "package_created": False,
                }
                return report
            except BaseException:
                stream.flush()
                print("Windows native runner failure; original batch log tail:\n"
                      + log.read_text(encoding="utf-8", errors="replace")[-5000:],
                      file=sys.stderr)
                raise
            finally:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, check=False, timeout=12,
                )
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=8)
                # Verify the independent Windows server listener has stopped;
                # none of the API endpoints should remain running after QA.
                for _ in range(20):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.2):
                            time.sleep(.1)
                    except OSError:
                        break
                else:
                    raise AssertionError("Windows acceptance left a server listening")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
