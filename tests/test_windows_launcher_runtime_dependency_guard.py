"""Windows launcher static dependency-regression gate.

This is NOT a user-PC acceptance run; the CI Windows job separately executes
start_windows.bat with native Chromium over real localhost TCP.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_existing_virtualenv_guard_checks_all_runtime_modules():
    launcher = (ROOT / "start_windows.bat").read_text(
        encoding="utf-8-sig")
    installer = (ROOT / "setup_windows.bat").read_text(
        encoding="utf-8-sig")
    requirements = (ROOT / "requirements.txt").read_text(
        encoding="utf-8-sig")
    # A stale P7.2 venv can have FastAPI installed but no numpy/scipy.
    # The previous import check would skip the installer in that state,
    # breaking the already-implemented original-RAR research ML button.
    assert '"import fastapi,uvicorn,pydantic,numpy,scipy"' in launcher
    assert "call \"%~dp0setup_windows.bat\" --auto" in launcher
    assert "if errorlevel 1 goto failed" in launcher
    assert '-r \"%~dp0requirements.txt\"' in installer
    for required in ("fastapi", "uvicorn", "pydantic", "numpy", "scipy"):
        assert any(line.startswith(required) for line in requirements.splitlines())
