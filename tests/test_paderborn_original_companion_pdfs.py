"""Use synthetic PDF files only: never invent author calibration metadata."""
import hashlib
from pathlib import Path

import pytest
from pypdf import PdfWriter

from scripts import audit_paderborn_original_companion_pdfs as audit
from scripts.audit_paderborn_assets import SourceAuditError


def fake_original(tmp_path, monkeypatch):
    archive = tmp_path / "K001.rar"
    archive.write_bytes(b"FAKE ARCHIVE")
    monkeypatch.setattr(audit, "archive_md5", lambda path: "af6dc58283d356cd438e7738a2d525b8")
    # Actual CI still checks the full original publisher-pinned MD5.
    original_size = Path.stat

    def stat_with_test_size(self, **kwargs):
        result = original_size(self, **kwargs)
        if self == archive:
            class SyntheticOriginal:
                st_size = 166_000_000
            return SyntheticOriginal()
        return result
    monkeypatch.setattr(Path, "stat", stat_with_test_size)
    return archive


def blank_pdf(folder, name="K001_document.pdf"):
    pdf = folder / name
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    with pdf.open("wb") as fh:
        w.write(fh)
    return pdf


def test_fake_pdf_unreadable_page_is_not_calibration_evidence(tmp_path, monkeypatch):
    archive = fake_original(tmp_path, monkeypatch)
    folder = tmp_path / "docs"
    folder.mkdir()
    pdf = blank_pdf(folder)
    report = audit.inspect_pdf_folder(archive, folder)
    assert report["source_bearing"] == "K001"
    assert report["number_of_companion_pdf_files_inspected"] == 1
    assert report["companion_pdf_metadata_and_lexical_pages"][0]["pages_total"] == 1
    assert report["companion_pdf_metadata_and_lexical_pages"][0]["pdf_pages_with_extractable_text"] == 0
    assert report["companion_pdf_metadata_and_lexical_pages"][0]["original_pdf_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert report["original_stored_vibration_Y_Data_to_SI_scale_verified"] is False
    assert report["training_or_field_model_activation_allowed"] is False


def test_no_unknown_archive_auto_approved(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    blank_pdf(folder)
    archive = tmp_path / "K001.rar"
    archive.write_bytes(b"NOT ORIGINAL")
    with pytest.raises(audit.CompanionDocumentError, match="original_archive_md5_mismatch"):
        audit.inspect_pdf_folder(archive, folder)


def test_unsafe_pdf_symlinks_refused(tmp_path, monkeypatch):
    archive = fake_original(tmp_path, monkeypatch)
    folder = tmp_path / "docs"
    folder.mkdir()
    a = blank_pdf(folder)
    (folder / "linked.pdf").symlink_to(a)
    with pytest.raises(audit.CompanionDocumentError, match="unexpected_entry"):
        audit.inspect_pdf_folder(archive, folder)


def test_non_pdf_extra_file_fails_closed(tmp_path, monkeypatch):
    archive = fake_original(tmp_path, monkeypatch)
    folder = tmp_path / "docs"
    folder.mkdir()
    blank_pdf(folder)
    (folder / "attack.exe").write_text("not a pdf")
    with pytest.raises(audit.CompanionDocumentError, match="invalid_format"):
        audit.inspect_pdf_folder(archive, folder)


def test_no_existing_report_overwrite(tmp_path):
    old = tmp_path / "old.json"
    old.write_text("PRESERVE_PREVIOUS_FINDINGS", encoding="utf-8")
    rc = audit.main(["--original-archive", str(tmp_path / "K001.rar"),
                     "--companion-pdfs", str(tmp_path),
                     "--out", str(old)])
    assert rc == 2
    assert old.read_text(encoding="utf-8") == "PRESERVE_PREVIOUS_FINDINGS"


def test_empty_pdf_folder_cannot_establish_calibration(tmp_path, monkeypatch):
    archive = fake_original(tmp_path, monkeypatch)
    folder = tmp_path / "docs"
    folder.mkdir()
    report = audit.inspect_pdf_folder(archive, folder)
    assert report["number_of_companion_pdf_files_inspected"] == 0
    assert report["human_approved_document_specific_si_calibration"] is False
