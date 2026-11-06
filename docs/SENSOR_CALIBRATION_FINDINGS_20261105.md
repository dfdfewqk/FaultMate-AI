# FaultMate AI — Paderborn sensor calibration evidence audit (2026-11-05)

## Verdict: physical units NOT VERIFIED

The official Paderborn MATLAB channel names 'vibration_1' and 'phase_current_1'
describe the quantities measured, but do NOT establish whether the numerical
samples stored in Y.Data are already in m/s² and A or are ADC/sensor voltages,
normalized counts, or previously converted engineering values. The inspected
real MAT records have blank Unit metadata. Neither sensor model identification
nor approximate signal amplitudes prove the stored-values calibration.

## Primary sources inspected

| Source | Direct evidence | Remaining limitation |
| --- | --- | --- |
| University [Paderborn Bearing DataCenter](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter) | Official benchmark dataset and CC BY-NC 4.0 noncommercial license | Raw numeric SI status not specified |
| [Lessmeier et al. (2016)](https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf), sec. 4.1, printed p. 7 | LEM CKSR 15-NP motor current; PCB 336C04 accelerometer + Kistler 5015A charge amplifier; synchronous 64 kHz sampling | dSPACE/DAQ scaling, offsets and saved MAT values not specified |
| [LEM CKSR 15-NP manufacturer page](https://www.lem.com/en/product-list/cksr-15np) | Analog voltage output, nominal 15 A, zero-current voltage reference near 2.5 V | Whether MAT already holds A, primary turns and actual recorded offset unknown |
| [Kistler 5015A instruction manual](https://kistler.cdn.celum.cloud/SAPCommerce_Download_original/002-121e.pdf), sections 5.3.3 and 5.4, printed p. 39 | Configurable sensitivity (pC/g and pC/(m/s²)); auto-ranging changes voltage output scale | Actual amplifier sensitivity, range and software scaling unknown |

**A component datasheet is not a dataset-specific calibration certificate.**
An unremoved current-transducer voltage zero-reference is not physical current.
A validated conversion should implement (stored_sample - input_zero_offset) *
scale_to_SI, not a scale-only multiplication.

## Minimum evidence needed before any real SI-based training

1. A dataset-author reply or original recording configuration stating the
   units of the **stored numeric MAT Y.Data** values for both channels.
2. Evidence of whether Paderborn software subtracted the LEM zero-current
   reference and applied any dSPACE gain/normalization before saving.
3. Kistler 5015A actual sensitivity/output range and PCB sensor calibration;
   specify whether the MATLAB vibration signal is stored as V, g, or m/s².
4. For the current channel, actual primary turns/reference and raw-to-A gain,
   with documented zero offset if the saved values are volts.
5. Confirmation that calibration is valid for all physical bearings and
   operating conditions, or file-specific calibration when settings differed.
6. Human-reviewed source-document copy (or explicit author communication)
   hash-bound to the precise MAT and source-specific manifest; do not
   fabricate documents, reviewer signatures or coefficients.
7. Check CC BY-NC 4.0 noncommercial restrictions before using this data.

## Code-level safety gate (not proof of actual calibration)

The experimental converter now requires an explicit *stored input unit* and
an *input zero offset* for BOTH vibration and current when converting
unverified/other-than-SI MAT fields under a reviewed manifest.

The manifest also requires original MAT SHA256, a local primary evidence
document SHA256, the exact source URL and page/section, source-specific
calibration explanation, dated reviewer and a positive scale to SI.

The numerical transformation is (sample - offset) * gain before calculating
RMS and peak, with SI/g conflicts checked and a documented physical constant
of 9.80665 m/s² per g.

**No certified Paderborn SI conversion has been performed.**
The implemented checks prove code structure and arithmetic, not the
truthfulness of a reviewer or a document. Synthetic software fixtures
are never eligible as real training inputs.

## Author clarification needed (do not send automatically)

Are Paderborn MATLAB Y.Data numeric samples for vibration_1 and
phase_current_1 already scaled to m/s² and A? If so, is there a written
record of the software-side mapping? If not, please provide the actual
Kistler charge-amplifier sensitivity/output range and LEM zero-current
reference and dSPACE scaling/offset used when recording these channels.
Were these settings consistent across the 32 bearings and four conditions?

## Step-1 status

**Manufacturer and primary-study research: complete. Protective code
and unit-offset tests: implemented. Actual dataset numerical calibration:
BLOCKED until primary source evidence is obtained.**

Do not publish SI feature CSV, trained ML, fault predictions or distribution
based on unverified MAT sample units.
