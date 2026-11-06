"""Research-only: scan ORIGINAL K001 RAR companion PDFs for actual SI evidence.

Designed for already-authenticated official K001 archive:
 * verify original official archive MD5 from pinned Paderborn catalog
 * inspect ONLY companion PDF document pages extracted from that RAR
 * report page-wise machine-readable words, not copyrighted PDF contents
 * never infer that a sensor/accelerometer model or a PDF mentioning a
   physical unit proves how original MATLAB vibration_1.Y.Data or
   phase_current_1.Y.Data numbers were exported/scaled/zeroed
 * never emit SI CSV, train/activate model, or call external paid AI
This code does not run 7z or access network; CI extracts only PDF sidecars in
an ephemeral runner after verifying exact original archive MD5.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_paderborn_assets import CATALOG, archive_md5, validate_catalog

K001 = "K001"
LIMIT = 32
MAX_PDF_BYTES = 40_000_000
MARKERS = {
    "matlab_export_channel": re.compile(r"(?i)(?:vibration[_ ]?1|phase[_ ]?current[_ ]?1|Y\.Data|MATLAB.{0,35}(?:unit|scale))"),
    "numeric_scale": re.compile(r"(?i)(?:[Cc]alibrat|sensitiv|scal(?:ing|ed|e)|gain|Umrechn|Kalibrier|Verstärk)"),
    "numeric_offset": re.compile(r"(?i)(?:zero.?current|offset|Nullpunkt|zero point|DC.?offset)"),
    "physical_units": re.compile(r"(?i)(?:m/s\^?2|m/s²|amp[eè]res?|milliampere|[mV]/[gA]|pC/g|Einheit|unit)"),
}
EXPECTED_CATALOG = K001


class CompanionDocumentError(ValueError):
    pass


def digest_pdf(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while b := stream.read(1024 * 1024):
            h.update(b)
    return h.hexdigest()


def inspect_pdf_folder(original_archive: Path, document_folder: Path):
    catalog = validate_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
    original = next((x for x in catalog if x["id"] == K001), None)
    if original is None:
        raise CompanionDocumentError("original_K001_bearing_not_in_verified_catalog")
    if (original_archive.is_symlink() or not original_archive.is_file()
        or original_archive.name.casefold() != "k001.rar"
        or original_archive.stat().st_size < 100_000_000
        or archive_md5(original_archive) != original["md5"]):
        raise CompanionDocumentError("source_K001_original_archive_md5_mismatch")
    if document_folder.is_symlink() or not document_folder.is_dir():
        raise CompanionDocumentError("source_pdf_folder_missing_or_symlink")
    pdfs = sorted(document_folder.rglob("*"))
    if len(pdfs) > LIMIT:
        raise CompanionDocumentError("companion_pdf_folder_too_many_entries")
    items = []
    from pypdf import PdfReader
    for path in pdfs:
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise CompanionDocumentError("companion_pdf_unexpected_entry")
        if path.is_dir():
            continue
        if (path.suffix.lower() != ".pdf"
            or not path.resolve().is_relative_to(document_folder.resolve())
            or path.stat().st_size > MAX_PDF_BYTES
            or path.stat().st_size < 200):
            raise CompanionDocumentError("source_pdf_invalid_format_or_size")
        try:
            reader = PdfReader(str(path), strict=True)
            if reader.is_encrypted:
                raise CompanionDocumentError("source_pdf_encrypted")
            pages = len(reader.pages)
            if not 1 <= pages <= 60:
                raise CompanionDocumentError("source_pdf_pages_out_of_scope")
            matches = {key: [] for key in MARKERS}
            nonempty = 0
            for idx, page in enumerate(reader.pages, 1):
                body = page.extract_text() or ""
                if body.strip():
                    nonempty += 1
                for key, pattern in MARKERS.items():
                    if pattern.search(body):
                        matches[key].append(idx)
        except CompanionDocumentError:
            raise
        except (ValueError, RuntimeError, OSError, TypeError, KeyError) as exc:
            raise CompanionDocumentError("source_pdf_parser_error") from exc
        items.append({
            "original_rar_companion_file_basename": path.name,
            "original_pdf_sha256": digest_pdf(path),
            "pdf_size_bytes": path.stat().st_size,
            "pages_total": pages,
            "pdf_pages_with_extractable_text": nonempty,
            "pages_with_machine_matlab_signal_name_mentions": matches["matlab_export_channel"],
            "pages_with_generic_calibration_terms": matches["numeric_scale"],
            "pages_with_generic_offset_terms": matches["numeric_offset"],
            "pages_with_physical_unit_words": matches["physical_units"],
        })
    return {
        "schema": "faultmate_original_K001_pdf_sidecar_provenance_review_v1",
        "source_bearing": K001,
        "original_rar_md5_matched_pinned_publisher": True,
        "original_rar_archive_md5": original["md5"],
        "number_of_companion_pdf_files_inspected": len(items),
        "companion_pdf_metadata_and_lexical_pages": items,
        "original_raw_mat_data_unchanged": True,
        "human_approved_document_specific_si_calibration": False,
        "original_stored_vibration_Y_Data_to_SI_scale_verified": False,
        "original_stored_phase_current_Y_Data_to_SI_scale_verified": False,
        "zero_offsets_verified": False,
        "no_original_pdf_or_raw_mat_redistributed": True,
        "training_or_field_model_activation_allowed": False,
        "notice": (
            "측정기·물리단위라는 단어가 PDF에 있다고 MATLAB Y.Data의 "
            "저장 수치 변환·오프셋 증거가 확보된 것은 아닙니다. "
            "PDF 본문 추출은 이미지로 된 페이지를 놓칠 수 있습니다."
        ),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-archive", type=Path, required=True)
    p.add_argument("--companion-pdfs", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or args.out.is_symlink():
            raise CompanionDocumentError("refuse_overwriting_original_companion_report")
        report = inspect_pdf_folder(args.original_archive, args.companion_pdfs)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({
            "status": "ORIGINAL_COMPANION_PDF_LEXICAL_REVIEW_NOT_CALIBRATION",
            "pdf_files": report["number_of_companion_pdf_files_inspected"],
            "calibration_evidence_approved": False,
            "production_ml_approved": False,
        }))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print("PADERBORN_ORIGINAL_COMPANION_PDFS_BLOCKED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
