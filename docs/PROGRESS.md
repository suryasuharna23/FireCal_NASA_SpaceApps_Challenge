# FireCal progress - 14 November 2026

## Shared data handoff update from ASUS

The continuation commit `90da7d7` and onboarding commit `dac4c13` are integrated
on the same branch. The machine-specific continuation record below is retained;
its missing-input and test results describe the faiz computer before transfer.

- The real snapshot exists on ASUS: version `593ae2d95fdf`, 7,716,551 retained
  points. Existing snapshot/API checks passed there; this does not claim the new
  numerical bias audit has run.
- Processed and sources ZIPs with per-file manifests/checksums are prepared under
  `data/interim/share/`. The sources package now also includes the prior
  `regional-audit/selection_lock.json` required by the continuation runner.
- [Data onboarding](DATA-ONBOARDING.md) explains transfer, setup and verification.
  Upload to shared storage and installation on the recipient computer remain pending.
- The earlier 126-test result on ASUS predates the new audit module. The faiz
  test results below are preserved with their own machine-specific limitations.
- Scientific status remains experimental; the next step after transfer is input
  preflight, then baseline reproduction and the fixed-coefficient audit.
- Integration validation on ASUS: all 16 new audit tests pass; Ruff lint/format
  pass. Preflight against the extracted packages reports ready, 27 point
  partitions and 463 verified API responses. The full numerical audit is pending.

## Branch and continuation

- Branch: `feat/firms-api-acquisition`, based on hsbu's `54a2ed9`.
- Continuation checkout on this computer:
  `C:\Users\faiz\Documents\02 Areas\compe\lonba nasa\FireCal-hsbu`.
- The original checkout's uncommitted onboarding material remains in
  `FireCal_NASA_SpaceApps_Challenge` on `main`.
- The supplied [handover](handover-bias-audit.md) is preserved as context. Its
  results and previous-machine paths are not evidence of files existing here.

## Previously completed by hsbu

The branch contains real Indonesia acquisition, country filtering, the pilot,
regional-model audit, and experimental extension. See
[the extension report](indonesia-extended.md) and
[regional findings](regional-audit-findings.md).

The handover reports snapshot `593ae2d95fdf`, 7,716,551 retained observations,
national January-October 2026 bias -12.20%, r 0.9944, and 8/27 eligible provinces
meeting both targets. Those values have **not been reproduced on this computer**.
The previous model was retained after its candidate-selection rule failed.

## Added in this continuation

- [x] Identify hsbu's remote branch and inspect its acquisition/audit code.
- [x] Create a separate checkout tracking his existing branch.
- [x] Install its locked Python workspace without changing the lockfile.
- [x] Preserve the handover and create this progress tracker (the referenced
      tracker was not present in the pushed branch).
- [x] Implement [the fixed-coefficient audit runner](../scripts/audit_indonesia_bias.py)
      and [calculation module](../pipeline/firecal/bias_audit.py).
- [x] Add missing-input preflight, receipt/path-relocation/checksum checks,
      immutable pre-analysis input manifest, and all-area baseline reproduction.
- [x] Implement monthly source/version/platform accounting, global subset
      divisors, leave-one-out and single-platform sensitivity, Terra/Aqua
      comparisons, zero-month handling, and explicit unavailable metrics.
- [x] Add tests using hand-calculated examples and a small generated snapshot.
      These tests do not substitute for the real snapshot audit.
- [x] Review official exposure references and create an
      [evidence register](bias-audit-exposure-evidence.csv), retaining unknowns.
- [x] Write [the diagnostic and next-evaluation protocol](bias-audit-protocol.md).
- [ ] Reproduce the actual snapshot's national and all-province baseline.
- [ ] Run real SP/NRT/platform/month sensitivity and interpret the tables.
- [ ] Obtain region/product-specific observation exposure and gap evidence.
- [ ] Write evidence-backed numerical findings and finalize a candidate protocol.

The model, serving configuration, existing datasets, and deployment are unchanged.
No new real-data acquisition was performed. The continuation is published on
hsbu's existing branch; numerical execution remains pending the data transfer.

## Missing input, not an unsuccessful scientific result

A bounded search in this computer's Documents, Desktop and Downloads found the
handover and the earlier synthetic onboarding data, but not hsbu's real snapshot.
The new checkout has zero real point partitions and no acquisition manifests or
previous selection lock. The preflight therefore reports not ready.

Transfer these directories, preserving their relative contents:

```text
data/interim/indonesia-extended-20261114/processed/
data/interim/api-acquisition/
data/interim/regional-audit/selection_lock.json
```

The acquisition folder must include nested CSV responses and JSON sidecars,
not merely its summary files. Preserve original historical raw archives too if
full upstream reprocessing is required; this audit consumes the already prepared
snapshot, and does not rebuild it. Never transfer `.env` or credentials in a
public archive.

Once transferred, use explicit paths if the layout differs:

```powershell
uv run --no-sync python scripts/audit_indonesia_bias.py --check-inputs
uv run --no-sync python scripts/audit_indonesia_bias.py
```

The first command checks prerequisites and saved API responses without writing
results. The second freezes inputs before analysis, then requires baseline
reproduction before completed diagnostics are published. Existing output
directories cannot be reused. A failed numerical run retains only its input
lock; inspect for a completed `audit.json` before treating a run as successful.

## Validation on this machine

| Check | Observed result |
| --- | --- |
| New audit tests | 16 passed, including a complete miniature snapshot/receipt run |
| Full Python suite | 116 passed; 26 existing fixture setup errors on Windows |
| Ruff lint | Passed |
| Ruff format | Passed, 86 Python files already formatted |
| `git diff --check` | Passed |
| Real-data input preflight | Exit 2, not ready; 24 missing prerequisite paths/categories |

The 26 setup errors all come from the existing pipeline fixture's directory
symlink (`pipeline/tests/conftest.py:31`) and `WinError 1314` in this Windows
session. The fixture and OS settings were left unchanged. The full suite also
reports the existing Starlette/HTTPX deprecation warning. The blocked test bodies
are not claimed to have passed.

The new tests cover hand-computed conversion and AOI weighting, global subset
divisors, zero local months, unavailable global subsets, preserved source
versions, one-month metrics, tamper detection, relocated receipts, mismatched
baseline rejection, and input/output immutability. Generated fixtures are clearly
separate from hsbu's real-data evidence.

The local machine-readable readiness report is
`data/interim/bias-audit-readiness-20261114.json` (ignored by Git). A fresh terminal
can run the preflight without relying on uv's installation location:

```powershell
.\.venv\Scripts\python.exe scripts/audit_indonesia_bias.py --check-inputs
```

No real snapshot input manifest, numerical audit tables, or new bias findings
were produced. Baseline reproduction remains pending transfer. Exposure-aware
correction and a genuinely prospective evaluation remain proposals.
