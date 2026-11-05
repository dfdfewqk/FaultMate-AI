# FaultMate AI — P7.2 ML converter handoff

This converter is experimental and fails closed when SI units are not evidenced. `--inspect` prints raw channel names/units without a CSV. Windows commands should run from the Git repository root. Do not use PowerShell with bash heredocs.

```powershell
& ".\.venv-ml\Scripts\python.exe" scripts/convert_mat_to_csv.py --mat "..\K001\N15_M07_F10_K001_1.mat" --inspect
& ".\.venv-ml\Scripts\python.exe" -m pytest tests/test_convert_mat_to_csv.py -q
```

For conversion supply `--asset-id K001 --trial-id N15_M07_F10_1 --source-id paderborn-bearing-datacenter --label healthy --label-provenance <verified official bearing data reference> --output data/converted/example.csv` using a true recording filename. The source_id must be the **same across all rows** used in one training run. Each recording must have a unique `(asset_id,trial_id)` pair. Aggregate validated rows into a single training CSV with only one header. Do not blindly concatenate CSV headers.

If the `.mat` Unit fields are empty, **do not** claim that the raw numeric data are in m/s²/A based on the test-rig sensor model, 64 kHz rate or free-text manifest. The primary Lessmeier et al. paper describes the sensors, filtering and acquisition but not the units or conversion of stored MATLAB `Y.Data` samples. See `docs/PADERBORN_UNIT_EVIDENCE_RESEARCH_20261105.md`.

The converter requires BOTH `--unit-manifest review.json` AND `--unit-evidence-document source-reference.pdf` (or a saved original `.txt`, `.md`, `.eml` confirmation) unless the MAT Unit fields explicitly specify m/s² and A. The evidence document must have its actual SHA256 bound to the review; the source MAT SHA256, recorded channel identities, real reviewer, UTC review time and source-specific nonzero numeric scale factors are mandatory.

Manifest structure, SOFTWARE FIXTURE EXAMPLE ONLY (not a genuine Paderborn calibration):
```json
{
  "source_sha256": "<source MAT SHA256>",
  "vibration_channel": "vibration_1",
  "current_channel": "phase_current_1",
  "vibration_unit": "m/s²",
  "current_unit": "A",
  "vibration_scale_to_m_s2": 1,
  "current_scale_to_a": 1,
  "stored_mat_values_calibration_verified": true,
  "evidence_document_sha256": "<evidence file SHA256>",
  "evidence_type": "dataset_author_confirmation",
  "evidence_url": "https://institution.example/verified-record",
  "evidence_location": "Exact page / section",
  "unit_evidence": "Human verified explicit conversion of published stored MAT numeric samples to SI with all acquisition gains.",
  "reviewed_by": "independent human reviewer",
  "reviewed_utc": "2026-11-05T00:00:00+00:00"
}
```

**Never copy the fixture values into a real manifest.** 1.0 would imply the stored values were already SI, which remains unverified for the real dataset. Other numerical multipliers are possible only if the source documentation establishes the complete capture-chain gains. A SHA256 and reviewer text provide traceability; the tool cannot establish the scientific truth of a cited document. Without genuine reviewed evidence, conversion must remain blocked.

Example after documentary proof is obtained:
```powershell
& ".\.venv-ml\Scripts\python.exe" scripts/convert_mat_to_csv.py --mat "data\raw\K001\N15_M07_F10_K001_1.mat" --asset-id K001 --trial-id N15_M07_F10_1 --source-id paderborn-bearing-datacenter --label healthy --label-provenance "verified official paper" --unit-manifest review.json --unit-evidence-document original-confirmation.pdf --output data\converted\verified-record.csv
```

Use `7z t` to test archive integrity, and inspect names before extracting. Extract with full paths as needed; the archive may contain many `.mat` recordings, not a single `K001.mat`. Keep `.rar`, `.mat`, raw/converted CSV, virtual environments and API keys out of GitHub. Evaluated models must never be auto-promoted to validated.

Official source: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download (CC BY-NC 4.0).