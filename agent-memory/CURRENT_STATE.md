# Current state — 2026-09-24 (end of session 2026-09-23-03, run 24)

Rewritten from scratch. Checked this run: `git log` / `rev-parse` (main
untouched), the hypothesis log (the 6 holdout ACCEPTs), the stored
fingerprint and returns (build 5, to 2026-09-21), the ledger, and pytest.

## Phase
- **Everything is on main** (Ben asked to merge, 2026-09-24): features,
  nightly hardening, exchange labels, the pattern catalogue + fingerprint,
  the analysis engine E1–E4, THE HOLDOUT (spent), its description, and the
  daily scan + paper-trading ledger. main was fast-forwarded to the
  daily-scan head.
- **No working branch.** daily-scan, analog-backtest and
  claude/great-bell-6wr1jq were merged and deleted (locally and on GitHub).
  The next branch is cut from main when Ben gives the next task.

## The daily scan (report/scan.py) and paper trading (report/paper.py)
- **Trades exactly the 6 holdout ACCEPTs, as-is.** "Strong" = one fired; no
  performance filter. Otherwise NOTHING STRONG TODAY.
- **`daily_scan` block v2 (hash `a5be2561c39c60af`; v1 `914a3afc4d05fea0`
  ran only on the pre-freeze days).**
  - Eligible = fired (unknown never fires) + liquid on T + a dated, non-UPCoM
    exchange (mirrors the holdout's gate).
  - ONE pick by: **HOSE before HNX** (Ben: focus HOSE ~85% / HNX ~12% /
    UPCoM ~3%) → validate net expectancy (per trade, frozen; ranks only) → the
    20-session mean traded value → the more liquid tier (tier 3 = most liquid
    in the code; Ben wrote "tier 1", see open questions) → symbol.
- **`paper_trading` block (hash `45ed221c5145016a`, Ben's numbers).**
  - Per signal day, net at the all-in cost.
  - No verdict before ≥ 30 scored days spanning ≥ 3 months.
  - PASS = cum > 0 AND drawdown ≥ −1.0 stake AND a majority of months
    positive.
  - FAIL = cum ≤ 0 OR drawdown < −1.5.
  - Otherwise PROVISIONAL.
  - No PASS/FAIL while the fee is PROVISIONAL.
  - VOID (no trade at entry) is not scored; STUCK (a stake, no return)
    withholds the verdict.
- **Forward record = days after 2026-09-24.** The ledger
  `research/paper_ledger.csv` is append-only and idempotent per day.
- **Smoke test, 2026-09-21: NOTHING STRONG TODAY** (280 liquid, 0 fired).
  - Seven days before the freeze are recorded (09-11 … 09-21), with one
    proposal: FPT 09-18, k5 marubozu_red + ma_50_rising + rvol_high, pending.
  - Forward record: 0 days, NO VERDICT YET.

## The research result (unchanged)
Holdout: 6 ACCEPTED, 9 REJECTED, 1 NOT TESTABLE. Per signal day at 0.40%,
the ACCEPTs run from breakout+volume_dry +0.74% down to k5 marubozu+ma50
−0.43%. That is why the forward test is per signal day. Report:
`research/reports/holdout-2026-09-10-describe.txt`.

## Verified by running it this run
- pytest **599 passed, 0 failed, 0 skipped** (DB up); `ruff check .` clean.
- Strict proofs (no exemptions):
  - new rules **41/41** (after v2);
  - re-run: holdout 33/33, E3 33/33, E4 23/23, describe 14/14;
  - earlier and unchanged: E2 46, E1 50, fingerprint 27, universe/breadth 17,
    sector 23, exchange 15, guards 5, T1 23, T2 36, T3 55, T4 20.

## Blockers / open (open-questions.md)
- **Data must flow for the forward test.** After each session:
  1. `nightly_update`;
  2. `fingerprint.build` (~20 min);
  3. `forward_returns.build`;
  4. `report.scan`.

  Then `report.paper score`. Nothing is scheduled.
- Ben: confirm the tier direction and the UPCoM/undated exclusion; the real
  broker fee (no verdict until then).
- G20 repair; X4, G19, G18, G2, G10, G11; the limit rounding / UPCoM
  reference.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben gives the next task (a new branch from main).
2. Decide how the daily pipeline runs (manual or scheduled), then scan each
   new session and score as outcomes mature.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop;
the "crowded day" idea; moving `pool_before` past 2024 (needs a new neighbours
version).

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 22–24 of
`logs/sessions/2026-09-23-session-03.md`. 4. `config/rules/protocol.yaml`
(the `daily_scan` and `paper_trading` blocks). 5. Only the code the task
touches, via `code-map.md`.
