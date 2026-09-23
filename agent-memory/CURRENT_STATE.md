# Current state — 2026-09-23 (end of session 2026-09-23-03, run 5)

Rewritten from scratch. DB and git figures were re-checked at the end of this
run (vnstock-db reachable; `git log`).

## Phase
**Phase 5: features. 25 measures.** Slices 1–3 (volume, trend, index regime)
are on main. Slice 4 (breadth + point-in-time universe) is on
`features/breadth-pit-build`. **Slice 5, sector (§5.4), is BUILT on
`features/sector-build` and awaits Ben's review.** Next after review: patterns
(doc §3).

## Git (Ben reviews on the branch and merges; I do not touch main)
- `main` = `4f36815` (GitHub too). Nothing from 2026-09-23 is on main.
- The stack, oldest first, each branch built on the one before:
  1. `features/pit-universe-breadth` `f4f52af`: calendar rebuild, guarded index
     fill, trading-days note. Approved.
  2. `features/breadth-pit-build` `163546e`: the PIT universe and breadth.
  3. `features/sector-build`: sector. It carries a cherry-pick of the proposal
     commit from `features/sector-proposal` (`c02ed23`, memory notes only), so
     that branch is superseded.
- Merge order: 1 → 2 → 3.

## The database: build 5, promoted 'good'
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars; 2,470,679 usable for volume |
| `trading_day` | 18,511 exchange-days; 3,669 distinct dates since 2012 |
| `index_bar` | 11,458 rows (VNINDEX 6,361 cafef + 2 vnstock; HNX-INDEX 5,095) |
| `symbol_industry` | **new (migration 007)**: 1 snapshot, 2026-09-23, 1,722 symbols |
| migrations | 001–007 |

## Built this run (sector, decisions locked by Ben; see decisions.md run 5)
- **Membership** (`data/sectors.py`): ICB level 2 from vnstock VCI, with steel
  (L4 1757) split out of basic resources. That is the ONLY manual exception.
  Each date uses the latest snapshot on or before it. Earlier dates borrow the
  first snapshot and are flagged. Covers all 1,214 active symbols. KBS rough
  cross-check: banks 24/25, securities 32/32, real estate 63/74.
- **The sector frame** (`features/sector.py`) is its OWN frame, keyed by
  (trade_date, sector): 74,580 rows, 20 sectors.
  - It takes the equal-weighted median daily return on the adjusted close,
    over ALL tradeable members.
  - A member counts only if it also traded the session before.
- **Measures**: `sector_change_20d` (in the new `SECTOR_REGISTRY`) and
  `stock_vs_sector_20d` (per-symbol; it also needs the stock's own clean
  window).
- **The join** is explicit in `compute()`: symbol → its sector on that date →
  (trade_date, sector).
- **Thin sector-day guard**: fewer than 5 members, or a drop below 0.80 × the
  trailing median. It blanks 8.7% of sector-days (banks 1.2%, Telecom 59%).
  At the 20-session level small sectors lose much more: IT 50%, retail 44%,
  oil & gas 36% of stock-days.
- **THE HARD GATE**:
  - Every value that read a borrowed label carries `flag__<measure>`, and
    `FeatureSet.flagged` lists each measure.
  - `quarantine_flagged()` blanks flagged values.
  - Sector-conditioned statistics are EXPLORATORY until dated membership
    accrues (B3).
  - Today **100% of historical sector values are flagged**.
- Real data: a stock's 20-session change correlates 0.63 with its sector's
  (VCB 0.72, HPG 0.69, SSI 0.78, VHM 0.45).

## Verified by running it this run
- `uv run pytest` → **127 passed, 0 skipped** (DB reachable, 7 live-DB tests).
- `uv run ruff check .` → clean. The new files are ruff-formatted.
- **Mutation check**: 22 sector rules, each removed in turn; **22/22 tests
  failed** as they should (after two tests were strengthened; see the log).
- `scripts/report_features.py 40` runs with all 25 measures.

## Blockers
Closed or handled: G1, G3, G4, G12, G13, G14, G15.

**Nightly-hardening slice (queued; do not touch during features):**
- G16: the nightly job never writes `index_bar`.
- G17: build 5 fails the factor>1 check.
- The holiday-list check.
- Historical exchange labels.
- The 2026-07-31 index disagreement.
- NEW: **schedule `snapshot_industry.py`** so dated ICB membership accrues.

Backtest items: B1, B2, and **B3 (new): quarantine flagged sector features;
pooled fallbacks on current labels must say so**.

Also open: G2, G5, G9, G10 (the liquidity floor is provisional), G11.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays. A missing day is
only a defect when it is a weekday the market was open.

## Next steps
1. Ben reviews `features/sector-build` and merges the stack in order.
2. Patterns (doc §3), then the backtest (B1, B2, B3; filter by
   `universe.liquid` per date).
3. The nightly-hardening slice, including the ICB snapshot schedule.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side; a
liquid-universe breadth measure; `sector_advance_share_10d`; sector rotation
as a report view.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Run 5 of
`logs/sessions/2026-09-23-session-03.md`. 4. Only the knowledge files the task
needs. 5. Only the code the task touches, via `code-map.md`.
