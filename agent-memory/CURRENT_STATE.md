# Current state — 2026-09-23 (end of session 2026-09-23-01, run 1)

Rewritten from scratch. **Git and test figures were checked this run.** The
database was unreachable: this cloud container has no Docker daemon. So every
DB figure below is carried over from 2026-09-22 (session 03, run 4) and marked
*(not re-read)*.

## Phase
**Phase 5: features. Slices 1–3 are built: §4.1 volume (7), §5.1–5.2 per-symbol
trend and levels (10), §5.3 index regime (4). That is 21 measures.**
Next slice: **breadth + the point-in-time universe** (§5.3 remainder). It also
covers part of G11. Sector (§5.4) comes after that.

## Git
Head `0b2ac91` on both `main` and `claude/gracious-shannon-kxn3x1`. Session
03's work is merged. This run changed memory files only.

## The database: build 5, promoted 'good' *(not re-read, as of 2026-09-22)*
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars |
| …of those usable for VOLUME | 2,470,679 (the rest are backfilled spans where volume cannot be adjusted) |
| `excluded_window` | 115 windows |
| `job_run` | 1 row, last status `no_new_data` |
| builds | 1 failed, 2 good, 3 good, 5 good (4 discarded before promotion) |
| index coverage | 5 sessions since 2012 have no VNINDEX row (warn) |

## Verified by running it this run
- `uv run pytest` → **69 passed, 4 skipped**. The skips are the four
  `test_data_integrity.py` DB tests (no database here). With the DB up, the
  suite was 73 passed on 2026-09-22.
- `uv run ruff check .` → clean.
- `scripts/nightly_update.py:248` still hard-codes `restated = False`, so G2 is
  still open (see Blockers).
- The volume measures read `matched_volume` only (checked in
  `features/volume.py`).

## Features built: 21 measures
**§4.1 volume (7), matched volume only:** rvol, sustained_volume,
up_down_volume_ratio, price_volume_agreement, price_volume_divergence,
traded_value, volume_dry_up.
**§5.1–5.2 per-symbol price (10):** ma_20, ma_50, ma_20_slope, ma_50_slope,
price_vs_ma_20, price_vs_ma_50, price_change_10d, price_change_20d,
near_support, near_resistance.
**§5.3 market regime (4), computed once and joined by trade_date:**
index_above_ma_50, index_ma_50_slope, index_change_20d,
index_drawdown_from_high. A symbol date the index does not cover is NaN, never
forward-filled.

Price-only measures stay available on backfilled spans; volume measures do not.
Each measure's declared `needs` drives that split, and both directions are
tested.

The 2026-09-22 run on 40 liquid symbols (118,743 stock-days) found
`near_support` / `near_resistance` firing on ~40% of scored days. That is too
unselective. **Not tuned**: parameters stay fixed until measured (doc §3.5 /
§8.1). This is a question for the broker-friend session. The full per-measure
table (scored / NaN / fires / median / p95) is in the previous version of this
file: `git show 0b2ac91:agent-memory/CURRENT_STATE.md`.

Nothing is materialised; measures compute on demand. **Base rates are NOT
computed yet.** That needs the return generator (B2).

## What exists
Phase 4 is complete: schema and migrations (005), historical load back to 2000,
the data-quality gate, cross-source reconciliation, missed-action repair, the
Class B backfill with seam rescaling, and the nightly job with a heartbeat
(`uv run python scripts/nightly_update.py`, not scheduled).
`backtest/forward_returns.py` holds the G3 primitives.

## Blockers
Closed or handled: **G1**, **G3** (implemented in `backtest/forward_returns.py`),
**G4**, **G12**, **G13**, **G14**, **G15**.

Open:
- **G2: restatement detection is NOT implemented.** The nightly job does
  not close it. `scripts/nightly_update.py:248` hard-codes `restated = False`
  and then logs "restatement detected: False", so it **reports a check it never
  runs**. It never re-derives past factors or diffs them against the stored
  series, so an overnight corporate action leaves the adjusted series stale
  without anything noticing. The misleading log line must go with the fix.
- **G5**: analog search has no overfitting defences.
- **G6**: whole-market paging. Only matters if we return to an API.
- **G8**: settled. Store from 2000, measure from 2012.
- **G9**: ranking function undefined.
- **G10**: Ben's four parameters (holding period, minimum liquidity, risk
  tolerance, daily-pick expectation). Still blocking parameter fixing.
- **G11**: survivorship. Partial coverage, better after the backfill.

Recorded for the **backtest** step, not to be acted on during features
(details in `knowledge/open-questions.md`):
- **B1**: two price-limit definitions. `checks.py` is correct (tick- and
  first-day-aware). `measure_fillability.py` and
  `forward_returns.is_at_ceiling/is_at_floor` use a flat 1.5 VND tolerance, so
  0.133% / 0.342% are slight undercounts. The backtest must reuse `checks.py`'s
  logic.
- **B2**: the return generator is not written. `return_k`, deferred exits
  and the no-gap rule are all still to do.

## Next steps
1. Ben confirms his broker fee (affects net returns only).
2. **Breadth + point-in-time universe slice.** Count only symbols trading on
   each date. Take direction from ADJUSTED close, so ex-dividend days are not
   counted as declines. Needs a running DB.
3. Then sector (§5.4), then patterns (doc §3), then the backtest (starting with
   B1 and B2).

## Parked
- **TypeSafe / Jev** for the later news-veto worker.
- **SSI FastConnect**: paused. Its one remaining advantage is foreign flow,
  which Ben has excluded.
- Ben's broker fee is provisional at 0.15%/side; affects net returns only.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Only the knowledge files the task
needs (for features: `money-flow.md`, `context-vietnam.md`, `patterns.md`).
4. Only the code files the task touches, via `code-map.md`. Never scan the repo.
