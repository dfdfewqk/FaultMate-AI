# FaultMate AI — P7.2 ML converter handoff

This converter is experimental and fails closed when SI units are not evidenced. `--inspect` prints raw channel names/units without a CSV. Windows commands should run from the Git repository root. Do not use PowerShell with bash heredocs.

```powershell
& ".\.venv-ml\Scripts\python.exe" scripts/convert_mat_to_csv.py --mat "..\K001\N15_M07_F10_K001_1.mat" --inspect
& ".\.venv-ml\Scripts\python.exe" -m pytest tests/test_convert_mat_to_csv.py -q
```

For conversion supply `--asset-id K001 --trial-id N15_M07_F10_1 --source-id paderborn-bearing-datacenter --label healthy --label-provenance <verified official bearing data reference> --output data/converted/example.csv` using a true recording filename. The source_id must be the **same across all rows** used in one training run. Each recording must have a unique `(asset_id,trial_id)` pair. Aggregate validated rows into a single training CSV with only one header. Do not blindly concatenate CSV headers.

If source MAT Unit fields are blank, **no SI conversion is allowed merely
because the sensor model is known or an operator wrote a review note**. The
converter requires BOTH a file-specific --unit-manifest and a local
--unit-evidence-document. The evidence must explicitly describe the numerical
units/scaling **already present in the stored Y.Data samples** and must be
checked by a human. General sensor datasheets are not enough.

Required review-manifest fields (schematic placeholders, NOT validated
Paderborn calibration, do not copy directly into a real run):

- source_sha256: source MAT SHA256.
- vibration_channel, current_channel: exact stored channel names.
- vibration_unit = m/s²; current_unit = A: output feature units.
- vibration_stored_unit: one of m/s², m/s^2, g, V, mV.
- current_stored_unit: one of A, V, mV.
- vibration_scale_to_m_s2, current_scale_to_a: independently reviewed positive factors.
- vibration_offset_in_stored_unit, current_offset_in_stored_unit:
  zero-reference offsets in **input units**, explicit even if zero.
- stored_mat_values_calibration_verified = true: only after reviewing
  actual acquisition and MATLAB export conversion.
- evidence_document_sha256: exact local evidence-document hash.
- evidence_type: primary_dataset_documentation or dataset_author_confirmation.
- evidence_url, evidence_location, unit_evidence: source URL, exact page
  or section and detailed mapping from stored numbers to physical units.
- reviewed_by, reviewed_utc: dated human review, never inferred.

The converter applies (stored numeric value - reviewed input offset) *
reviewed factor BEFORE RMS/peak calculation. If input is g, the factor
must equal 9.80665 m/s² per g. Existing SI metadata cannot be overridden
by arbitrary gain or offset. An analog current transducer's zero-current
voltage must not be treated as current; actual Paderborn zero reference
and dSPACE conversion are still unknown.

Research and missing proof: docs/SENSOR_CALIBRATION_FINDINGS_20261105.md

Do not fabricate a manifest or assume physical units based on column names. The converter validates hash/format but cannot independently authenticate a reference. User supplied labels alone also do **not** establish real ground truth. Verify bearing label and units against source fact sheets and calibration. Separate GitHub Windows runner checks of K001 and KA04 have been reported, but none establishes the physical units of stored samples. Current stage-1 work does not claim a calibrated Paderborn training dataset.

Use `7z t` to test archive integrity, and inspect names before extracting. Extract with full paths as needed; the archive may contain many `.mat` recordings, not a single `K001.mat`. Keep `.rar`, `.mat`, raw/converted CSV, virtual environments and API keys out of GitHub. Evaluated models must never be auto-promoted to validated.

Official source: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download (CC BY-NC 4.0).