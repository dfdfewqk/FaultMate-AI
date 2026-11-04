"""No external archives are used for tests of the one-command K001 inspector."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from inspect_paderborn_archive import (
    ArchiveInspectionError, archive_members, choose_recording, inspect,
)


class ArchiveInspectorTests(unittest.TestCase):
    def test_listing_extracts_mat_only(self):
        listing = "Path = README.txt\n\nPath = N15_M07_F10_K001_1.mat\n\nPath = dir/N09_M07_F10_K001_2.mat\n"
        self.assertEqual(len(archive_members(listing)), 2)

    def test_selects_matching_bearing_and_prefers_first_standard_recording(self):
        candidates = ["N15_M07_F10_K002_1.mat", "K001/N09_M07_F10_K001_2.mat", "K001/N15_M07_F10_K001_1.mat"]
        self.assertEqual(choose_recording(candidates, "K001"), "K001/N15_M07_F10_K001_1.mat")

    def test_bearing_mismatch_fails(self):
        with self.assertRaisesRegex(ArchiveInspectionError, "no_recording_matching_bearing"):
            choose_recording(["N15_M07_F10_K002_1.mat"], "K001")

    def test_missing_archive_fails_before_7zip(self):
        with self.assertRaisesRegex(ArchiveInspectionError, "rar_file_not_found"):
            inspect(Path("/not/a/real/K001.rar"), "7z")

    def test_member_path_with_windows_separator(self):
        self.assertEqual(choose_recording([r"K001\N15_M07_F10_K001_1.mat"], "K001"),
                         r"K001\N15_M07_F10_K001_1.mat")

    def test_no_unverified_data_is_treated_as_measured(self):
        from inspect_paderborn_archive import main
        with mock.patch("sys.argv", ["inspect_paderborn_archive.py", "--archive", "missing.rar"]):
            self.assertEqual(main(), 2)


if __name__ == "__main__":
    unittest.main()