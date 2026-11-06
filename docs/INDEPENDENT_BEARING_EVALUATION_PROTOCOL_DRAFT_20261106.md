# FaultMate AI — draft independent-bearing evaluation protocol (NOT yet preregistered or executed)

**Status:** draft made after observing the already opened KI21 false negative and the
10-development-bearing condition diagnostics. This document **cannot retroactively
make any historical data blind or independent**. The experimental classifier is
not production approved; default SI-CSV ML remains disabled.

## Why and what is frozen already
- Existing **research-only** Paderborn logistic model: pinned by
  `scripts.evaluate_unseen_paderborn_damaged.PINNED_MODEL_SHA`. Do not change
  its coefficients, bearing-level 12-feature order, standardization, pooled
  four-condition/80-MAT median aggregation or **0.5 threshold** during an
  independent evaluation.
- Historical development physical bearings:
  healthy K001–K005 and damaged KA04, KA16, KB23, KI04, KI16. Their **796
  unique measurements are not 796 independent bearing samples**.
- Previously opened bearings: K006, KI18 and KA15/KA22/KA30/KB24/KB27/KI14/
  KI17/KI21. These assets are excluded from any **fresh independent** test or
  classifier-selection experiment, regardless of renaming, splitting, or
  re-downloading. Previous 7/8 damaged detection with KI21 missed remains a
  historical finding, not a prospective performance claim.
- Observed KI21 current crest minima and per-condition scaler-z shifts are
  **post-hoc hypotheses**, not validated candidate features. They must never
  be used to modify model choices and then recycled as new test evidence.

## Preconditions to freeze BEFORE any new raw source is opened
1. Identify source institution, accession, exact published dataset, signed
   archive/file hashes and permitted usage. Document commercial rights;
   original Paderborn source CC BY-NC 4.0 does not grant commercial use.
2. Provide a verified physical-bearing inventory with separate healthy and
   damaged objects, labels traceable to primary provenance rather than
   model predictions, measurement-condition protocol, sampling frequency,
   sensor channels and duplicate fingerprints.
3. Write and commit a prospective fixed **bearing count/availability rule**,
   explicit class counts, and acceptance criterion before accessing source
   features/labels/results. The count is **not yet specified**, so no
   statistical power or field false-alarm guarantee is currently asserted.
4. Document matching vibration and current channels at all four official
   conditions, with 20 MATLAB paired recordings per bearing (or treat
   mismatched protocols as a **separate domain study**, not a valid test of
   this frozen 80-record classifier). Missing files, mixed identities, reused
   bearing IDs, duplicate sensor fingerprints, corrupt source hashes and
   uncertainty in original signal interpretation must fail closed.
5. Lock the extractor/source SHA, standardized feature schema and frozen
   model hash, fixed 0.5 threshold, software environment and an immutable
   proposed-test manifest. Verify zero asset/fingerprint overlap with all
   historical development and opened test data before any modeling.
6. Specify **one primary metric** at the independent physical-bearing level
   (for example, healthy specificity/false positive counts) with a declared
   confidence-interval procedure and separately report sensitivity and
   every false negative. Define the minimum scientifically acceptable result
   *before looking at outcomes*. No unregistered threshold search or
   feature/condition selection after errors are revealed.
7. Freeze a once-only analysis plan; prohibit leakage from trial-level
   permutations/cross-validation. Repeated recordings of one bearing produce
   **one bearing prediction**, not 80 independent labels. Retain immutable
   hashes and a complete confusion matrix and list of misses.

## Required output and abort criteria
- Before tests: source/labels/consent/license/asset count, duplicate audit,
  four-condition input compatibility, signed protocol hash and model hash.
- After tests if preconditions pass: physical bearing TP/TN/FP/FN; per-class
  counts; sensitivity and specificity with **bearing-level** intervals using
  the declared prior method; error inventory and operating-condition notes.
- If independent healthy cases are missing: **do not** report specificity,
  FPR, overall accuracy or field readiness as measured.
- If damaged provenance is unverifiable, SI/feature contract mismatches,
  protocol differs, or repeated/opened assets leak: abort primary evaluation,
  record limitation and retain model as research-only.
- These results never authorize a field repair action, automatic device
  control, work permission, paid API, commercial reuse, model promotion or
  an EXE/ZIP production release. User Windows acceptance, OEM review and
  explicit model approval remain distinct external gates.

## Current next step
Document descriptive **within-bearing repeated-MAT trial variability** for
the 10 SHA-verified development bearings and original KI21, preserving source
checks. A feature distribution or trial IQR comparison is *not* an independent
extraction reproducibility experiment; repeating source extraction from the
same original archive and checking byte-equivalent derived features would be
a separate reproducibility test. First secure genuinely new physical-bearing
data and permissions before declaring this protocol preregistered or
choosing its final sample size/acceptance thresholds.
