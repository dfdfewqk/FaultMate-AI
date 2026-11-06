# Paderborn data readiness — source audit, not model training

As of 2026-11-04, the verified K001 archive is one **healthy** physical bearing.
Its 80 recordings across four conditions do not constitute 80 independent bearings.
The genuine MAT `Unit` fields for `vibration_1` and `phase_current_1` were empty.
The original archive + MATLAB structure was directly verified in the [GitHub Windows CI run](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41792148113).

## Primary source evidence

- [Paderborn University Bearing DataCenter](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter): 6 healthy / 26 damaged bearing assets; CC BY-NC 4.0 noncommercial restrictions.
- [Lessmeier et al., 2016 primary paper](https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf): Table 5 identifies accelerated-lifetime damage; Section 4 identifies accelerometer 336C04, current transducer CKSR 15-NP, and the 64 kHz acquisition setup. **This describes which physical quantities were measured, not whether every stored MAT channel has SI-calibrated numerical values.**
- [Zenodo mirrored archive inventory](https://zenodo.org/records/15845309): independent MD5 checksum for each RAR. This is a **public secondary mirror**, not a substitute for primary calibration documentation.

## Curated first evaluation cohort

`PADERBORN_TRAINING_ASSETS.json` contains twelve distinct **physical** bearings:

- Healthy: **K001–K006** (6 independent bearing assets).
- Accelerated-lifetime damage, source paper Table 5: **KA04, KA16, KB23, KI04, KI16, KI18** (6 independent bearing assets; outer, inner and mixed-type bearing damage represented).

This is only a **proposed cohort and official checksum catalog**. Aside from K001, the original archive bytes and raw sensors have **not** been inspected in this work. Do not label these archives verified simply because they appear in the catalog.

Run metadata-only validation (no original signals downloaded):

```sh
python scripts/verify_zenodo_catalog.py
```

Audit existing archives without overwriting or downloading anything:

```sh
python scripts/audit_paderborn_assets.py --root data/raw
```

The audit verifies each *existing* RAR's official MD5, 7-Zip test and exact 80 MAT filenames. It does **not** extract SI measurements or train a model. A missing file is reported as missing; it is never counted as an independent measured sample.

## Still blocked / mandatory before ML

1. Obtain original Paderborn dataset-specific sensor signal numeric units / full acquisition calibration and trace the evidence to each source MAT. The `Unit` fields in the first original K001 recording are blank. The sensor model, sample rate and reported measured quantity are **not enough to assert** that numbers are in `m/s²` or `A`.
2. Only after explicit source-bound unit review, extract proper SI features without fabricating raw measurements or labels. Preserve file SHA-256, bearing code and trial ID.
3. Audit and inspect at least five genuine healthy and five genuine damaged bearings; check duplicate recordings.
4. Maintain partitioning **by physical bearing asset** across train, validation and test. Never count multiple recordings as independent assets. Report held-out F1 and both false-positive and false-negative counts.
5. No automatic model activation, no industrial safety assertion, and no commercial use under the CC BY-NC 4.0 license.

**Status:** K001 source/archive/one-MAT structural inspection passed. Candidate archive manifest prepared. SI units, additional raw bearings, actual ML model **not verified**. No CSV/model created.
