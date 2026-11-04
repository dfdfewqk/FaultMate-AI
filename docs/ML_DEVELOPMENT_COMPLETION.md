# FaultMate AI — ML/DeepSeek development boundary & final Windows test

This is a **development-ready workflow**, **not** a claim that any real measurement has been converted, trained, or externally validated.

## Finished source-code stages

1. `scripts/inspect_paderborn_archive.py` checks the full RAR with 7-Zip and temporarily extracts just one MATLAB recording to print real `Name`, `Data` shape, and recorded `Unit`. It does not convert or infer SI units.
2. `scripts/convert_mat_to_csv.py` extracts one recording with reviewed labels and verified SI units. Empty MATLAB `Unit` requires a **human-reviewed, SHA-256-bound unit manifest** containing real supporting evidence. No empty units may be assumed to mean SI units. It never overwrites existing CSV.
3. **`scripts/assemble_bearing_features.py`** merges individually reviewed per-recording CSVs. It rejects duplicate `(asset_id, trial_id)` pairs, duplicate exact feature recordings within an asset, conflicting labels, mixed datasets/licenses, impossible vibration RMS/peak relationships, missing metadata, and non-Paderborn licenses. It reports independent bearings by class and can refuse to publish until **at least five per class**. This count is **not** proof of sensor calibration or labels.
4. Existing `scripts/train_ml.py` performs asset-disjoint train/validation/test splits, train-only normalization, a baseline comparison, held-out metrics, and writes **`evaluated_pending_review`** only. It never enables the model. **Rerunning against an output folder that already contains either evaluation artifact fails instead of overwriting previous results**; use a new output directory for each run.
5. **`scripts/review_bearing_model.py`** verifies matching evaluation/model/source hashes and a separate *human-provided* explicit review JSON. It cannot check whether the human has truly inspected source documents. Dry-run does **not** publish; `--apply` is required and never overwrites an existing model. The runtime model loader rejects unreviewed models even if a JSON status is manually changed to `validated`.
6. DeepSeek opt-in backend and P7.2 browser controls already exist. Per-request consent, emergency stops, local evidence allowlists, and index-only model responses remain unchanged. The *live* DeepSeek call needs a later, explicit real-world test.

## Required original-data and license verification

- Primary source: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter
- Recording information: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download
- License: **CC BY-NC 4.0** (non-commercial; credit the research authors and institution).
- Official data describes six healthy and 26 damaged bearing states, different operating conditions, and 20 four-second recordings per setting. These recordings **are not** independent physical bearings. Every physical bearing must retain a stable `asset_id` across all recordings.
- The raw MATLAB `Unit` metadata may be blank. Sensor description alone is **not sufficient** to conclude that the numeric arrays are in m/s² or A. If the documented units or sensor calibration scale are unclear, stop before CSV conversion. A free-text claim in `unit_evidence` is not, by itself, proof.
- A single `K001.rar` is **not** enough to train or evaluate a model. Do not report synthetic test results as real-world ML accuracy.

## Single Windows execution sequence after development is frozen

Run in a **separate working tree** of `work/faultmate-ml-converter-fix-20261030`; preserve other branches and the original `.venv`. The existing `.venv-ml` should be used if it already works. No Python reinstall or replacement environment is required merely to execute these scripts.

```powershell
# Set-Location to the actual repository root containing faultmate/, scripts/, tests/
& ".\.venv-ml\Scripts\python.exe" ".\scripts\inspect_paderborn_archive.py" --archive "C:\Users\User\Downloads\FaultMate-AI-main\K001.rar"
```

After inspecting official sensor calibration and labels, generate **only verified** feature CSVs with the converter. Example recording name is schematic, not a confirmed K001 archive member:

```powershell
& ".\.venv-ml\Scripts\python.exe" ".\scripts\convert_mat_to_csv.py" --mat ".\data\raw\N15_M07_F10_K001_1.mat" --inspect
```

When `Unit` metadata is empty, obtain a real source reference proving the numeric physical units before using `--unit-manifest`. Manifest structure (values here are **placeholders, not verified**; do not use as-is):

```json
{
  "source_sha256": "ACTUAL_64_CHARACTER_SHA256_OF_MAT",
  "vibration_channel": "ACTUAL_CHANNEL_NAME",
  "current_channel": "ACTUAL_CHANNEL_NAME",
  "vibration_unit": "m/s^2",
  "current_unit": "A",
  "unit_evidence": "EXACT_REVIEWED_OFFICIAL_CALIBRATION_REFERENCE_AND_SECTION"
}
```

If source measurements are raw voltages/ADC values, this tool does **not** calculate calibration conversions. Stop until sensor sensitivity, scaling and offset are verified and implemented separately. Do not fill the manifest with asserted SI units as a workaround.

After sufficient **genuinely verified per-recording** CSVs are saved under `data/converted/individual/`, use:

```powershell
& ".\.venv-ml\Scripts\python.exe" ".\scripts\assemble_bearing_features.py" --input-dir ".\data\converted\individual" --output ".\data\converted\bearing_training.csv" --require-ready
& ".\.venv-ml\Scripts\python.exe" ".\scripts\train_ml.py" ".\data\converted\bearing_training.csv" --output ".\models\evaluation"
```

Check the held-out confusion matrix, group counts, false positives/false negatives, data hashes, license and actual source records. **No validated model is generated by the trainer.** Human approval is required separately.

Approval JSON is **not generated automatically**. A reviewer must explicitly supply the matching SHA-256 of `bearing_evaluated.json`, `data_sha256`, an identity, timezone-aware `reviewed_utc`, substantial notes, `decision: "approved_for_experimental_use"`, and each of these five boolean checks set `true` only after real inspection: `unit_calibration_verified`, `label_provenance_verified`, `independent_assets_verified`, `heldout_errors_reviewed`, `noncommercial_use_only`.

```powershell
# Review without publishing anything
& ".\.venv-ml\Scripts\python.exe" ".\scripts\review_bearing_model.py" --evaluated ".\models\evaluation\bearing_evaluated.json" --report ".\models\evaluation\evaluation_report.json" --review ".\models\review-local.json"
# Only after explicit human release decision, repeat with --apply
```

An approved model is confined to **experimental bearing-feature comparison**. It never indicates actual failure probability, safe working conditions, or permission to control equipment.

## Final tests (after all code is integrated)

1. Automated Python tests (`python -m pytest -q tests`) and available browser/HTTP tests; report counts and failures separately.
2. Windows 7-Zip integrity, real MATLAB channel and physical-unit review for `K001.rar`; no arbitrary label or calibration claims.
3. At least five **independent** actual physical bearings per class; inspect dataset audit, no group leakage; report held-out metrics honestly.
4. DeepSeek LIVE: set `DEEPSEEK_API_KEY` in the server environment locally (never GitHub/browser) and test consent missing, emergency hold, success and upstream failures. No automatic repeated paid calls. Keep the deterministic triage usable when API fails.
5. Launch via existing `start_windows.bat`; verify normal diagnosis, optional AI/ML, errors, absence of PLC actions, safety hold, and no unauthorized storage or transmission.

**Do not** merge the PR or claim a live ML/DeepSeek system until these real-data/Windows checks are reported. Original P7.2 UI and its existing files remain intact.
