"""Evaluation JSON stays UTF-8, ASCII-escaped, and readable on cp949 Windows.

Synthetic data is for contract tests only, not genuine predictive accuracy.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.train_ml import train

FIELDS = (
    "asset_id", "trial_id", "source_id", "vibration_rms_m_s2",
    "vibration_peak_m_s2", "current_rms_a", "label", "label_provenance", "license",
)
NOTE = "교육용 실험 데이터 평가. 현장 안전·고장 예측 성능 보증 아님."


def _write_synthetic_fixture(target: Path) -> None:
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for prefix, label, scale in (("H", "healthy", 1.), ("D", "damaged", 4.)):
            for asset_num in range(6):
                for trial_num in range(2):
                    value = scale + trial_num * .02
                    writer.writerow({
                        "asset_id": f"{prefix}{asset_num}",
                        "trial_id": f"trial_{trial_num}",
                        "source_id": "synthetic_test_only",
                        "vibration_rms_m_s2": value,
                        "vibration_peak_m_s2": value * 1.5,
                        "current_rms_a": value / 3,
                        "label": label,
                        "label_provenance": f"synthetic_fixture_{prefix}{asset_num}",
                        "license": "test-only",
                    })


def test_training_outputs_are_valid_utf8_and_cp949_decodable_ascii_json(tmp_path):
    input_csv = tmp_path / "fixture.csv"
    _write_synthetic_fixture(input_csv)
    output_dir = tmp_path / "new_evaluation"
    train(input_csv, output_dir, test_fixture_only=True)

    before = {}
    for name in ("evaluation_report.json", "bearing_evaluated.json"):
        target = output_dir / name
        raw = target.read_bytes()
        before[name] = raw
        assert raw.isascii(), f"Non-ASCII output in {name} breaks Windows cp949 compatibility"
        utf8_result = json.loads(raw.decode("utf-8"))
        cp949_result = json.loads(raw.decode("cp949"))
        assert utf8_result == cp949_result
        assert raw.endswith(b"\n")

    report = json.loads(before["evaluation_report.json"].decode("cp949"))
    assert report["note"] == NOTE  # Detect mojibake; ASCII-safe JSON alone is insufficient.
    assert report["license"] == "test-only"
    assert report["source_id"] == "synthetic_test_only"
    model = json.loads(before["bearing_evaluated.json"].decode("utf-8"))
    assert model["status"] == "evaluated_pending_review"

    with pytest.raises(ValueError, match="evaluation_artifacts_already_exist"):
        train(input_csv, output_dir, test_fixture_only=True)
    assert {p.name: p.read_bytes() for p in output_dir.iterdir()} == before
