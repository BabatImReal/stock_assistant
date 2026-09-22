# Current state — 2026-09-22 (end of session 03, run 4)

Rewritten from scratch. Every number below was read from the database, from
`git log`, or from a test run in this run.

## Phase
**Phase 5 — features. Slices 1–3 BUILT: §4.1 volume (7), §5.1–5.2 per-symbol
trend and levels (10), §5.3 index regime (4) — 21 measures.**
Next slice: **breadth + the point-in-time universe** (§5.3 remainder), which
also discharges part of G11. Sector (§5.4) after that.

## The database — build 5, promoted 'good'
| | |
| --- | --- |
| `bar_raw` | **2,886,721** rows, **1,709** symbols, **2000-07-28 → 2026-09-21** |
| research window (2012+) | **2,511,070** adjusted bars |
| …of those usable for VOLUME | **2,470,679** (the rest are backfilled spans where volume cannot be adjusted) |
| `excluded_window` | 115 windows |
| `job_run` | 1 row, last status `no_new_data` |
| builds | 1 failed, 2 good, 3 good, 5 good (4 discarded before promotion) |

## Verified by running it this run
- `uv run pytest` → **73 passed** (36 of them feature tests).
- `uv run ruff check .` → clean.
- Guards **proven by removal** this run: restoring the old `near_support`
  lookback fails the new pivot-margin test; deleting the `_window_ok` guard fails
  exactly the four contract tests; neutering `boolean_from` fails the
  NaN-preservation test; removing the pivot confirmation filter fails the
  look-ahead test. One of my own tests was found passing for the wrong reason
  and was rewritten until it failed without the guard.
- `scripts/report_features.py 40` → 118,743 stock-days scored across 40
  liquid symbols, 21 measures including index regime.
- New data-quality check `index_covers_every_trading_session` → **5 sessions
  since 2012 have no VNINDEX row** (warn).
- Git head `0dfe90c`; working tree clean apart from this file.

## Features built — 21 measures
**§4.1 volume (7), matched volume only:** rvol, sustained_volume,
up_down_volume_ratio, price_volume_agreement, price_volume_divergence,
traded_value, volume_dry_up.
**§5.1–5.2 per-symbol price (10):** ma_20, ma_50, ma_20_slope, ma_50_slope,
price_vs_ma_20, price_vs_ma_50, price_change_10d, price_change_20d,
near_support, near_resistance.
**§5.3 market regime (4), computed once and joined by trade_date:**
index_above_ma_50 (fires 62.4%), index_ma_50_slope (median 0.004),
index_change_20d (median 0.012), index_drawdown_from_high (median −0.031).
A symbol date the index does not cover is NaN, never forward-filled; an index
gap is treated as a data defect and reported.

Price-only measures remain available on backfilled spans; volume measures do
not. That split is driven by each measure's declared `needs`, and both
directions are tested.

Observed on 40 liquid symbols since 2012 (118,743 stock-days):

| measure | scored | NaN | fires | median | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| rvol | 105,065 | 11.5% | — | 0.887 | 2.250 |
| sustained_volume | 103,379 | 12.9% | — | 1.000 | 4.000 |
| up_down_volume_ratio | 105,065 | 11.5% | — | 1.127 | 3.098 |
| price_volume_agreement | 105,352 | 11.3% | 17.86% | — | — |
| price_volume_divergence | 105,352 | 11.3% | 7.88% | — | — |
| traded_value (k VND) | 111,346 | 6.2% | — | 75.0M | 632.8M |
| volume_dry_up | 104,495 | 12.0% | 10.10% | — | — |
| ma_20 / ma_50 | 110,806 / 102,728 | 6.7% / 13.5% | — | 14.97 / 14.94 | 71.8 / 71.9 |
| ma_20_slope / ma_50_slope | 109,357 / 100,214 | 7.9% / 15.6% | — | 0.002 / 0.003 | 0.045 / 0.061 |
| price_vs_ma_20 / _50 | 110,806 / 102,728 | 6.7% / 13.5% | — | 0.003 / 0.007 | 0.102 / 0.177 |
| price_change_10d / 20d | 113,561 / 110,513 | 4.4% / 6.9% | — | 0.003 / 0.006 | 0.133 / 0.202 |
| **near_support** | 99,718 | 16.0% | **40.29%** | — | — |
| **near_resistance** | 99,718 | 16.0% | **40.90%** | — | — |

**Flagged, not fixed:** the two level measures fire on ~40% of scored days,
which is not selective enough to be useful as written. The parameters are the
provisional textbook values (60-day lookback, 2% tolerance, 2 touches). Doc
§3.5 says fix parameters first and measure before adjusting, so they have NOT
been tuned — this is a question for the broker-friend session.

Nothing is materialised; measures compute on demand. **Base rates are still NOT
computed** — that needs the return generator (B2).

## What exists
Phase 4 is complete: schema and migrations (005), historical load back to 2000,
the data-quality gate, cross-source reconciliation, missed-action repair, the
Class B backfill with seam rescaling, and the nightly job with a heartbeat
(`uv run python scripts/nightly_update.py`, not scheduled).
`backtest/forward_returns.py` holds the G3 primitives.

## Blockers
Closed or handled: **G1**, **G3**, **G4**, **G12**, **G13**, **G14**, **G15**.

Open, and one of them is worse than it looked:
- **G2 — restatement detection is NOT implemented.** Checked in the source this
  run: `scripts/nightly_update.py:248` hard-codes `restated = False` and line
  250 logs "restatement detected: False". The job **reports a check it never
  runs**. It computes factors for the new session only, never re-derives past
  factors from the fresh files, never diffs them against the stored series. A
  corporate action landing overnight leaves the adjusted series stale and
  nothing notices. The misleading log line must go with the fix.
- **G5** analog search has no overfitting defences.
- **G6** whole-market paging — only matters if we ever return to an API.
- **G8** settled: store from 2000, measure from 2012.
- **G9** ranking function undefined.
- **G10** Ben's four parameters (holding period, minimum liquidity, risk
  tolerance, daily-pick expectation) — still blocking parameter fixing.
- **G11** survivorship — partial coverage, better after the backfill.

Recorded for the **backtest** step, not to be acted on during features:
- **B1** two different price-limit definitions exist. `checks.py` is correct
  (limit in force + one tick, first-day bands); `measure_fillability.py` and
  `forward_returns.is_at_ceiling/is_at_floor` use a flat 1.5 VND tolerance with
  no tick rounding, so ceiling/floor bars on higher-priced stocks are
  **under-detected** and the 0.133% / 0.342% rates are slight undercounts.
- **B2** the return generator is not written. `forward_returns.py` is
  primitives only; computing `return_k`, deferring exits on real bars, and
  enforcing the no-gap rule all remain.

## Next steps
1. Ben confirms his broker fee (affects net returns only).
2. **Breadth + point-in-time universe slice** — counts only symbols trading on
   each date, direction on ADJUSTED close so ex-dividend days are not fake
   declines. Discharges part of G11 and implements the PIT liquid-universe
   decision.
3. Then sector (§5.4), then patterns (doc §3), then the backtest (B1, B2).
3. Then patterns (doc §3), then the backtest (which starts by clearing B1
   and B2).

## Parked
- **TypeSafe / Jev** for the later news-veto worker.
- **SSI FastConnect** — paused; its one remaining advantage is foreign flow,
  which Ben has excluded.
- Ben's broker fee is provisional at 0.15%/side; affects net returns only.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Only the knowledge files the task
needs — for features, `money-flow.md`, `context-vietnam.md`, `patterns.md`.
4. Only the code files the task touches, via `code-map.md`. Never scan the repo.
