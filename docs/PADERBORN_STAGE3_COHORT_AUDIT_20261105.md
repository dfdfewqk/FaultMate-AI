# FaultMate AI — Stage 3: 12 bearings / 960 raw MATLAB recordings

Date: 2026-11-05 (KST). Branch: work/faultmate-cohort-12-raw-audit-20261105.
Base: work/faultmate-sensor-calibration-reconciled-20261105.
Existing main branch, original records, previous ML artifacts, UI and binaries are preserved.

## Source and cohort

- Original source: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter
- Public checksum mirror: https://zenodo.org/records/15845309
- Six independently identified healthy bearings: K001 K002 K003 K004 K005 K006.
- Six accelerated-lifetime damaged bearings: KA04 KA16 KB23 KI04 KI16 KI18.
- Each physical bearing has four official conditions with 20 recordings, totaling 12 x 80 = 960 raw MAT recordings.
- The pinned MD5 values and bearing labels are in docs/PADERBORN_TRAINING_ASSETS.json.
- Dataset license CC BY-NC 4.0 requires attribution and restricts commercial use.

## Previously verified real source evidence

- K001 archive: 173881721 bytes, MD5 af6dc58283d356cd438e7738a2d525b8, 7-Zip and all 80 names passed. https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41792148113
- KA04 source: 17 and 18 within N09_M07_F10 have identical measured vibration+current samples despite different MAT SHA256. https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41797267886
- Earlier KA04 integrated spot check of eight MATs reported seven unique signals. https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41942462085
- Ten other candidate archives were not directly verified by these historical reports.

## Corrected completeness contract

- A collection of twelve JSON reports does not prove 960 recordings were inspected.
- scripts/combine_paderborn_raw_audits.py now requires all 80 unique official condition/trial IDs per physical bearing before incrementing the fully audited count.
- Full cohort status requires all 12 independently identified bearings and exactly 960 inspected recordings. Otherwise the status is raw_audit_partial, with explicit incomplete-bearing IDs.
- Reused MAT SHA256 with contradictory raw fingerprints causes a validation failure.
- Independent-bearing minimums count only bearings with a complete 80-recording audit.
- Even after full raw audit, training_permitted, physical_units_verified and model_activated remain false.

## Validation

- Full Python regression with synthetic 12x80 and partial-report tests: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41957276318 (passed).
- Direct original full-source workflow: .github/workflows/official-paderborn-12-full-audit.yml
- Its independent Windows matrix checks the Zenodo MD5, sevenzip integrity, complete 80-recording MAT inventory and per-channel raw fingerprints for each of twelve archives.
- The aggregator checks duplicate fingerprints across bearings and all 960 trials. It saves seven-day audit JSON artifacts only.
- No repository commits of RAR/MAT, physical-unit CSV, model, keys, ZIP or EXE; no packaging.
- This document must NOT be treated as a claim that the full real 12-bearing audit passed until workflow evidence confirms that result.

## Remain blocked

Raw MATLAB channel Unit values are not proven to be in m/s^2 or amperes; source-specific calibration is unresolved. Physical-unit CSV conversion, model learning and approval remain disabled. The physical bearing, not its trial, must be the split group in any later ML assessment.

## Final actual execution results (2026-11-05 UTC)

- Independent original-source CI: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41957475830
  - ALL 12 independent bearing jobs passed source RAR MD5, complete 7-Zip integrity, official 80-filename inventory and 80 MAT signal decoding.
  - Original multi-OS aggregation initially failed on K001 because Windows CRLF checkout and Linux LF checkout produced different byte-level SHA256 values for the same official catalog JSON.
  - This was diagnosed by independently reproducing both hashes for the identical catalog: LF be8abe1ea64e92119ad244668f4305402c6cc31687fd8737f937aa3b717e21a3 vs CRLF 3057511fd8ba99a823e62b28b4c85d6dda6ebc0d06e19a40e5447ed9152feb63.
  - The aggregator now permits only those two line-ending representations of the pinned actual catalog. Other digests remain rejected.
- Corrected full cohort aggregate run, **SUCCESS**: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41958473911
  - Reused the 12 actual JSON audit artifacts without redownloading 2 GB of RAR source data.
  - 12/12 physical bearing archives, healthy=6, damaged=6, 960/960 MATLAB recordings, no missing bearing/audit or cross-bearing duplicate.
  - 956 unique (vibration_1 + phase_current_1) raw-signal pairs; four duplicate recordings, ALL on KA04:
    1. N09_M07_F10_KA04_18 duplicates 17.
    2. N15_M07_F04_KA04_15 duplicates 6.
    3. N15_M07_F04_KA04_19 duplicates 5.
    4. N15_M07_F04_KA04_20 duplicates 6 (hence 6/15/20 are a three-way repeat).
  - Only the four repeated trials must be excluded/deduplicated as measurements. KA04 remains ONE damaged physical bearing. Other eleven bearings had zero repeated raw-signal pairs.
  - Result status raw_archives_audited_calibration_unverified, cohort_raw_audit_complete=true, unique_raw_signals_in_inspected_recordings=956, fully_audited_bearings=12, minimum_bearing_counts_met=true.
  - Safety flags: physical_units_verified=false, si_csv_generated=false, model_trained=false, model_activated=false, training_permitted=false.
- Latest complete regression: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41958416836 **219 passed**.
- Dedicated offline cross-platform raw aggregate regression in successful aggregate job: **17 passed**.

**Stage 3 conclusion**: original 12-bearing archive/file inventory, source labeling and raw-signal duplication audit complete with recorded evidence, but NOTHING is validated in physical SI units. Stage 4 must not run actual feature training until the previously identified Paderborn calibration blocker is genuinely resolved; no fabricated SI features or false model predictions.
