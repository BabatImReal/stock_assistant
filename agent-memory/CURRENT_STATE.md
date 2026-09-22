# Current state — 2026-09-22 (end of session 02, run 9)

Every number below was read from the database or from `git log` in this run.

## Phase
**Phase 4 — data foundation COMPLETE. All four steps built and run.**
Next is features (doc §4–5). Nothing blocks it except Ben's broker fee, which
only affects the net-return figure.

## The database — build 5, promoted 'good'
| | |
| --- | --- |
| `bar_raw` | **2,886,721** rows, **1,709** symbols, **2000-07-28 → 2026-09-21** |
| research window (2012+) | **2,511,070** adjusted bars |
| `negotiated_volume` | 4,228,174 rows (absence = unknown, never zero) |
| `index_bar` | 11,456 | `trading_day` | 18,505 exchange-days |
| `excluded_window` | 115 windows (~18,726 calendar days) |
| factors in build 5 | cafef 2,824,492 · vnstock 47,334 · **inferred 14,775** |
| symbols with backfill | 46 |
| builds | 1 failed, 2 good, 3 good, 5 good (4 was discarded before promotion) |

## What works, verified by running it
- `uv run pytest` → **36 passed** (unit + live-database + forward returns).
- `scripts/nightly_update.py` → ran once; correctly reported `no_new_data` and
  wrote a heartbeat row. **One command: `uv run python scripts/nightly_update.py`**
- `uv run ruff check .` → clean. Pre-commit: 7 hooks.
- `scripts/load_history.py` → loads CafeF back to 2000.
- `scripts/run_checks.py` → 14 checks + reconciliation; promotes a build only
  if nothing blocking failed. It **rejected build 1** over three real defects.
- `scripts/repair_missed_actions.py`, `backfill_transfers.py`,
  `verify_date_shifts.py`, `investigate_warnings.py`,
  `analyse_missed_actions.py`, `count_exchange_transfers.py`,
  `probe_free_sources.py`, `probe_matched_vs_deal.py` — all run.

## Data quality: no blocking failures. Live warnings:
- **5,527** symbol-days since 2012 move beyond the price limit with no factor
  change (was 8,213 before the rule work; see `decisions.md` run 8).
- 1,131 symbols missing > 20 sessions inside their listed range (108 liquid).
  Mostly days the stock genuinely did not trade.
- 4,028 exchange-days with < 20 symbols (only 6 of them since 2012).
- 120 factors > 1 on one symbol (GGG), all pre-2012.
- 68 symbols whose latest factor ≠ 1 — all have stopped trading; none liquid.
- 84 bars moved off a weekend date, each verified against vnstock.

## Reconciliation, CafeF vs vnstock (10 symbols, 2012 → now)
Close ~87%, volume ~99%. 2020 onward is 99.7–100% every year. The shortfall is
**three symbols with a constant-ratio adjustment-policy difference** (VNM, MBB,
PNJ), all resolving January 2022 — recorded as a known policy difference,
CafeF canonical, no action.

## Blockers G1–G15
Closed or handled: **G1** (volume adjusted by the inverse factor; traded-value
invariant proves it), **G4** (116 Class A stitched, 251 Class B counted, 46 of
47 liquid ones backfilled), **G12** (CafeF volume is matched-only), **G13**
(foreign flow excluded until a live source exists), **G14** (calendar from stock
rows), **G15** (CafeF canonical).
Open: **G2** (restatement detection — becomes real with the nightly job),
**G3** (forward-return definition — proposal awaiting Ben), **G5** (analog
search has no overfitting defences), **G6** (whole-market paging — only matters
if we ever go back to an API), **G8** (2010 vs 2012 — settled: store from 2000,
measure from 2012), **G9** (ranking function undefined), **G10** (Ben's four
parameters), **G11** (survivorship — partial coverage, now better after the
backfill).

## G3 — closed and implemented
signal at close of t → entry at open of t+1 → `return_k = close(t+1+k) /
open(t+1) − 1`, k ≥ the earliest-sell offset for the ERA of the entry date.
Three settlement eras, all verified: T+3; T+2 settling 16:30 from 2016-01-04
(so earliest sell is **still T+3**); T+2 settling before 13:00 from 2022-08-25.
Entries rejected when t+1 opens at the ceiling (**0.133%** of liquid bars);
exits deferred past a floor close (**0.342%**, cap 5 sessions, only 3 runs
market-wide exceed it). Gross and net both stored; round trip **0.40%** with a
**provisional** 0.15%/side broker fee.

## Backfill seams
35 of 46 needed a level rescale; **44 of 46 now within 2%**. TDP and VHM meet
across 73 and 308 days, where the ratio is real price movement rather than a
mismatch — left alone and written to `excluded_window`.

## Next steps
1. Ben confirms his broker fee (affects net returns only).
2. **Features** (doc §4–5): volume measures on matched volume, trend, support
   and resistance, market regime.
3. Then pattern rules (doc §3), then the backtest.

## Parked
- **TypeSafe / Jev** for the later news-veto worker.
- **SSI FastConnect** — paused. Its one remaining advantage over the free
  sources is foreign flow, which Ben has excluded anyway.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Only the knowledge files the task
needs — for data work, `data-model.md`, `data-sources.md`, and the blockers in
`open-questions.md`. 4. Only the code files the task touches, via `code-map.md`.
Never scan the repo.
