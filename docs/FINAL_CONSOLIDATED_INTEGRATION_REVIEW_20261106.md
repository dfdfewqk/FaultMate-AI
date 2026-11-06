# FaultMate AI — single-branch consolidated integration review (2026-11-06)

**Purpose:** prepare ONE draft review surface for the accumulated existing
program, without merging to `main`, activating unapproved ML, adding new
equipment diagnostics, downloading new study data, making paid API calls or
building a release archive. Main still requires explicit review and
user-owned final acceptance.

## Code inventory actually checked

- Consolidated source parent: `work/faultmate-stage7-final-integration-cancel-safety-20261106`
  at `196aa760efde78e2476549aff36b752291270eaf`.
- GitHub compare versus preserved `main` `483f7229b28b7dc90201aa658cf8c0eaa5b3ab41`:
  **304 commits ahead, 0 behind, 167 changed files** at the checked parent.
  This is a *difference/ancestry* observation, not a review verdict and
  does not assert all non-ancestor side branches are byte-for-byte included.
- Main ancestry follows #1 → #6 → #8 → #9 → … → #38, through their
  nested bases. #2/#7 were closed without merge, replaced by #3/#8.
- IMPORTANT side branches #3 (Windows integration), #4 (AI transport),
  #5 (Paderborn raw evidence) are **diverged**, not direct ancestors of #38.
  #6 explicitly documents **manual reconciliation** of their functionality.
  The checked consolidated source has:
  - `setup_windows.bat`, `start_windows.bat`,
    `tests/windows_launcher_smoke.py` and native Windows browser tests;
  - `faultmate/integration/agent.py` opt-in preview-bound context and
    blocked credential redirects; mocked HTTP/consent tests;
  - `scripts/audit_paderborn_raw_recordings.py`, original archive checksum,
    identity and duplicate tests.
  This **does not claim** each side-branch commit has been merged.
  Closing side PRs requires a separate code-review decision; leave untouched.
- Latest parent [Actions #42152276063](https://github.com/dfdfewqk/FaultMate-AI/actions/runs/42152276063):
  **5/5 completed SUCCESS**; Linux **586 passed, 1 warning**; Windows
  BAT→localhost/native Chromium; separate Chromium UI; actual original K001
  and historical known-damaged KI21 original RAR replay. Any changes on this
  consolidated review branch require a new **exact HEAD** CI pass.

## Executable paths in this accumulated source

| Path | Concrete behavior | Confirmed limitations |
|---|---|---|
| Local P7.2 diagnosis | 3 equipment categories, 7 hand-curated cases, 8 references, keyword candidate suggestion, explicit operator case choice, emergency hold | Deterministic educational assistance, not proven physical root-cause diagnosis |
| DeepSeek assistant | Explicit review preview + SHA digest + individual consent, only bounded allowlisted candidate/question indices, mocked network/redirect/error and local fallback | No user's actual API key/paid provider response tested. Do not call without consent |
| Native ML CSV API | Strict input shape/limit; only independently approved calibrated production models may infer | No approved SI model: **unavailable**. Do not load study classifier into this path |
| Optional original Paderborn RAR analysis | Local UI→bounded temporary stream→official archive hash→80 original paired MAT→12 unitless features→frozen experimental score; cleanup/busy lock | Real K001 and KI21 CI only; 7-Zip dependency; research-only, no maintenance/field or normal specificity guarantee |
| Optional feature-JSON research route | Existing dimensionless feature-report score | Uploaded JSON metadata does not prove original archive identity |
| Local runner | Python launcher and Windows BAT, port local 127.0.0.1; recover missing FastAPI/NumPy/SciPy in existing Windows venv | Windows GitHub runner passed; user's real PC not yet accepted |

## Model evidence, no-go and data

- Original 12 Paderborn bearing / 960-MAT source verification and **956 unique**
  original recordings were used for experimental training/evidence.
- Existing classifier uses **ten physical development bearings**, full
  4-condition 80-record pooled median 12-feature input, `0.5` frozen cutoff.
- Historical **8-damaged-only** evaluation detected 7, missed **KI21**.
  This cannot establish specificity/false-positive rate; KI21's subsequent
  many replays are **not new independent evaluations**.
- Six native healthy Paderborn physical bearings are already opened. The
  KAIST and BJTU source protocols cannot be used as independent validation
  of this frozen model without a **separate** research contract.
- SI measurement scaling and commercialization of original Paderborn
  CC BY-NC 4.0 evidence remain unverified. The current research model stays
  unapproved, runtime inference inactive, never a work/safety authorization.

## Review/acceptance checklist — no silent completion

1. [x] Confirm concrete nested PR bases and preserve non-ancestor side
   branches #3/#4/#5, rather than blindly marking them merged.
2. [x] Verify consolidated source exposes safety guards, Windows launch,
   Python/JS user routes and original-record audit code.
3. [x] Keep original source/model/user files unchanged and paid API disabled
   in CI; keep the primary `main` untouched.
4. [ ] Verify this new consolidated review branch's **final SHA** passes
   all five existing Linux/Windows/browser/original-data jobs.
5. [ ] Manual PR diff review before any merge to `main`; 167 files and
   304 commits at parent require particular care for overlapping code.
6. [ ] Real user Windows PC double-click and local browser/actual original RAR
   acceptance; hosted GitHub Windows CI **does not replace user PC**.
7. [ ] Optional charged DeepSeek live one-call test only with explicit user
   consent and account/key. Never claim it already happened.
8. [ ] Production model approval **blocked** until independent physical
   healthy tests, true engineering units, exact input contract and license.
9. [ ] EXE/ZIP deployment deliberately not performed.

**No-go today for production field ML and full release**, independent of the
fact that present local code/test paths pass automated regression.
