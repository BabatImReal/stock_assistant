# Current state — 2026-09-24 (end of session 2026-09-24-01, run 6)

Rewritten from scratch. This session ran in a cloud container with **NO
database and no data files**. The DB figures below come from the previous
session's checked state, NOT re-read. This run checked: `git log`, the
hypothesis log in git (16 holdout rows), pytest, ruff.

## Phase
- **On main (`f53b72a`):** features, nightly hardening, exchange labels, the
  pattern catalogue (T1–T4), the fingerprint (T5).
- **On `features/analog-backtest` (`2ed5bef`):** the analysis engine E1–E4 and
  THE HOLDOUT (run once 2026-09-24; spent). Awaiting Ben's review.
- **On `claude/great-bell-6wr1jq`:** `features/analog-backtest` +
  session 2026-09-24-01: the fee research and **`describe-holdout`** (built,
  tested, NOT yet run on real data).

## Git
- `main` = `f53b72a`. Only Ben merges.
- `features/analog-backtest` = `2ed5bef` (the holdout commit).
- `claude/great-bell-6wr1jq` = fast-forwarded to `2ed5bef`, then this
  session's commit on top. It is the only session branch.

## The research result (unchanged; the holdout is spent)
- N = 1,554 → 1,454 testable → 82 passed discovery → 16 held on validate →
  **holdout: 6 ACCEPTED, 9 REJECTED, 1 NOT TESTABLE** at the registered 0.40%
  all-in.
- Only 2 accepts are also significant: k3 marubozu_red+breadth+rvol (p 0.022)
  and k5 marubozu_red+ma_50_rising+rvol (p 0.007).
- Report: `research/reports/holdout-2026-09-10.txt`. Log: slice "holdout",
  protocol `0106fab4dc2f35a2`, build 5.

## Fees (researched this session → knowledge/context-vietnam.md)
- Tax 0.10% on each sale. Exchange fee 0.03% a side, even at "zero-fee"
  brokers. Commission 0–0.35% a side (legal cap 0.5%).
- All-in round trip: **0.16%** (zero-commission) / **0.40%** (registered) /
  **0.60%** (0.25% a side). 0.10% is unreachable.
- Verdicts at those costs, read off the report's break-even column (exact,
  since NET is linear in the gross): **10 / 6 / 5 accepted.**
- Ben does not know his fee. `costs.yaml` is unchanged (0.15%/side,
  PROVISIONAL).

## New this session: describe the holdout (information only)
- `backtest/risk.py`:
  - per trade: avg win, avg loss, payoff, best, worst;
  - max drawdown and worst losing streak on a fixed stake per signal day
    (basket, and one random pick over 1,000 seeded paths: median and
    worst-5%);
  - the share of 60-pick stretches ≤ 0.
- `protocol.describe_holdout` / `run_describe_holdout`: takes the verdicts
  from the log and re-derives the same de-clustered trades. It **refuses
  unless the count, the mean NET and the build match the log**. It writes no
  log row and is safe to repeat. Costs: 0.16 / 0.40 / 0.60%.
- **Run 6:** Ben ran it on an OLD checkout (`features/analog-backtest`, where
  the command does not exist). It fell through to `run()` and crashed in
  `_slice` (`tuple.index`). `run()` now names an unknown command. **Ben must
  check out `claude/great-bell-6wr1jq` first.**
- **Run on Ben's machine** (DB up, on this branch):
  `uv run python -m vnstock_research.backtest.protocol describe-holdout` →
  `research/reports/holdout-2026-09-10-describe.txt`.
- **Not computed yet.** No real numbers exist.

## Verified by running it this run
- `uv run pytest` → **534 passed, 0 failed, 24 skipped.** The 24 skips are
  the DB tests (no database here). 537 + 21 new tests − 24 skipped = 534
  (11 test_risk, 9 test_holdout, 1 test_protocol).
- `uv run ruff check .` → clean.
- Strict mutation check of the new code: **15/16 killed**. The survivor is
  equivalent: the `losing_windows` short guard (NaN either way).

## Blockers / open
- **Ben:** run `describe-holdout` and paste the report; choose a broker or
  confirm the fee.
- How G9 (one pick) weighs the weak-p accepts; the 2026 weakness;
  `pool_before` for the look-alikes.
- The paper-trading pass bar: to be written down BEFORE paper trading starts.
- G20 repair; X4, G19, G18, G2, G9, G10, G11; the limit rounding / UPCoM
  reference to confirm.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben runs `describe-holdout`; analyse avg win/loss, drawdown and streaks
   for the 6 accepts (especially the 2 significant ones) at 0.16/0.40/0.60%.
2. Fee fixed from a real order confirmation (the fee ÷ the order value).
3. Ben reviews and merges `features/analog-backtest` (+ this branch).
4. G9: rank to one pick; then the paper-trading pass bar; then the daily scan.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. `logs/sessions/2026-09-24-session-01.md`.
4. `research/reports/holdout-2026-09-10.txt` (+ `-describe.txt` once run),
`knowledge/validation.md`, `knowledge/context-vietnam.md` (fees).
5. Only the code the task touches, via `code-map.md`.
