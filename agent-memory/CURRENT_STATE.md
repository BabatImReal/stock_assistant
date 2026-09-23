# Current state — 2026-09-23 (end of session 2026-09-23-03, run 1)

Rewritten from scratch. **Every DB figure below was re-read from the live
database this run** (vnstock-db, PostgreSQL 16.15, reachable).

## Phase
**Phase 5: features. Slices 1–3 are built: §4.1 volume (7), §5.1–5.2 per-symbol
trend and levels (10), §5.3 index regime (4). That is 21 measures.**
Next slice: **breadth + the point-in-time (PIT) universe.** It is PROPOSED
(session 2026-09-23-03 log, run 1) and **awaiting Ben's approval. No code yet.**
Sector (§5.4) comes after that.

## Git
Work happens on branch `features/pit-universe-breadth`, cut from `main` at
`4f36815`. `main` is untouched. This run's commit is on the branch and pushed.

## The database: build 5, promoted 'good'
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars (build 5) |
| …of those usable for VOLUME | 2,470,679 |
| `excluded_window` | 115 windows |
| `trading_day` | 18,511 exchange-days; 3,669 distinct dates since 2012 (was 3,670 before the phantom fix) |
| `index_bar` | VNINDEX 6,361 cafef + 2 vnstock; HNX-INDEX 5,095 cafef |
| `job_run` | 1 row, `no_new_data` (2026-09-22) |
| builds | 1 failed, 2 good, 3 good, 5 good |
| migrations | 001–006 applied (006 = `index_bar.source`, this run) |

## Done this run (Task 1: the 5 missing VNINDEX sessions)
Diagnostic run on real data. Each date has its own cause:
- **2025-05-02: PHANTOM.** It was in `trading_day` with no `bar_raw` row behind it
  (`verify_date_shifts.py` deleted the bar and never re-derived the calendar). It
  is a public holiday. **Fixed**: `db.rebuild_trading_day()` is now the calendar's
  one definition, and the scripts that write `bar_raw` call it. A new gate
  check `calendar_matches_bar_raw` (fail) and a live-DB test both enforce it.
  The test failed before the fix (7,352 drifted exchange-days) and passes after
  (0). 1,358 symbols had `gap_before` inflated by 1; for 611 it went 1→0.
- **2024-05-17, 2026-07-02: INDEX-GAP.** Normal sessions. **Backfilled** VNINDEX
  from vnstock (`scripts/backfill_index_gaps.py`, `source='vnstock'`). The
  neighbours reconcile to ≤0.03%. Index dates whose regime window touches a gap
  went from 150 to 50.
- **2018-01-23/24: real HOSE halt.** vnstock shows the index at volume 0. **Left
  as is, and explained.** The gate now warns about 2 sessions, both explained.

## Verified by running it this run
- `uv run pytest` → **79 passed, 0 skipped** (DB reachable, all 5 live-DB tests ran).
- `uv run ruff check .` → clean. `ruff format --check` flags 16 files, all of
  which were already unformatted before this run (my new file is formatted).
- The data-quality gate, run read-only on build 5: **1 blocking failure, G17
  (predates this run)**. See Blockers.

## Features built: 21 measures
**§4.1 volume (7), matched volume only:** rvol, sustained_volume,
up_down_volume_ratio, price_volume_agreement, price_volume_divergence,
traded_value, volume_dry_up.
**§5.1–5.2 per-symbol price (10):** ma_20, ma_50, ma_20_slope, ma_50_slope,
price_vs_ma_20, price_vs_ma_50, price_change_10d, price_change_20d,
near_support, near_resistance.
**§5.3 market regime (4), computed once and joined by trade_date:**
index_above_ma_50, index_ma_50_slope, index_change_20d,
index_drawdown_from_high.
Nothing is materialised. **Base rates are NOT computed yet.** They need the
return generator (B2). `near_support`/`near_resistance` fire on ~40% of scored
days (2026-09-22 run). Not tuned; this is for the broker friend.

## Blockers
Closed or handled: G1, G3, G4, G12, G13, G14, G15.

Open:
- **G17 (new): the promoted build 5 fails `factor_never_above_one_in_research_window`**
  with 15,670 factors > 1, all `source='vnstock'` on 21 symbols. They come from the
  seam rescale, which ran after the last gate run. The rescale is by design;
  the check needs a decision from Ben. **Until then, the nightly job would refuse
  to promote any new build.**
- **G16 (new): the nightly job never writes `index_bar`**, even though its
  docstring says it does. It must be fixed before the job is scheduled.
- **G2**: restatement detection is not implemented. `nightly_update.py`
  hard-codes `restated = False` and logs a check it never runs.
- **G5** analog-search overfitting defences; **G9** ranking undefined;
  **G10** Ben's four parameters (block parameter fixing); **G11** survivorship,
  partly met (the PIT universe covers universe membership).
- Index disagreement on **2026-07-31** (VN 0.51%, HNX 1.40% vs vnstock), not
  explained yet. HNX-INDEX is missing 33 sessions (it isn't used). **2025-05-05**:
  CafeF's HNX stock file lost the session. `exchange` in `bar_raw` and
  `symbol_exchange` is the CURRENT exchange, not the one on the date. Details
  in `knowledge/open-questions.md`.
- Backtest-step items **B1** (two price-limit definitions) and **B2** (return
  generator not written).

## Next steps
1. **Ben approves or amends the PIT universe + breadth proposal** (questions Q1–Q5
   in the session log). Then build it on this branch.
2. Ben decides G17. Then fix G16 before scheduling the nightly job.
3. Then sector (§5.4), patterns (doc §3), and the backtest (B1, B2).

## Parked
TypeSafe / Jev (news-veto worker); SSI FastConnect (paused); broker fee
provisional at 0.15%/side.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. The last run of
`logs/sessions/2026-09-23-session-03.md` (the proposal). 4. Only the knowledge
files the task needs. 5. Only the code the task touches, via `code-map.md`.
