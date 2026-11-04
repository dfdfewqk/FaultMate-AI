# FaultMate AI — P7.2 ML converter handoff

This converter is experimental and fails closed when SI units are not evidenced. `--inspect` prints raw channel names/units without a CSV. Windows commands should run from the Git repository root. Do not use PowerShell with bash heredocs.

```powershell
& ".\.venv-ml\Scripts\python.exe" scripts/convert_mat_to_csv.py --mat "..\K001\N15_M07_F10_K001_1.mat" --inspect
& ".\.venv-ml\Scripts\python.exe" -m pytest tests/test_convert_mat_to_csv.py -q
```

For conversion supply `--asset-id K001 --trial-id N15_M07_F10_1 --source-id paderborn-bearing-datacenter --label healthy --label-provenance <verified official bearing data reference> --output data/converted/example.csv` using a true recording filename. The source_id must be the **same across all rows** used in one training run. Each recording must have a unique `(asset_id,trial_id)` pair. Aggregate validated rows into a single training CSV with only one header. Do not blindly concatenate CSV headers.

If the `.mat` Unit fields are empty, a **human-reviewed** external calibration reference is necessary before a file-scoped `--unit-manifest review.json` is prepared. Illustrative manifest schema ONLY (not proof of units):

```json
{
  "source_sha256": "hex sha256 of the exact .mat file",
  "vibration_channel": "vibration_1",
  "current_channel": "phase_current_1",
  "vibration_unit": "m/s²",
  "current_unit": "A",
  "unit_evidence": "Exact independently reviewed source document, page/section"
}
```

Do not fabricate a manifest or assume physical units based on column names. The converter validates hash/format but cannot independently authenticate a reference. User supplied labels alone also do **not** establish real ground truth. Verify bearing label and units against source fact sheets and calibration. Actual K001.rar extraction and measurements were **not** run in the ChatGPT environment.

Use `7z t` to test archive integrity, and inspect names before extracting. Extract with full paths as needed; the archive may contain many `.mat` recordings, not a single `K001.mat`. Keep `.rar`, `.mat`, raw/converted CSV, virtual environments and API keys out of GitHub. Evaluated models must never be auto-promoted to validated.

Official source: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download (CC BY-NC 4.0).