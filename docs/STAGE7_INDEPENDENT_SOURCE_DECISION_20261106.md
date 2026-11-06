# Stage7 — independent physical-bearing source decision (2026-11-06)

**Decision: NO GO for new frozen-model independent healthy specificity evaluation.**
This is an offline, research-only source-admissibility review, **not** a
newly preregistered trial, data download, classifier score, or field validation.

## Original, already reviewed source options

| Dataset | Source-backed facts | Why it cannot count as a new independent Paderborn-model normal test |
|---|---|---|
| **Paderborn 6203** | Six physical healthy bearings K001–K006, four fixed conditions, 20 original paired MAT measurements per condition (author's primary KAt DataCenter). | **Every healthy physical bearing was already opened.** Re-downloading/partitioning K001–K006 doesn't create a new specimen. Prior KI21 false negative remains exposed, and the original CC BY-NC 4.0 license does not permit commercial dataset reuse without permission. |
| **KAIST varying load** | Existing primary-source review confirms different vibration/current sampling rates, three conditions. | Not the frozen model's native four-condition, 64 kHz, 80 paired-MAT input protocol. |
| **KAIST varying speed** | Existing primary-source review confirms different vibration/current sampling rates and no established exact four-condition matching. | Cannot be scored as if it were Paderborn without a separately designed and independently validated domain study. |
| **BJTU-RAO/PHM24** | Source-author documentation describes **one normal health-state folder**, nine working conditions and up to four original CSVs per condition, not nine physically distinct healthy bearings. | Physical IDs and original raw file checksums are unverified, bearing type/conditions differ, and source-data commercial license is unconfirmed. |

Primary evidence: [Paderborn KAt university description](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter/data-sets-and-download),
[Paderborn data and source checksums](https://zenodo.org/records/15845309).
Existing machine-audited candidate metadata:
`docs/EXTERNAL_HEALTHY_SOURCE_CANDIDATES_20261105.json`;
`scripts/audit_external_healthy_compatibility.py`;
`scripts/audit_bjtu_primary_layout.py`.

## New guard implemented this step

- `scripts/audit_independent_bearing_preflight.py` verifies the **existing pinned frozen model** and existing source admissibility report, reads a visibly **DRAFT** plan, refuses previously opened Paderborn physical IDs (all development, opened holdout, eight previously examined damaged) and rejects duplicate speculative asset IDs/checksums.
- A SHA-shaped string is **metadata, not a verified raw file hash**. Even a proposal with perfect-looking fields can never bypass the original-byte source/identity/physical-bearing scientific review.
- The current draft records **no newly verified physical healthy/damaged specimens**. No minimum class sample sizes, primary outcome metric, confidence interval or acceptance threshold have been silently chosen after inspecting KI21.
- The output always reports **no new independent accuracy/specificity, no model training/inference and no runtime approval**.
- This adds a check on *readiness*, not a proof of deterministic raw feature extraction. Prior Stage7 within-bearing IQR and KI21/current-scaler exploratory findings are left intact.

## Work that remains conditional on genuinely new evidence

1. Obtain a **new physical-specimen** healthy/damaged dataset with legally usable original signals and provenance. Do not treat different sessions/conditions or segments as new physical bearings.
2. Determine whether its paired vibration/current measurements match the frozen 6203 4×20 64kHz signal contract. If not, scope an entirely **separate** external-domain project; do not run the existing model as though compatible.
3. Before opening outcomes, freeze independent sample counts, principal bearing-level metric and interval calculation, sample selection/split and acceptance criteria. Only then construct an immutable prospective manifest, verify source raw bytes/labels/hash overlap and perform any new evaluation.
4. If source permission, independent healthy evidence, physical SI calibration, user Windows acceptance or the API input contract remains unresolved, retain current research-only ML state and **block field deployment**.

## User-protection rule

No data or model overwrite, no main branch merge, no unauthorized paid
DeepSeek requests, and no new EXE/ZIP before independent validation plus final
Windows acceptance. Existing rule-based diagnostics remain available.
