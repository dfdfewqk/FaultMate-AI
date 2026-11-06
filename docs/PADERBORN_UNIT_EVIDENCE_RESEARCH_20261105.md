# Paderborn KAt 2016 — stored MATLAB signal units / calibration evidence investigation

Date: 2026-11-05 (KST). Stage: **unit provenance research in progress, not verified**.

## Primary-source findings

- KAt original benchmark portal: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter . Original data license is CC BY-NC 4.0; non-commercial research use only without additional permission.
- Lessmeier et al. (2016), Section 4.1, PDF page 7: https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf
- Reported sensing chain: LEM CKSR 15-NP motor phase current transducer, 25 kHz analog low-pass, 64 kHz ADC; PCB Piezotronics 336C04 accelerometer, Kistler 5015A charge amplifier, 30 kHz low-pass, 64 kHz acquisition.
- University rig description: https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/test-rig-and-measurement-equipment . This describes *measured quantities* (phase current and surface acceleration), NOT the numeric representation in published MATLAB Y.Data arrays.
- Zenodo mirror with published per-RAR checksums: https://zenodo.org/records/15845309 . Checksums establish archive identity, not physical calibration.
- Published original MAT records examined via existing Windows CI have empty Unit fields for vibration_1 and phase_current_1; details in docs/PADERBORN_DATASET_READINESS.md and docs/KA04_RAW_DUPLICATE_AUDIT_20261104.md.

## External cross-checks (not primary calibration evidence)

- An independent 2026 dataset normalization tool explicitly marks Paderborn vibration unit as unknown in its release notes: https://data.safetycli.com/packages/pypi/bearing-datasets/changelog . Its general conversion system refuses unknown units. This supports caution but is not proof of the original stored units.
- Another dataset user's documented original MAT inspections also report blank Unit fields: https://github.com/RocketWill/operating-state-aware-monitoring/blob/main/data/paderborn/README.md . Secondary, not authoritative.

## Decision table

| Claim | Evidence | Status |
| --- | --- | --- |
| phase_current_1 is sampled from a motor current transducer | Original benchmark paper §4.1 | verified physical quantity |
| vibration_1 is sampled from an accelerometer at bearing housing | Original benchmark paper §4.1 | verified physical quantity |
| sampling rate for both channels ~64 kHz | Original paper §4.1 | verified nominal acquisition setting |
| stored MATLAB Y.Data vibration values already have m/s² units | no source-specific published numerical scaling found | **not verified** |
| stored MATLAB Y.Data phase current values already have A units | no source-specific published numerical scaling found | **not verified** |
| numeric V/ADC to SI factors and charge-amplifier/current-transducer settings applied to stored values | no original acquisition-chain calibration documentation found | **not verified** |
| source files' Unit entries alone prove SI | Unit values empty in inspected original records | false |

## What evidence would resolve stage 2?

Obtain a verifiable original **dataset-specific** statement or acquisition/export calibration log (e.g. dataset authors' written confirmation) that explicitly states the stored Y.Data numeric units and any channel conversions. A standalone manufacturer's sensor datasheet or 64 kHz sampling frequency cannot establish this.

Specific questions to send to the Paderborn KAt data contact:

1. For the *2016 bearing damage benchmark dataset* files such as N15_M07_F10_K001_1.mat, do stored Y.Data values of vibration_1 already represent m/s² (or g, V, raw counts), and phase_current_1 already represent A (or V, raw counts)?
2. What exact numerical factors, offsets and filter/charge-amplifier gains were applied before the MATLAB export? Are the factors identical for all 32 bearings and all four operating conditions?
3. If raw values are in volts/counts, what precise conversion factors can reconstruct m/s² and A? Is there a published calibration/acquisition configuration document containing these factors?
4. Do any older versions of the 2016 archive or measurement logs include populated Unit fields or metadata not present in the Zenodo mirror?

Primary university contact listing (for later manual contact, not yet contacted): https://www.uni-paderborn.de/en/person/97759 . **No external email has been sent.**

## Software and use restrictions

- The existing converter default remains fail-closed for unknown units; no real SI CSV, ML training, accuracy results or production activation are legitimate while the above evidence is unverified.
- `scripts/convert_mat_to_csv.py` now demands a hash-bound source document, documented conversion factors, timestamp and reviewer for manual override of missing Unit entries. Even this cannot attest the document's truth; the reviewer must inspect actual documentation that applies to the **stored MAT numeric array**, not just a sensor's nominal response.
- Any research-only dimensionless/raw-feature baseline must be separately labelled *uncalibrated experimental raw-signal analysis*. It must never be passed into current three SI-named fields, represented as m/s²/A, or automatically activated as the validated model.
- Stage 2 is **not complete** until the primary-source unit question is settled or an explicitly distinct uncalibrated research pathway is approved. The code guard can be ready while factual evidence is still missing.
