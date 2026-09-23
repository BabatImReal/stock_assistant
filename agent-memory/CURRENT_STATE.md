# Current state — 2026-09-23 (end of session 2026-09-23-03, run 4)

Rewritten from scratch. DB and git figures were re-checked at the end of this
run (vnstock-db reachable; `git log`).

## Phase
**Phase 5: features. 23 measures.** Slices 1–3 (volume, trend, index regime)
are on main. Slice 4 (breadth + point-in-time universe) is built on
`features/breadth-pit-build` and awaits Ben's review. **Slice 5, sector (§5.4),
is PROPOSED on `features/sector-proposal`. It waits on Ben's answers to S1–S6;
no code yet.**

## Git (Ben reviews on the branch and merges; I do not touch main)
- `main` = `4f36815` (GitHub too). Nothing from 2026-09-23 is on main.
- `features/pit-universe-breadth` = `f4f52af`: calendar rebuild, guarded index
  fill, trading-days note. Approved, not merged.
- `features/breadth-pit-build` = `163546e`, stacked on it: the PIT universe +
  breadth build.
- `features/sector-proposal`, stacked on `163546e`: the sector proposal (memory
  only). Merge order: pit-universe-breadth → breadth-pit-build → sector-proposal.

## The database: build 5, promoted 'good' (no DB writes this run)
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars; 2,470,679 usable for volume |
| `excluded_window` | 115 |
| `trading_day` | 18,511 exchange-days; 3,669 distinct dates since 2012 |
| `index_bar` | 11,458 rows: VNINDEX 6,361 cafef + 2 vnstock; HNX-INDEX 5,095 |
| migrations | 001–006 |

## Sector: what this run found (details in `knowledge/data-sources.md`)
- **No sector data anywhere in our data**: not in the DB, not in any CafeF
  file. CafeF's index file holds only VNINDEX and HNX-INDEX.
- **vnstock VCI `symbols_by_industries()`: ICB levels 1–4, free, CURRENT
  SNAPSHOT ONLY** (no dates, no reclassification history).
  - It covers all active symbols and 366 of 495 inactive ones: 99.0% of liquid
    stock-days since 2012.
  - 19 of the 825 ever-liquid symbols are missing, all delisted.
- KBS (a different taxonomy) cross-check: banks 24/25, securities 32/32, real
  estate 69/83. Overall 74.6% at ICB level 2.
- No free history for the HOSE sector indices.
- Proposal (session log, run 4):
  - ICB level 2;
  - a sector frame (median member return, advance share, count) computed once
    per run;
  - per-symbol measures joined on (date, sector): `sector_change_20d`,
    `sector_advance_share_10d`, `stock_vs_sector_20d`;
  - a label-look-ahead flag in the fingerprint for dates before the first
    snapshot.
- Open questions: S1 source, S2 flag vs forward-only, S3 level, S4 all vs
  liquid members, S5 registry, S6 migration 007.

## Verified by running it this run
- `uv run pytest` → **104 passed, 0 skipped** (DB reachable). `uv run ruff check .`
  → clean. No code changed this run.

## Features built: 23 measures
§4.1 volume (7); §5.1–5.2 trend and levels (10); §5.3 index regime (4);
§5.3 breadth (2, on breadth-pit-build). "Liquid" has one definition:
`data/universe.py`.

## Blockers
Closed or handled: G1, G3, G4, G12, G13, G14, G15.

**Nightly-hardening slice (queued; do not touch during features):**
- G16: the nightly job never writes `index_bar`.
- G17: build 5 fails the factor>1 check after the seam rescale.
- The holiday-list check.
- Historical exchange labels.
- The 2026-07-31 index disagreement.

Sector adds a sibling limitation: **ICB labels are current-only**, the same
shape as the exchange-label problem.

Also open: G2 (restatement), G5, G9, G10 (Ben's parameters; the liquidity
floor is still provisional), G11 (membership done; delisted history uneven),
B1/B2 (backtest).

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays. A missing day is
only a defect when it is a weekday the market was open.

## Next steps
1. Ben answers S1–S6. Then build sector on `features/sector-proposal`.
2. Ben reviews and merges the stacked branches in order.
3. Patterns (doc §3), then the backtest (B1, B2, filtering by
   `universe.liquid` on each date).
4. The nightly-hardening slice, which should also schedule the forward ICB
   snapshots if S2 is approved.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
a liquid-universe breadth measure; sector rotation as a report view.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Run 4 of
`logs/sessions/2026-09-23-session-03.md` (the sector proposal).
4. `knowledge/data-sources.md`, the sector section. 5. Only the code the task
touches, via `code-map.md`.
