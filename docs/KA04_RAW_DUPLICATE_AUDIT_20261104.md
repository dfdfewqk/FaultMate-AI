# KA04 raw signal duplicate investigation — 2026-11-04

## Scope and independent execution

Source archive: Paderborn Bearing DataCenter KA04, genuine accelerated-lifetime damaged bearing.
QA CI: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41797267886

The Windows GitHub Actions runner independently downloaded **KA04.rar** from
https://zenodo.org/records/15845309 and performed:
- Published per-archive MD5 comparison against `docs/PADERBORN_TRAINING_ASSETS.json`.
- Full 7-Zip archive integrity and 80-file operating-condition inventory checks.
- Extraction of exactly two recordings from operating condition `N09_M07_F10`.
- Raw MATLAB loading of `vibration_1` and `phase_current_1`, independent of reported file hashes.
- Element-by-element comparison of **both** sensor sample arrays.

## Observed — confirmed duplicate signals

| Measurement | KA04_17 | KA04_18 |
| --- | --- | --- |
| Full recording filename | N09_M07_F10_KA04_17.mat | N09_M07_F10_KA04_18.mat |
| MAT SHA-256 | f309c8f26012c0cc088d8858b3b328d473cca93eb83d7d3c4b5ca046cf100cd5 | f07e5a1c5a5b3f94fa3ba0c390a63db889fe0e60213f353b1a40a309bb4bc78d |
| `vibration_1` samples | 256082 | 256082 |
| `phase_current_1` samples | 256082 | 256082 |
| Raw `Unit` metadata | unknown | unknown |

**Verdict:** The MATLAB files have different file hashes, but the measured vibration and phase-current sequences match element by element. These are **not two independent observations**. The dataset can still provide one physical KA04 bearing; do **not** double-weight these two trials.

Both original `Unit` fields are empty; **physical calibration is not verified**. Do not assert the values are in m/s² or A, and do not train or activate a model based on this report.

## Code correction and regression

- `scripts/qa_bearing_recording_duplicates.py`: source-bound read-only raw signal duplication inspection.
- `tests/test_qa_bearing_recording_duplicates.py`: synthetic comparison contracts.
- `scripts/train_ml.py`: rejects identical feature vectors from the *same bearing*, even if a duplicate is supplied under a new `trial_id`.
- `tests/test_train_ml_artifact_preservation.py`: dedicated duplicate-data regression ensuring no evaluation artifact is written.

Independent Python test suite locally: **176 passed**.
No original RAR/MAT, secret, calibrated CSV, or model was added to the repository.

## Boundaries

This spot check proves one real duplicate and channel structure, not the absence of other duplicates. A complete per-bearing scan remains necessary once unit provenance and official data access are settled. Keep the approved-model gate closed.
