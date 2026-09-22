# Current state — 2026-09-22 (end of session 03, run 2)

Rewritten from scratch. Every number below was read from the database, from
`git log`, or from a test run in this run.

## Phase
**Phase 5 — features (doc §4–5). Slice 1 (volume) BUILT. Slice 2 (trend and
context) not started.**

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
- `uv run pytest` → **52 passed** (16 of them the new feature tests).
- `uv run ruff check .` → clean.
- The four contract guards were **proven by removal**: deleting the guard line
  in `features/base.py` fails exactly those four tests and passes the other 12.
- `scripts/report_volume_features.py 40` → 118,743 stock-days scored across 40
  liquid symbols, feature set `1846768b2661b224`.
- Git head `0dfe90c`; working tree clean apart from this file.

## Features slice 1 — doc §4.1, built and run
Seven measures, all on MATCHED volume only: `rvol`, `sustained_volume`,
`up_down_volume_ratio`, `price_volume_agreement`, `price_volume_divergence`,
`traded_value`, `volume_dry_up`. Switched on/off in
`config/rules/features.yaml`; the enabled set and resolved parameters are
recorded as a `FeatureSet` fingerprint.

Observed on 40 liquid symbols since 2012:

| measure | scored | NaN | fires | median | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| rvol | 104,779 | 11.8% | — | 0.887 | 2.250 |
| sustained_volume | 102,839 | 13.4% | — | 1.000 | 4.000 |
| up_down_volume_ratio | 105,065 | 11.5% | — | 1.127 | 3.098 |
| price_volume_agreement | 105,065 | 11.5% | 17.87% | — | — |
| price_volume_divergence | 105,065 | 11.5% | 7.87% | — | — |
| traded_value (k VND) | 111,346 | 6.2% | — | 75.0M | 632.8M |
| volume_dry_up | 103,933 | 12.5% | 10.10% | — | — |

Nothing is materialised: measures compute on demand until the measure set is
stable. **Base rates are NOT computed** — that needs the return generator (B2).

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
2. **Slice 2: trend and context measures** (doc §5.1–5.4) — moving averages and
   slopes, support and resistance, market regime from the index, sector.
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
