# Current state — 2026-09-25 (end of session 2026-09-25-01, run 1)

Rewritten from scratch. Checked this run: `git rev-parse origin/main`
(`dfabd5b`, untouched), the md5 of all four research/*.csv logs (identical
before and after), `git diff origin/main --stat` (only new files + the
cherry-pick), pytest and ruff. This was a cloud session with NO database.

## Phase
- **main (`dfabd5b`):** everything through complements_1 (run 25).
  Untouched; only Ben merges.
- **`features/structural-features` (`49614c6`, from another session, run
  26):** structural features + batch structural_1. Still awaiting Ben.
  Its memory (run 26) is on that branch, not on main.
- **`claude/design-system-pattern-history-aqbkd8` (THIS session's one
  branch, cut from main):** the pattern-history study. Ben asked for
  `features/pattern-history`; the cloud harness pins the session to this
  name. Rename, merge or delete: Ben's call.

## Git (claude/design-system-pattern-history-aqbkd8)
1. `961dff9`: cherry-pick of 1b04481 (structural.py, structural.yaml,
   test_structural.py). Code + tests only: no batch, no log rows.
2. `0726d88`: the pattern-history study + tests.
3. The memory commit for this run.

## Pattern history (INFORMATION ONLY; built, NOT run on real data)
- `backtest/history.py` + `config/rules/history.yaml`:
  - 21 registered patterns + 8 structural signals (structural_1's
    comparisons, unchanged);
  - 2012-01..2025-12, 2026 refused;
  - k 3 and 5, GROSS;
  - per month / year / period / all, × regime (index vs MA50 on the signal
    day): fires raw + de-clustered, mean / median / hit (gross > 0),
    base on every judged liquid day, edge;
  - the market itself as `ALL_LIQUID`.
- Point in time: each period (discover 2012-19, validate 2020-23,
  holdout_spent 2024-25) through `evidence.validated` with before = the
  next period's start.
- Summary: fixed rules (years beating the base, LEANS on the best 2 years,
  up vs down ≥ 3 pts, per period) + a coin-flip yardstick for luck.
- Writes ONLY `research/reports/pattern-history.{txt,csv}`. No log row, no
  p-value, no holdout path.
- **Ben runs it:** `uv run python -m vnstock_research.backtest.history`
  (needs the structural fingerprint `5_f6181075e5962796` on build 5 and
  the returns). About 2-3 min expected (synthetic smoke: 325k liquid rows
  in 50 s).
- No top patterns are known yet: nothing was run on real data.

## Verified by running it this run
- pytest **658 passed, 0 failed, 24 skipped** (the skips are DB tests; no
  DB in this container); `ruff check .` clean.
- Strict mutation proof on history.py: **32/32 genuine**.
- Earlier proof scripts are not in the repo (they lived in old scratchpads),
  so they were NOT re-run. No existing file changed, and the suite passes.
- research/hypothesis_log.csv, hypothesis_log_batches.csv,
  neighbours_log.csv, paper_ledger.csv: byte-identical.

## Batches so far (candidate generation; the holdout stays sealed)
- complements_1 (main): N 3,864 → 151 candidates.
- structural_1 (features/structural-features only): N 3,024 → 236.
- NONE materially stronger than the six holdout ACCEPTs.

## The daily scan + paper trading (on main, unchanged)
- daily_scan v2 trades the 6 holdout ACCEPTs, HOSE first.
- The forward record starts after 2026-09-24. There are no forward rows
  yet, because the pipeline does not run.

## Blockers / open (open-questions.md)
- Ben: run the pattern-history study; the branch name.
- Ben: review features/structural-features; whether any candidate joins the
  forward test (a new daily_scan version, before forward rows exist).
- **Data must flow for the forward test.** After each session:
  1. `nightly_update`;
  2. `fingerprint.build` (~20 min);
  3. `forward_returns.build`;
  4. `report.scan`.

  The structural fingerprint is a separate ~24-min build. Nothing is
  scheduled.
- Ben: the tier-direction wording, the UPCoM/undated exclusion, the real
  broker fee.
- G20 repair; X4, G19, G18, G2, G10, G11.

## Ben's standing expectations
Research reaches 100%; "ready for money" at least 50–60%. Focus HOSE ~85% /
HNX ~12% / UPCoM ~3%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben runs the pattern-history study and reads its summary.
2. Ben reviews features/structural-features and this branch.
3. Run the daily pipeline so the forward record starts.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); base quality / VCP; sector RS (needs point-in-time labels);
precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3.
`logs/sessions/2026-09-25-session-01.md`. 4. `config/rules/history.yaml`.
5. Only the code the task touches, via `code-map.md`.
