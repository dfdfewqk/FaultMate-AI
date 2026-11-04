"""Offline unit tests: they do not claim that an actual K001 archive was verified."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_k001_archive import (archive_recordings, file_hashes, inspect_archive,
                                SourceVerificationError)


def matching_inventory() -> str:
    return "\n".join(
        f"Path = N{speed:02d}_M07_F10_K001_{n}.mat"
        for speed in (9, 10, 11, 15) for n in range(1, 21)
    )


class K001SourceTests(unittest.TestCase):
    def test_exact_80_recordings(self):
        records = archive_recordings(matching_inventory())
        self.assertEqual(len(records), 4)
        self.assertEqual(sum(map(len, records.values())), 80)

    def test_reject_fake_healthy_damaged_names(self):
        listing = matching_inventory() + "\nPath = K001_damaged_1.mat"
        with self.assertRaisesRegex(SourceVerificationError, "unexpected_mat_filenames"):
            archive_recordings(listing)

    def test_reject_missing_recording(self):
        listing = matching_inventory().replace("Path = N09_M07_F10_K001_20.mat", "")
        with self.assertRaisesRegex(SourceVerificationError, "unexpected_recording_inventory"):
            archive_recordings(listing)

    def test_reject_duplicate_recording(self):
        listing = matching_inventory().replace("Path = N09_M07_F10_K001_20.mat", "Path = N09_M07_F10_K001_19.mat")
        with self.assertRaisesRegex(SourceVerificationError, "missing_or_duplicate_recordings"):
            archive_recordings(listing)

    def test_reject_wrong_number_of_conditions(self):
        listing = "\n".join(x for x in matching_inventory().splitlines() if "N09_" not in x)
        with self.assertRaisesRegex(SourceVerificationError, "unexpected_recording_inventory"):
            archive_recordings(listing)

    def test_reject_missing_archive(self):
        with self.assertRaisesRegex(SourceVerificationError, "archive_not_found"):
            inspect_archive(Path("definitely-no-k001-file.rar"))

    def test_reject_tiny_archive_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "K001.rar"
            path.write_bytes(b"RAR!fake-test")
            with self.assertRaisesRegex(SourceVerificationError, "archive_too_small"):
                inspect_archive(path)

    def test_reject_wrong_digest_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "K001.rar"
            path.write_bytes(b"fake")
            with self.assertRaisesRegex(SourceVerificationError, "zenodo_md5_mismatch"):
                inspect_archive(path, minimum_bytes=0)

    def test_hash_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "K001.rar"
            path.write_bytes(b"checksum")
            a, b = file_hashes(path)
            self.assertEqual(a, hashlib.md5(b"checksum", usedforsecurity=False).hexdigest())
            self.assertEqual(b, hashlib.sha256(b"checksum").hexdigest())

    def test_verify_valid_fake_archived_metadata_with_mocked_7zip(self):
        # This tests orchestration only. It is NOT a real dataset authenticity test.
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "K001.rar"
            path.write_bytes(b"test fixture")
            expected_md5 = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
            from subprocess import CompletedProcess
            with patch("verify_k001_archive.subprocess.run", side_effect=[
                CompletedProcess([], 0, stdout="Everything is OK"),
                CompletedProcess([], 0, stdout=matching_inventory()),
            ]) as run:
                report = inspect_archive(path, sevenzip="fake7z", expected_md5=expected_md5, minimum_bytes=0)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(report["status"], "archive_matches_zenodo_and_inventory")
            self.assertFalse(report["physical_units_verified"])

    def test_failure_of_archive_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "K001.rar"
            path.write_bytes(b"test fixture")
            expected = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
            from subprocess import CompletedProcess
            with patch("verify_k001_archive.subprocess.run", return_value=CompletedProcess([], 2, stdout="CRC Error")):
                with self.assertRaisesRegex(SourceVerificationError, "sevenzip_test_failed"):
                    inspect_archive(path, sevenzip="fake7z", expected_md5=expected, minimum_bytes=0)

if __name__ == "__main__":
    unittest.main()