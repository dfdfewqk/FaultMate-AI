"""Consolidated cleanup gate: preserve live app, evidence, and five-job CI.

Previous short-lived workflow files are retired ONLY from the new review
branch; historical Git commits and original study manifests remain intact.
No deletion or provider request occurs when this test runs.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

RETIRED_HISTORICAL_BRANCH_ONLY_CI = (
    "calibration-safety.yml",
    "cohort-coverage-safety.yml",
    "faultmate-ml-integrity.yml",
    "faultmate-regression.yml",
    "preintegration-cleanup-regression.yml",
    "stage6-program-integration.yml",
    "stage7-local-api-boundary.yml",
    "stage7-source-readiness-regression.yml",
    "stage7-windows-native-browser-acceptance.yml",
    "windows-integration.yml",
    "validate-k001.yml",
)

MUST_KEEP = (
    "faultmate/app.py",
    "faultmate/diagnostics/engine.py",
    "faultmate/knowledge/catalog.json",
    "faultmate/integration/agent.py",
    "faultmate/integration/context.py",
    "faultmate/integration/ml.py",
    "faultmate/integration/research_raw_archive.py",
    "web/app.js", "web/index.html", "web/style.css",
    "setup_windows.bat", "start_windows.bat",
    "docs/PADERBORN_TRAINING_ASSETS.json",
    "docs/experiments/PADERBORN_REAL_UNITLESS_MODEL_UNAPPROVED_20261105.json",
    "docs/FINAL_CONSOLIDATED_INTEGRATION_REVIEW_20261106.md",
    "scripts/audit_paderborn_raw_recordings.py",
    "scripts/train_paderborn_unitless.py",
    "scripts/verify_k001_archive.py",
    "scripts/optional_deepseek_one_call_acceptance.py",
    "tests/browser_stage6_integrated.py",
    "tests/windows_native_browser_acceptance.py",
    "tests/test_ai_review_evidence_display_contract.py",
    "tests/test_existing_deepseek_key_presence.py",
    ".github/workflows/official-paderborn-12-full-audit.yml",
    ".github/workflows/recombine-12-raw-audits.yml",
    ".github/workflows/real-paderborn-unitless-ml.yml",
)


def test_only_superseded_historical_ci_paths_removed():
    assert len(RETIRED_HISTORICAL_BRANCH_ONLY_CI) == 11
    for name in RETIRED_HISTORICAL_BRANCH_ONLY_CI:
        assert not (WORKFLOWS / name).exists(), name
    for path in MUST_KEEP:
        assert (ROOT / path).is_file(), path


def test_one_current_five_job_acceptance_gate_remains():
    path = WORKFLOWS / "stage7-known-damaged-ki21-replay.yml"
    content = path.read_text(encoding="utf-8")
    for job in (
        "name: Linux complete Python + source compatibility + real local HTTP",
        "name: Windows whole Python + real batch start + no API transfer",
        "name: Chromium full P7.2 UI + attempted transfer warning and mocked agent",
        "name: REAL K001 original MD5 RAR > 80 MAT > 12 features > frozen research ML score",
        "name: REAL previously opened damaged KI21 original RAR -> app known false-negative safety check",
    ):
        assert job in content, job
    assert "work/faultmate-p7-final-pr40-44-consolidation-cleanup-20261106" in content
    assert "      - main" in content
