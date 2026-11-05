"""Synthetic-only contract tests. No fabricated data used for reported ML metrics."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scipy.io import savemat

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "convert_mat_to_csv.py"


class MatConverterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mat = self.root / "N15_M07_F10_K001_1.mat"
        self.output = self.root / "record.csv"
        self.metadata = self.root / "units.json"
        self.evidence = self.root / "fixture-calibration.txt"
        self.evidence.write_text(
            "SYNTHETIC FIXTURE ONLY. This is NOT evidence for Paderborn's real units. " * 4,
            encoding="utf-8",
        )
        # Savemat creates the same kind of MATLAB Name/Data/Unit records.
        signals = np.empty((1, 2), dtype=object)
        for i, (name, values, unit) in enumerate([
            ("vibration_1", np.linspace(-2, 2, 32), "m/s²"),
            ("phase_current_1", np.linspace(-4, 4, 32), "A"),
        ]):
            signals[0, i] = {"Name": name, "Data": values, "Unit": unit}
        savemat(self.mat, {"N15_M07_F10_K001_1": {"Y": signals}})

    def synthetic_review_manifest(self):
        # Test fixture proving software gates, not evidence of real Paderborn SI units.
        return {
            "source_sha256": hashlib.sha256(self.mat.read_bytes()).hexdigest(),
            "vibration_channel": "vibration_1", "current_channel": "phase_current_1",
            "vibration_unit": "m/s²", "current_unit": "A",
            "stored_mat_values_calibration_verified": True,
            "evidence_document_sha256": hashlib.sha256(self.evidence.read_bytes()).hexdigest(),
            "evidence_type": "primary_dataset_documentation",
            "evidence_url": "https://example.org/synthetic-fixture-only",
            "evidence_location": "synthetic section 1",
            "unit_evidence": "Synthetic hypothetical calibration of stored numerical MAT sample values; not a real source",
            "reviewed_by": "synthetic_test_reviewer",
            "reviewed_utc": "2026-11-05T00:00:00+00:00",
            "vibration_scale_to_m_s2": 1.0,
            "current_scale_to_a": 1.0,
        }

    def run_converter(self, *args):
        base = [sys.executable, str(SCRIPT), "--mat", str(self.mat),
                "--asset-id", "K001", "--trial-id", "N15_M07_F10_1",
                "--source-id", "paderborn-bearing-datacenter", "--label", "healthy",
                "--label-provenance", "official Paderborn K001 health table",
                "--output", str(self.output)]
        return subprocess.run(base + list(args), text=True, capture_output=True)

    def test_nested_record_converts_and_matches_columns(self):
        result = self.run_converter()
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.output.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_id"], "K001")
        self.assertEqual(rows[0]["trial_id"], "N15_M07_F10_1")
        self.assertEqual(rows[0]["source_id"], "paderborn-bearing-datacenter")
        self.assertEqual(rows[0]["license"], "CC BY-NC 4.0")
        self.assertAlmostEqual(float(rows[0]["vibration_peak_m_s2"]), 2.0)

    def test_missing_current_fails_without_writing_csv(self):
        savemat(self.mat, {"vibration_1": np.arange(32, dtype=float)})
        result = self.run_converter()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing_required_channel", result.stderr)
        self.assertFalse(self.output.exists())

    def test_wrong_label_fails(self):
        result = self.run_converter("--label", "damaged")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_missing_units_fails_closed(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        result = self.run_converter()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unit_metadata_missing", result.stderr)
        self.assertFalse(self.output.exists())

    def test_hash_bound_reviewed_units_for_missing_mat_units(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        self.metadata.write_text(json.dumps(self.synthetic_review_manifest()), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata),
                                    "--unit-evidence-document", str(self.evidence))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.output.is_file())

    def test_unit_manifest_wrong_hash_fails(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        self.metadata.write_text(json.dumps({
            "source_sha256": "0" * 64,
            "vibration_channel": "vibration_1", "current_channel": "phase_current_1",
            "vibration_unit": "m/s²", "current_unit": "A", "unit_evidence": "fake evidence document",
        }), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata),
                                    "--unit-evidence-document", str(self.evidence))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash_mismatch", result.stderr)

    def test_legacy_manifest_with_unverified_free_text_still_fails_closed(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        self.metadata.write_text(json.dumps({
            "source_sha256": hashlib.sha256(self.mat.read_bytes()).hexdigest(),
            "vibration_channel": "vibration_1", "current_channel": "phase_current_1",
            "vibration_unit": "m/s²", "current_unit": "A",
            "unit_evidence": "Unsupported claim that raw values are calibrated.",
        }), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unit_evidence_document_required", result.stderr)
        self.assertFalse(self.output.exists())

    def test_source_document_hash_mismatch_does_not_create_csv(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        manifest = self.synthetic_review_manifest()
        manifest["evidence_document_sha256"] = "f" * 64
        self.metadata.write_text(json.dumps(manifest), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata),
                                    "--unit-evidence-document", str(self.evidence))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unit_evidence_document_hash_mismatch", result.stderr)
        self.assertFalse(self.output.exists())

    def test_review_with_missing_stored_numeric_calibration_fails(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.arange(32, dtype=float), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        manifest = self.synthetic_review_manifest()
        manifest["stored_mat_values_calibration_verified"] = False
        self.metadata.write_text(json.dumps(manifest), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata),
                                    "--unit-evidence-document", str(self.evidence))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stored_numeric_calibration_not_verified", result.stderr)
        self.assertFalse(self.output.exists())

    def test_hypothetical_source_bound_scaling_applies_to_values_not_just_names(self):
        signals = np.empty((1, 2), dtype=object)
        signals[0, 0] = {"Name": "vibration_1", "Data": np.linspace(-1, 1, 32), "Unit": ""}
        signals[0, 1] = {"Name": "phase_current_1", "Data": np.linspace(-2, 2, 32), "Unit": ""}
        savemat(self.mat, {"Y": signals})
        manifest = self.synthetic_review_manifest()
        manifest["vibration_scale_to_m_s2"] = 2.0
        manifest["current_scale_to_a"] = 3.0
        self.metadata.write_text(json.dumps(manifest), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata),
                                    "--unit-evidence-document", str(self.evidence))
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.output.open(encoding="utf-8", newline="") as source:
            actual = list(csv.DictReader(source))[0]
        self.assertAlmostEqual(float(actual["vibration_peak_m_s2"]), 2.0)
        self.assertAlmostEqual(float(actual["current_rms_a"]),
                               float(np.sqrt(np.mean(np.linspace(-2, 2, 32) ** 2))) * 3.0)

    def test_inspection_only(self):
        result = self.run_converter("--inspect")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("vibration_1", result.stdout)
        self.assertFalse(self.output.exists())

    def test_existing_csv_not_overwritten(self):
        self.output.write_text("PREEXISTING", encoding="utf-8")
        result = self.run_converter()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "PREEXISTING")


if __name__ == "__main__":
    unittest.main()