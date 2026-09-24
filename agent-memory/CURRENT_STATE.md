# Current state — 2026-09-24 (end of session 2026-09-24-01, run 7)

Rewritten from scratch. This session ran in a cloud container with **NO
database**. The holdout-description numbers come from Ben's own run
(`research/reports/holdout-2026-09-10-describe.txt`, pasted in, saved to git).
This run checked: git log, the 16 trade counts against the holdout report, and
pytest (from run 6).

## Phase
- **On main (`f53b72a`):** features, nightly hardening, exchange labels, the
  pattern catalogue (T1–T4), the fingerprint (T5).
- **On `features/analog-backtest` (`2ed5bef`):** the analysis engine E1–E4 and
  THE HOLDOUT (run once 2026-09-24; spent).
- **On `claude/great-bell-6wr1jq`:** all of the above + session
  2026-09-24-01: the fee research, `describe-holdout` (built, and run by Ben),
  the clear unknown-command error, and this analysis. Ben should work from
  this branch; `features/analog-backtest` lacks `describe-holdout`.

## Git
- `main` = `f53b72a`. Only Ben merges.
- `features/analog-backtest` = `2ed5bef`.
- `claude/great-bell-6wr1jq` = `2ed5bef` + `51b5aa9` (describe + fees) +
  `ae8845c` (unknown command) + this run's commit (the report + notes).

## The research result
- Holdout (registered, per trade, 0.40%): **6 ACCEPTED, 9 REJECTED, 1 NOT
  TESTABLE**. Only 2 accepts are significant (the two marubozu_red + rvol
  variants).
- **Run 7 finding (knowledge/validation.md):** the per-trade expectancy is
  not what a one-stake-a-day pick earns. Totals in % of one stake over
  2024-01 → 2026-09, at 0.40%:

| accepted | per-trade sum | one stake a day | its max drawdown |
| --- | --- | --- | --- |
| k3 breakout+volume_dry | +31% | **+30.5%** | −34% (bad path −45%) |
| k3 higher_lows+breadth+ma50 | +86% | **+19.8%** | −41% (bad −71%) |
| k3 breakout+above_ma50+volume_dry | +15% | +12.6% | −48% |
| k3 three_black_crows+breadth+rvol | +40% | +4.5% | −37% |
| k3 marubozu_red+breadth+rvol | +386% | **−2.8%** | −52% (bad −94%) |
| k5 marubozu_red+ma50rising+rvol | +200% | **−117%** | −206% |

- The 2 "significant" ideas earn only on crowded days (many stocks firing at
  once). Every REJECT loses per day at 0.40%.
- Nothing is strong enough to trade real money. The best per-day results
  are small next to their drawdowns, and rare (breakout: 41 signal days in
  2.7 years).

## Fees (context-vietnam.md)
- All-in round trip: 0.16% (zero commission) / 0.40% (registered) / 0.60%.
- The fee swings the per-day totals hard: higher_lows +63% / +20% / −16%;
  marubozu+breadth +36% / −3% / −35%.
- Ben's fee is unknown; `costs.yaml` is unchanged (0.15%/side, PROVISIONAL).

## Verified (run 6; no code changed in run 7)
- pytest **534 passed, 0 failed, 24 skipped** (the DB tests; no DB here).
- ruff check clean.
- Mutation check of the describe code: 15/16 killed (1 equivalent).

## Blockers / open (open-questions.md, "After the holdout description")
- **Ben, architectural:** measure the daily-pick strategy PER SIGNAL DAY
  (one stake a day) in G9 and any future registered test? It can only be
  tested on new data or in paper trading. The holdout is spent.
- **Check the extreme trades** (−57.7%, +53.0%, −36.1%, a repeated −30.7%)
  for missed corporate actions. The describe report does not name
  symbol/date yet.
- Broker/fee choice. The G9 ranking. The paper-trading pass bar (to be
  written before starting).
- G20 repair; X4, G19, G18, G2, G10, G11; the limit rounding / UPCoM
  reference.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben answers the unit question (per trade vs per signal day).
2. Name and check the extreme trades.
3. Design paper trading (the pass bar fixed in advance, per-day unit), then G9.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop;
the "crowded day" idea (a NEW hypothesis: only for unused data).

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. `logs/sessions/2026-09-24-session-01.md`
(run 7). 4. `knowledge/validation.md` (the last section),
`research/reports/holdout-2026-09-10-describe.txt`. 5. Only the code the task
touches, via `code-map.md`.
