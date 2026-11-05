"""Source-document-backed BJTU/PHM24 inventory check; NOT a trained model.

Two independent evidence levels are kept separate:
1. What the AUTHORS DOCUMENTED in their BJTU dataset guide (one normal
   state / nine conditions / four CSVs each = 36 FILES, NOT 36 bearings).
2. What actual, identity-verified original healthy PHYSICAL bearing records
   have been inspected: NONE. Filename metadata cannot establish that.

An optional public Drive index probe uses gdown's --json metadata mode only.
No CSV bytes, credentials, cookies, models, original datasets, or paid API.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_LAYOUT = ROOT / "docs/BJTU_PRIMARY_AUTHOR_LAYOUT_20261105.json"
EXPECTED_LABEL = "M0_G0_LA0_RA0"
DRIVE_FOLDER = (
    "https://drive.google.com/drive/folders/"
    "1RlZvFw-v07VvsL2Ni9cS7iFrTPDIhn2r?usp=sharing"
)
SENSOR_OBJECTS = {"motor", "gearbox", "leftaxlebox", "rightaxlebox"}
CONDITIONS = {(20, 0), (40, 0), (60, 0),
              (20, 10), (40, 10), (60, 10),
              (20, -10), (40, -10), (60, -10)}
PATH_RE = re.compile(
    r"^BJTU_RAO_Bogie_Datasets/M0_G0_LA0_RA0/"
    r"Sample_([1-9])/data_"
    r"(motor|gearbox|leftaxlebox|rightaxlebox)"
    r"_M0_G0_LA0_RA0_(20|40|60)Hz_([+-]?10|0)kN\.csv$"
)


class PublishedSourceError(ValueError):
    pass


def verify_published_layout(doc: dict) -> None:
    if not isinstance(doc, dict) or doc.get("schema") != "faultmate_bjtu_primary_publication_layout_v1":
        raise PublishedSourceError("wrong_primary_source_schema")
    s = doc.get("reported_folder_structure")
    sensor = doc.get("source_document_sensor_info")
    usage = doc.get("source_licensing_evidence")
    gaps = doc.get("evidence_gaps")
    if not all(isinstance(x, dict) for x in (s, sensor, usage, gaps)):
        raise PublishedSourceError("missing_primary_source_metadata")
    fixed = {
        "root_folder": "BJTU_RAO_Bogie_Datasets",
        "labeled_health_state_folders": 51,
        "normal_health_state_folders": 1,
        "normal_label": EXPECTED_LABEL,
        "faulty_health_state_folders": 50,
        "working_conditions_per_label": 9,
        "samples_per_health_state": 9,
        "csv_files_per_sample": 4,
        "sample_seconds": 10,
        "all_channels_nominal_sample_rate_hz": 64000,
        "reported_normal_sample_sessions": 9,
        "expected_normal_csv_files_if_original_complete": 36,
        "expected_total_sample_sessions_if_original_complete": 459,
        "expected_total_csv_files_if_original_complete": 1836,
    }
    for key, wanted in fixed.items():
        if type(s.get(key)) is not type(wanted) or s.get(key) != wanted:
            raise PublishedSourceError("published_layout_mismatch:" + key)
    if (set(s.get("csv_monitor_objects", [])) != SENSOR_OBJECTS
        or len(s["csv_monitor_objects"]) != 4):
        raise PublishedSourceError("exact_four_original_sensor_csv_groups_required")
    rows = s.get("nine_reported_conditions")
    if (not isinstance(rows, list) or len(rows) != 9
        or any(not isinstance(c, dict) or
               type(c.get("speed_hz")) is not int or
               type(c.get("lateral_load_kn")) is not int for c in rows)
        or {(c["speed_hz"], c["lateral_load_kn"]) for c in rows} != CONDITIONS):
        raise PublishedSourceError("nine_original_operating_conditions_unproven")
    if (doc.get("original_distribution_url") != DRIVE_FOLDER
        or "Introduction-to-BJTU-RAO-Bogie-Datasets.pdf" not in
           str(doc.get("original_author_public_dataset_guide", ""))
        or doc.get("status") != "original_author_document_reviewed_no_actual_sensor_csv_claim"):
        raise PublishedSourceError("source_document_or_distribution_mismatch")
    if (sensor.get("channels") != 24
        or sensor.get("axlebox_bearing_type") != "HRB 352213"
        or sensor.get("paderborn_bearing_type") != "6203"
        or sensor.get("same_bearing_or_operating_condition_as_paderborn") is not False):
        raise PublishedSourceError("cannot_substitute_bjtu_for_paderborn_original_bearing")
    if (usage.get("guide_usage_statement") !=
            "The datasets are publicly available, and anyone can feel free to use them when the data source is indicated."
        or usage.get("source_guide_attribution_required") is not True
        or usage.get("commercial_permission_explicitly_confirmed") is not False
        or usage.get("machine_readable_dataset_license_confirmed") is not False):
        raise PublishedSourceError("source_license_cannot_be_assumed_commercial")
    for key in ("public_drive_subfolder_contents_downloaded",
                "original_csv_bytes_read", "original_file_shas_verified",
                "unique_healthy_physical_bearing_ids_confirmed",
                "normal_sample_sessions_are_independent_physical_bearings",
                "direct_frozen_paderborn_model_inference_allowed",
                "healthy_specificity_measured",
                "license_for_commercial_integration_verified"):
        if gaps.get(key) is not False:
            raise PublishedSourceError("unverified_source_evidence_fabricated:" + key)
    if gaps.get("number_independent_healthy_physical_bearings_verified") is not None:
        raise PublishedSourceError("nine_conditions_are_not_nine_healthy_bearings")


def inspect_metadata_only_healthy_paths(paths: list[str]) -> dict:
    """Filename layout only; *never* upgrades to raw/physical-asset evidence."""
    if not isinstance(paths, list):
        raise PublishedSourceError("expected_list_of_relative_published_paths")
    if len(paths) > 36:
        raise PublishedSourceError("healthy_folder_cannot_hold_more_than_36_original_csv")
    groups: dict[str, set[str]] = defaultdict(set)
    cond: dict[str, tuple[int, int]] = {}
    seen: set[str] = set()
    for p in paths:
        if not isinstance(p, str) or not p.isascii() or "\\" in p or ".." in p or p in seen:
            raise PublishedSourceError("invalid_repeated_or_traversal_source_path")
        seen.add(p)
        m = PATH_RE.fullmatch(p)
        if not m:
            raise PublishedSourceError("nonoriginal_healthy_filename_contract")
        session, obj, speed, load = m.groups()
        operating = (int(speed), int(load))
        if operating not in CONDITIONS:
            raise PublishedSourceError("invalid_primary_nine_condition_pair")
        if session in cond and cond[session] != operating:
            raise PublishedSourceError("session_condition_conflict")
        cond[session] = operating
        groups[session].add(obj)
    all_complete = (
        len(paths) == 36 and len(groups) == 9
        and all(groups.get(f"{n}") == SENSOR_OBJECTS for n in range(1, 10))
        and set(cond.values()) == CONDITIONS
    )
    return {
        "source": "local_filename_index_not_original_csv_hashes",
        "metadata_paths_checked": len(paths),
        "healthy_state_label": EXPECTED_LABEL,
        "nine_source_conditions_and_four_sensor_groups_layout_complete": all_complete,
        "source_csv_file_integrity_verified": False,
        "distinct_normal_physical_bearing_count": None,
        "healthy_bearing_independent_holdout_proven": False,
        "new_normal_specificity_measured": False,
        "frozen_paderborn_model_approved_for_bjtu": False,
    }


def _no_live_probe() -> dict:
    return {
        "public_drive_probe_requested": False,
        "google_drive_folder_reachable": None,
        "metadata_entries_returned": 0,
        "metadata_listing_complete": False,
        "normal_folder_structurally_verified": False,
        "original_csv_files_downloaded": False,
        "source_csv_sha256_verified": False,
        "independent_normal_physical_bearings_verified": 0,
        "raw_signal_model_evaluation_performed": False,
        "paid_external_api_called": False,
    }


def probe_public_folder_metadata(*, timeout_seconds: int = 55) -> dict:
    """Run gdown --json (never download files); failure is not evidence of absence.

    The publicly shared folder may contain too many files for the gdown API
    and its listing can be partial, unavailable, or require browser login.
    File names alone do not establish the unique physical bearings or data
    license. Only records a tiny summary; does not store Drive IDs or CSV.
    """
    result = _no_live_probe()
    result["public_drive_probe_requested"] = True
    cmd = [sys.executable, "-m", "gdown", DRIVE_FOLDER, "--folder",
           "--json", "--no-cookies"]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=timeout_seconds, check=False)
        if completed.returncode != 0:
            result["public_drive_error_class"] = "metadata_listing_failed_or_limited"
            return result
        if len(completed.stdout) > 2_000_000:
            result["public_drive_error_class"] = "metadata_listing_exceeds_safe_limit"
            return result
        docs = json.loads(completed.stdout)
        if not isinstance(docs, list):
            result["public_drive_error_class"] = "unexpected_gdown_metadata_output"
            return result
        paths = [d["path"] for d in docs if isinstance(d, dict) and
                 isinstance(d.get("path"), str)]
        # A successful partial gdown metadata listing cannot certify 51x9x4
        # originals, since its documented folder limit can truncate results.
        result["google_drive_folder_reachable"] = True
        result["metadata_entries_returned"] = len(paths)
        # The authors publicly shared this source: keep only relative display
        # names, never Google file IDs, download tokens, cookies or CSV contents.
        # This may be a PARTIAL gdown listing, not the 51-state inventory.
        result["public_entry_path_sample"] = sorted({
            re.sub(r"[^\\w/.+() -]", "_", p)[:180]
            for p in paths if p and len(p) < 500
        })[:25]
        result["metadata_listing_complete"] = False
        result["normal_folder_structurally_verified"] = False
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError,
            json.JSONDecodeError):
        result["public_drive_error_class"] = "metadata_probe_unavailable_or_timed_out"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-layout", type=Path, default=PUBLISHED_LAYOUT)
    parser.add_argument("--healthy-paths-json", type=Path,
                        help="Optional FILE-NAME-ONLY relative-path JSON array.")
    parser.add_argument("--probe-drive-public-metadata", action="store_true",
                        help="Optional publicly shared Drive metadata probe only; no CSV downloads.")
    parser.add_argument("--out", type=Path, required=True,
                        help="NEW JSON report. Existing output is never overwritten.")
    args = parser.parse_args(argv)
    try:
        verify_published_layout(json.loads(args.source_layout.read_text(encoding="utf-8")))
        result = {
            "status": "published_bjtu_layout_reviewed_original_sensor_data_unverified",
            "documented_normal_health_states": 1,
            "documented_normal_operating_conditions": 9,
            "documented_normal_csv_files": 36,
            "documented_all_csv_files": 1836,
            "nine_conditions_are_nine_independent_bearings": False,
            "source_healthy_physical_bearings_verified": 0,
            "false_positive_rate_measured": False,
            "publication_documented_folder_structure_only": True,
            "drive": probe_public_folder_metadata()
                if args.probe_drive_public_metadata else _no_live_probe(),
        }
        if args.healthy_paths_json is not None:
            result["filename_contract"] = inspect_metadata_only_healthy_paths(
                json.loads(args.healthy_paths_json.read_text(encoding="utf-8")))
        if args.out.exists() or args.out.is_symlink():
            raise PublishedSourceError("refuse_to_overwrite_existing_evidence")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write("\n")
        print(json.dumps({
            "published_normal_csv_files": 36,
            "physically_independent_healthy_bearings_verified": 0,
            "real_model_inference_performed": False,
            "external_paid_api_called": False,
            "drive_metadata_reachable": result["drive"]["google_drive_folder_reachable"],
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        print("BJTU_SOURCE_LAYOUT_FAIL_CLOSED:", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
