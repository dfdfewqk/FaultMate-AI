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
        # Savemat creates the same kind of MATLAB Name/Data/Unit records.
        signals = np.empty((1, 2), dtype=object)
        for i, (name, values, unit) in enumerate([
            ("vibration_1", np.linspace(-2, 2, 32), "m/s²"),
            ("phase_current_1", np.linspace(-4, 4, 32), "A"),
        ]):
            signals[0, i] = {"Name": name, "Data": values, "Unit": unit}
        savemat(self.mat, {"N15_M07_F10_K001_1": {"Y": signals}})

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
        self.metadata.write_text(json.dumps({
            "source_sha256": hashlib.sha256(self.mat.read_bytes()).hexdigest(),
            "vibration_channel": "vibration_1", "current_channel": "phase_current_1",
            "vibration_unit": "m/s²", "current_unit": "A",
            "unit_evidence": "Human-reviewed official sensor calibration page, section 3",
        }), encoding="utf-8")
        result = self.run_converter("--unit-manifest", str(self.metadata))
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
        result = self.run_converter("--unit-manifest", str(self.metadata))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash_mismatch", result.stderr)

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