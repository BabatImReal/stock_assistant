# Current state — 2026-09-26 (session 2026-09-26-01, run 1)

Rewritten from scratch. Checked this run on Ben's machine (DB up): the four
research CSVs' md5 (all byte-identical to the expected values after the
history run), that the report wrote ONLY the txt + csv (`git status`), and
the three report sanity checks. Did NOT re-run pytest this run (report-only
run); the branch's last suite was 658 passed / 24 skipped (cloud session).

## Phase
- **main (`dfabd5b`):** everything through complements_1 (run 25). Untouched.
- **`features/structural-features` (`49614c6`):** structural features + batch
  structural_1. Awaiting Ben's review.
- **`claude/design-system-pattern-history-aqbkd8` (checked out now):** the
  pattern-history descriptive study, built by the 2026-09-25 cloud session and
  RUN on real data this run. HEAD now adds the report + CSV + this memory.
  NOT merged. Rename/merge/delete: Ben's call.

## What this branch is (pattern history, INFORMATION ONLY)
- `backtest/history.py` + `config/rules/history.yaml`: an exploratory
  DESCRIPTION of how all 21 patterns + 8 structural signals behaved by
  year × month × regime, 2012–2025 (2026 refused). Per-period gate
  (discover 2012–19, validate 2020–23, holdout_spent 2024–25 shown for
  understanding only). De-clustered stats vs the judged base; tidy CSV +
  readable report + a fixed-rule SUMMARY with a coin-flip yardstick.
- **NOT an edge.** No hypothesis-log rows; holdout stays sealed. Many signals
  × years × months × regimes were looked at with no correction. A "consistent"
  signal here is at most an idea for a NEW registered test on the forward
  ledger — 2024–2025 is spent.
- Ran in ~2 min. Fingerprint `5_f6181075e5962796` (structural featureset)
  loaded fine; the ~24-min structural build was NOT needed.

## Report findings (research/reports/pattern-history.{txt,csv})
- **Most consistent k=3:** three_black_crows (13/14 yrs, +5.9 pts, hit
  54.4% vs base 48.5%, 2,528 fires) > higher_lows (13/14, +3.2, 6,577) >
  marubozu_red (13/14, +2.2, 33,212) > tight_range (12/14, +2.5) >
  inverted_hammer (12/14, +1.4).
- **Most consistent k=5:** higher_lows (13/14, +3.4, 6,327) >
  three_black_crows (13/14, +3.1, 2,473) > inverted_hammer (13/14, +1.7) >
  marubozu_red (13/14, +1.6) > tight_range (12/14, +1.9).
- **#1 vs luck:** a coin flip beats the base ≥13/14 yrs only 0.1% of the time
  → ≈0.0 of 29 signals by chance on the consistency axis. Real on that axis,
  but months × regimes uncorrected → a lead, not an edge.
- **Regime/years:** three_black_crows stronger in DOWN markets (k3 down +9.0
  vs up +3.5), holds across all periods incl. spent holdout (D+4.8 V+8.3
  H*+3.5), leans on 2023/2022 but survives their removal (+4.0). higher_lows
  even across regimes, holds without 2017/2025. marubozu_red widest sample
  (33k), steady +2.2.
- **Structural:** rs_60 #10 (k3), rs_120 #6 / rs_60 #7 (k5); +0.8..+1.1,
  concentrated in UP markets (down ≈0 / negative). NOT materially stronger
  than the candlestick/trend patterns (matches run 26).
- **LEAN on 1–2 years:** k3 — bearish_engulfing, evening_star,
  three_white_soldiers, three_inside_down, rs_20_strong; k5 adds
  inside_day_run, stage_3_topping. 17/29 positive pooled edge at each k.

## Report sanity checks (all PASS)
1. `not_yet_known` small (k3 662/1009/1072; k5 higher at period ends, as the
   longer window expects). fill_flagged (~17% of liquid stock-days) and
   window_gap are the expected gate exclusions (limit-locked/unresolved fills;
   windows over a trading gap — forbidden by the non-negotiables), not defects.
2. ALL_LIQUID grid: 2018 (−0.2/−0.3) and 2022 (−0.8/−1.2) are the weak years,
   as expected.
3. No pooled edge above 75%: the 156 hit>75% cells (n≥100) are month×regime
   splits (mostly 2021 down-regime months) where the base is equally high —
   market/regime, not signal (edge −5..+23 pts, median +3; no full-year
   signal on n≥200 exceeds +15 pts).

## Batches so far (candidate generation; the holdout stays sealed)
- complements_1 (main): N 3,864 → 151 candidates.
- structural_1 (features/structural-features only): N 3,024 → 236.
- NONE materially stronger than the six holdout ACCEPTs.

## The daily scan + paper trading (on main, unchanged)
- daily_scan v2 trades the 6 holdout ACCEPTs, HOSE first. No forward rows yet
  (the pipeline does not run).

## Blockers / open (open-questions.md)
- Ben: whether any pattern-history lead becomes a NEW registered forward test.
- Ben: review features/structural-features; the pattern-history branch name.
- **Data must flow for the forward test.** After each session: nightly_update
  → fingerprint.build (~20 min) → forward_returns.build → report.scan. The
  structural fingerprint is a separate ~24-min build. Nothing is scheduled.
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
1. Ben reads the pattern-history report; decides on any new forward test.
2. Ben reviews features/structural-features and this branch.
3. Run the daily pipeline so the forward record starts.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); base quality / VCP; sector RS (needs point-in-time labels);
precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3.
`logs/sessions/2026-09-26-session-01.md`. 4. `config/rules/history.yaml`.
5. Only the code the task touches, via `code-map.md`.
