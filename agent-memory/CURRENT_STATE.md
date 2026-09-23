# Current state — 2026-09-23 (end of session 2026-09-23-03, run 3)

Rewritten from scratch. DB figures were re-read from the live database at the
end of this run (vnstock-db, reachable). Git figures were checked with `git log`.

## Phase
**Phase 5: features. 23 measures.** Slices 1–3 (volume, trend, index regime)
are on main. **Slice 4 (breadth + point-in-time universe, doc §5.3) is BUILT on
`features/breadth-pit-build` and awaits Ben's review.** Sector (§5.4) comes
next.

## Git (review before main)
- `main` = `4f36815`, on GitHub too. Earlier this run I merged
  `features/pit-universe-breadth` into main (`ce864f9`) and pushed it. Ben then
  said not to merge. With his approval, `origin/main` was force-reset to
  `4f36815`. Nothing else ever landed on main.
- `features/pit-universe-breadth` = `f4f52af` (calendar rebuild, guarded index
  fill, PIT/breadth proposal, trading-days note). Pushed and approved by Ben,
  but NOT merged.
- `features/breadth-pit-build` is STACKED on `f4f52af` and holds this run's
  build. Pushed. Merge order: pit-universe-breadth first, then this one.

## The database: build 5, promoted 'good' (no DB writes this run)
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars; 2,470,679 usable for volume |
| `excluded_window` | 115 |
| `trading_day` | 18,511 exchange-days; 3,669 distinct dates since 2012 |
| `index_bar` | VNINDEX 6,361 cafef + 2 vnstock; HNX-INDEX 5,095 cafef |
| `job_run` | 1 row |
| migrations | 001–006 |

## Built this run (slice 4, decisions locked by Ben; see decisions.md)
- `data/universe.py` is **the one definition of "liquid"**. It is recomputed on
  demand from bar_raw.
  - Tradeable on D = traded (volume > 0), not date-shifted, not excluded.
  - Liquid on D = tradeable + traded on ≥ 40 of the last 60 SESSIONS + average
    traded value ≥ the floor.
  - `liquid_symbols()` is now the liquid set on the latest session:
    **280 symbols**. The old 90-calendar-day approximation gave 283.
- `features/breadth.py` builds its own breadth frame.
  - It covers ALL tradeable stocks, uses the adjusted close, and counts only
    stocks that traded the previous session.
  - Measures: `breadth_advance_share` and `breadth_advance_share_10d`.
  - Thin days are blanked: count < 0.80 × the trailing 20-session median, a
    threshold set from the measured distribution. That blanks 54 of 3,689
    sessions.
- `features/base.py`: market measures declare which frame they read, and
  `compute_market` takes a dict of frames.
- Real data:
  - The adjusted close avoided **4,830** fake ex-date declines.
  - Breadth correlates **0.80** with the VNINDEX daily return, with 106 days of
    sharp disagreement.
  - In the 40-symbol report, the daily measure is NaN on 1.4% of stock-days and
    the 10-day one on 7.5%.

## Verified by running it this run
- `uv run pytest` → **104 passed, 0 skipped** (DB reachable; 6 live-DB tests).
- `uv run ruff check .` → clean. The new files are ruff-formatted; the 16
  older files that were already unformatted are untouched.
- **Mutation check**: 17 rules, each removed in turn; **17/17 tests failed** as
  they should. The other 7 new tests check behaviour or guard against a
  regression; none has a single line to remove.
- `scripts/report_features.py 40` runs end to end with both frames.

## Blockers
Closed or handled: G1, G3, G4, G12, G13, G14, G15.

**Nightly-hardening slice (separate; do not touch during features):**
- G16: the nightly job never writes `index_bar`.
- G17: build 5 fails the factor>1 gate check after the seam rescale, so the
  nightly job would refuse to promote a new build.
- The holiday-list check.
- Historical exchange labels.
- The 2026-07-31 index disagreement.

All of these are in `knowledge/open-questions.md`.

Also open:
- G2: restatement detection is not implemented.
- G5 and G9.
- G10: Ben's four parameters. The liquidity floor is still provisional.
- G11: membership is done; CafeF's delisted history is still uneven.
- B1 and B2, for the backtest.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays. A missing day is
only a defect when it is a weekday the market was open
(`knowledge/context-vietnam.md`).

## Next steps
1. **Ben reviews `features/breadth-pit-build`.** Then merge both branches, in order.
2. Sector (§5.4), then patterns (doc §3), then the backtest (B1, B2). The
   backtest must filter by `universe.liquid` on each date.
3. The nightly-hardening slice, when Ben schedules it.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side; a
liquid-universe breadth measure (optional, not built).

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Run 3 of
`logs/sessions/2026-09-23-session-03.md`. 4. Only the knowledge files the task
needs. 5. Only the code the task touches, via `code-map.md`.
