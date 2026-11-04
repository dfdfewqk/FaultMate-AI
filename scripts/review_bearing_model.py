"""Human-gated publication of an independently evaluated bearing model.

This tool does not validate physical units or ground truth by itself. Only a
human who examined the original source, calibration, split, and held-out errors
may sign the review JSON. Never use synthetic test data for a real deployment.
No model is published unless --apply is explicitly supplied.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOURCE = 'paderborn-bearing-datacenter'
LICENSE = 'CC BY-NC 4.0'
SCOPE = 'experimental_bearing_feature_windows_only'
APPROVAL = 'approved_for_experimental_use'
REVIEW_CHECKS = (
    'unit_calibration_verified',
    'label_provenance_verified',
    'independent_assets_verified',
    'heldout_errors_reviewed',
    'noncommercial_use_only',
)


def _load_object(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('json_object_required')
    return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_score(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1


def validate_review(evaluated_path: Path, report_path: Path, review_path: Path) -> dict:
    evaluated = _load_object(evaluated_path)
    report = _load_object(report_path)
    review = _load_object(review_path)
    digest = _sha(evaluated_path.read_bytes())
    if evaluated.get('status') != 'evaluated_pending_review':
        raise ValueError('model_not_pending_review')
    if (evaluated.get('scope') != SCOPE or evaluated.get('source_id') != SOURCE or
        evaluated.get('license') != LICENSE):
        raise ValueError('source_scope_or_license_not_approved')
    from faultmate.integration.ml import EXPECTED_LABELS, FEATURES
    if evaluated.get('classes') != list(EXPECTED_LABELS) or evaluated.get('feature_names') != list(FEATURES):
        raise ValueError('model_schema_mismatch')
    if not re.fullmatch('[a-f0-9]{64}', evaluated.get('data_sha256', '')):
        raise ValueError('data_sha256_invalid')
    if report.get('data_sha256') != evaluated['data_sha256'] or report.get('source_id') != SOURCE or report.get('license') != LICENSE:
        raise ValueError('report_source_mismatch')
    metrics = evaluated.get('heldout_evaluation')
    if not isinstance(metrics, dict) or any(report.get(key) != value for key, value in metrics.items()):
        raise ValueError('evaluation_report_mismatch')
    for key in ('validation_macro_f1', 'validation_dummy_macro_f1', 'heldout_macro_f1'):
        if not _valid_score(metrics.get(key)):
            raise ValueError('evaluation_score_invalid')
    if metrics['validation_macro_f1'] <= metrics['validation_dummy_macro_f1']:
        raise ValueError('validation_baseline_not_beaten')
    matrix = metrics.get('heldout_confusion_matrix')
    if not (isinstance(matrix, list) and len(matrix) == 2 and
        all(isinstance(row, list) and len(row) == 2 and all(type(v) is int and v >= 0 for v in row) for row in matrix)):
        raise ValueError('heldout_matrix_invalid')
    partitions = report.get('partition_by_asset')
    if not isinstance(partitions, dict) or not partitions:
        raise ValueError('independent_split_report_missing')
    counts = Counter(partitions.values())
    if set(counts) != {'train', 'validation', 'test'}:
        raise ValueError('partition_names_invalid')
    if any(counts[k] != metrics.get(k + '_asset_count') or counts[k] < 2 for k in counts):
        raise ValueError('partition_count_mismatch')
    if review.get('decision') != APPROVAL:
        raise ValueError('explicit_human_approval_missing')
    if review.get('evaluated_sha256') != digest or review.get('data_sha256') != evaluated['data_sha256']:
        raise ValueError('human_review_hash_mismatch')
    if not all(review.get(key) is True for key in REVIEW_CHECKS):
        raise ValueError('human_review_checklist_incomplete')
    if not isinstance(review.get('reviewed_by'), str) or len(review['reviewed_by'].strip()) < 2:
        raise ValueError('reviewer_identity_missing')
    try:
        timestamp = datetime.fromisoformat(review.get('reviewed_utc', '').replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('review_date_invalid') from exc
    if not isinstance(review.get('notes'), str) or len(review['notes'].strip()) < 20:
        raise ValueError('review_notes_missing')
    result = dict(evaluated)
    result['status'] = 'validated'
    result['review_record'] = {key: review[key] for key in
        ('decision', 'evaluated_sha256', 'data_sha256', 'reviewed_by', 'reviewed_utc', *REVIEW_CHECKS, 'notes')}
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluated', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('models/bearing_validated.json'))
    parser.add_argument('--apply', action='store_true', help='Explicitly publish ONLY after human review')
    args = parser.parse_args(argv)
    try:
        result = validate_review(args.evaluated, args.report, args.review)
        if args.apply:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as handle:
                json.dump(result, handle, indent=2, ensure_ascii=False)
                handle.write('\n')
        print(json.dumps({'review_checks_passed': True, 'published': args.apply,
                          'model_active_only_if_saved_under_project_models': args.apply,
                          'output': str(args.output) if args.apply else None}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print('MODEL_NOT_PUBLISHED:', str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
