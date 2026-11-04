# K001 real-archive verification (2026-11-04 UTC)

## Scope and evidence

This report records a **real, downloaded Zenodo K001.rar** verification performed in an ephemeral GitHub Actions **Windows** runner, independently of Antigravity logs.

- CI run: https://github.com/dfdfewqk/FaultMate-AI/actions/runs/41792148113
- Workflow commit: b9299f9fc2b4cc2f9e3a1613ee648b0daee965f3
- Source: https://zenodo.org/records/15845309
- Verification scripts: `scripts/verify_k001_archive.py` and `scripts/inspect_paderborn_archive.py`
- Artifact: `k001-validation-windows-json` (two JSON reports only, expires after 7 days; no raw data is uploaded).

## Actual archive inspection — PASS

- Archive: `K001.rar`
- Length: **173,881,721 bytes**
- MD5: `af6dc58283d356cd438e7738a2d525b8` — matches the official Zenodo record
- SHA-256: `0f119ebdb28fb2f4d9fac1beb1319429f63f7ae1256c23c872f280f3560918e5`
- Full 7-Zip archive integrity test: **passed**
- Exact recording inventory: **80 MATLAB files**:
  - `N09_M07_F10`: 20 recordings
  - `N15_M01_F10`: 20 recordings
  - `N15_M07_F04`: 20 recordings
  - `N15_M07_F10`: 20 recordings
- Physical bearing label: **K001 = healthy**; recordings of a single physical bearing are NOT independent training assets.

## Actual MATLAB inspection — PASS for structure; FAIL CLOSED for units

Inspected exactly `K001\\N15_M07_F10_K001_1.mat` from the verified archive.

- Extracted recording SHA-256: `e1a971e93991e5f8bbfdcacde5a0fec895a4248f8232d52b59ff85d034c9c00d`
- `phase_current_1`: 256001 samples; raw `Unit` entry empty / **unknown**
- `vibration_1`: 256001 samples; raw `Unit` entry empty / **unknown**
- Both required channels were found; archive inspector returned exit code **0**, with status `raw_channels_found_units_require_source_review`.
- **Physical units are NOT verified**. The original numbers MUST NOT be asserted as amperes or metres per second squared until source-bound calibration/units evidence is independently reviewed.
- CSV generated: **no**
- ML trained: **no**
- Model enabled: **no**

## Independent code checks

- Local test suite of staged existing FaultMate Python sources plus the K001 verifier: **154 passed**.
- Synthetic MATLAB Y/Name/Data/Unit inspection: channel names recognized correctly; missing units rejected by `verify_units`.
- A first Ubuntu hosted attempt downloaded the official archive and passed its MD5 checks but the Ubuntu 7-Zip executable segfaulted (exit -11). That platform-specific failure was resolved by using the Windows hosted runner. Do not mislabel it as source corruption.

## Hold gate

**Stop before SI feature extraction or training.**

To unlock: obtain trustworthy dataset-specific proof of each stored channel's physical scale/calibration; verify actual raw units or provide a reviewed, SHA-256-bound manifest. Collect at least five distinct healthy and five distinct damaged bearing assets, then use asset-grouped train/validation/test splits. Keep original P7.2 data and all previous evaluations unchanged. Respect the original Paderborn CC BY-NC 4.0 noncommercial license.
