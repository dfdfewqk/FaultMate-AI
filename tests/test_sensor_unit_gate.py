"""Synthetic fixtures only: these tests do NOT validate real Paderborn calibration."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sensor_unit_gate.py"
spec = importlib.util.spec_from_file_location("sensor_unit_gate", MODULE_PATH)
gate = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(gate)


class UnitEvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mat = self.root / "N15_M07_F10_K001_1.mat"
        self.mat.write_bytes(b"TEST ONLY NOT A REAL MAT")
        self.document = self.root / "recorded_calibration.txt"
        self.document.write_text("synthetic chain fixture for tests only", encoding="utf-8")
        proof = {
            "file": self.document.name,
            "sha256": hashlib.sha256(self.document.read_bytes()).hexdigest(),
            "source_url": "https://example.org/synthetic-calibration",
            "calibration_scope": "synthetic fixture measurement chain only",
        }
        self.manifest = {
            "dataset": "paderborn_bearing_datacenter",
            "asset_id": "K001",
            "raw_mat_sha256": hashlib.sha256(self.mat.read_bytes()).hexdigest(),
            "channels": {
                "vibration_1": {"mode": "already_physical", "source_unit": "m/s^2", "target_unit": "m/s^2", "evidence": dict(proof)},
                "phase_current_1": {"mode": "calibrated_voltage", "source_unit": "V", "target_unit": "A", "sensitivity_v_per_unit": 0.1, "zero_offset_v": 2.5, "evidence": dict(proof)},
            },
            "physical_unit_review": {"approved": True, "reviewer": "test-only", "reviewed_utc": datetime.now(timezone.utc).isoformat()},
        }

    def evaluate(self):
        return gate.evaluate_manifest(self.manifest, self.root, self.mat)

    def test_complete_synthetic_fixture(self):
        self.assertTrue(self.evaluate()["physical_csv_allowed"])

    def test_missing_raw_file_blocks(self):
        self.assertIn("raw_mat_not_checked", gate.evaluate_manifest(self.manifest, self.root, None)["errors"])

    def test_bad_mat_hash_blocks(self):
        self.manifest["raw_mat_sha256"] = "0" * 64
        self.assertIn("raw_mat_digest_mismatch", self.evaluate()["errors"])

    def test_unit_unknown_blocks(self):
        self.manifest["channels"]["vibration_1"]["mode"] = "unknown"
        self.assertIn("vibration_1:unverified_source_unit", self.evaluate()["errors"])

    def test_current_offset_required(self):
        del self.manifest["channels"]["phase_current_1"]["zero_offset_v"]
        self.assertIn("phase_current_1:missing_zero_offset", self.evaluate()["errors"])

    def test_evidence_tamper_blocks(self):
        self.document.write_text("changed", encoding="utf-8")
        self.assertIn("phase_current_1:evidence_digest_mismatch", self.evaluate()["errors"])

    def test_path_traversal_blocks(self):
        self.manifest["channels"]["vibration_1"]["evidence"]["file"] = "../other.txt"
        self.assertIn("vibration_1:evidence_file_not_verified", self.evaluate()["errors"])

    def test_review_required(self):
        self.manifest["physical_unit_review"]["approved"] = False
        self.assertIn("human_unit_review_required", self.evaluate()["errors"])

    def test_convert_voltage_removes_offset_before_scaling(self):
        c = self.manifest["channels"]["phase_current_1"]
        converted = gate.convert_samples_to_physical([2.5, 2.6, 2.4], c, "A")
        for result, expected in zip(converted, [0.0, 1.0, -1.0]):
            self.assertAlmostEqual(result, expected)

    def test_reject_boolean_sensitivity(self):
        self.manifest["channels"]["phase_current_1"]["sensitivity_v_per_unit"] = True
        self.assertIn("phase_current_1:missing_positive_sensitivity", self.evaluate()["errors"])


if __name__ == "__main__":
    unittest.main()
