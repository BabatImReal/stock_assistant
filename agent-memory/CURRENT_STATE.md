# Current state — 2026-09-24 (session 2026-09-23-03, run 20, BEFORE the holdout run)

Rewritten from scratch. Checked this run: `git log`, the hypothesis log, the
stored returns (build 5), `job_run`, pytest. This is the state at COMMIT 1:
the holdout is frozen and its runner is built, but it has NOT been run.

## Phase
**On main (`f53b72a`):** features, nightly hardening, exchange labels, the
pattern catalogue (T1–T4), the fingerprint (T5). Untouched; Ben merges.
**On `features/analog-backtest`:** design, E1, E2, E3 and E4 are built; E1–E3
are approved and E4 was reported to Ben. **Now: the holdout (run 20).**

## The holdout freeze: F = 2026-09-10
- Computed, not hardcoded:
  - `python -m vnstock_research.backtest.protocol freeze` (`freeze_date`) on
    the stored returns (build 5; last settled session 2026-09-21, the CafeF
    end-of-day file loaded 2026-09-22 08:29 UTC);
  - F = the last session before the first entry since 2024-01-01 whose k=3 or
    k=5 outcome is still `pending`. That entry is 2026-09-11: 5 k=5 exits are
    deferred at the floor (e.g. KOS closed −7% on 2026-09-21).
- Checked: 0 pending outcomes at k=3 and at k=5 for entries in
  [2024-01-01, 2026-09-10]; all of them resolve by 2026-09-21.
- `registered.slices.holdout.end = "2026-09-10"`. The protocol hash leaves out
  the holdout end (the one value the registration left open), so it is still
  `0106fab4dc2f35a2`, the same as the E3 log.

## The holdout runner (`backtest/protocol.py`; `run` still refuses "holdout")
- `holdout_plan`:
  - ONLY the hypotheses that held in the latest validate run (16);
  - refused if the end is not frozen, if the registration changed, or if the
    log has ANY holdout row (it runs once).
- `holdout_verdict` applies `holdout_rule` as written (no min_edge):
  - ACCEPT = the discover sign is kept AND net expectancy > 0;
  - below 30 de-clustered occurrences: NOT TESTABLE, never a pass.
- `holdout`:
  - through the gate (`validated`) with `cutoff` = the day after the last
    settled session; entries after F are cut;
  - refuses any entry up to F whose outcome is not final;
  - de-clustering and the date-block p-value come from `evaluate`, as on
    every slice.
- **Information only, beside the verdict:**
  - the p-value;
  - net and the verdict at ALL-IN round-trip costs of 0.10%, 0.25% and
    0.40%: both broker fees plus the 0.10% tax. The registered cost is
    2 × 0.15% + 0.10% = 0.40%;
  - the break-even cost.
- `run_holdout` appends slice "holdout" to the log (protocol hash, code hash,
  build) and writes `research/reports/holdout-2026-09-10.txt`.

## Verified this run (before the run)
- pytest: **537 passed, 0 failed, 0 skipped**; `ruff check .` clean.
- Strict proofs:
  - holdout **33/33**;
  - E3 33/33 re-run (5 mutants retargeted to the same lines after the shared
    helpers were extracted);
  - E4 23/23 re-run.

## Next
1. COMMIT 2: run the holdout ONCE, then log, report and memory.
2. Ben reviews; Ben merges.
3. Then G9 (ranking to one pick) and the daily scan.

## Blockers / open
- **For Ben:** the E3 questions; `pool_before` for the look-alikes after the
  holdout; the broker fee (NET is provisional).
- G20 repair; X4, G19, G18, G2, G9, G10, G11.
- The limit rounding rules and UPCoM's reference are still to be confirmed.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.
