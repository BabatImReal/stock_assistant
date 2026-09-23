# Current state — 2026-09-23 (end of session 2026-09-23-03, run 9)

Rewritten from scratch. DB and git figures were re-checked at the end of this
run (vnstock-db reachable; `git log`).

## Phase
**Phase 5 features (§4–5, 25 measures) and the nightly hardening are on main.**
**Dated exchange labels are BUILT on `features/exchange-labels`, awaiting
Ben's review and merge.** Patterns (§3) + the fingerprint (§3.6) are PROPOSED
(session log run 8, P1–P9 open) and wait until this branch is merged.

## Git: ONE working branch (Ben, 2026-09-23)
- `main` = `5e81cc5` (GitHub too). Only Ben merges.
- **`features/exchange-labels`** is the only other branch. Work stays here: no
  new or stacked branches. It holds the exchange-label slice, the
  one-branch rule, and the patterns proposal note (which rides along).

## The database: build 5, promoted 'good'
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars (build 5) |
| `exchange_membership` | **new**: 232 cafef_transfer spans (116 symbols) + 1,390 kbs_listing (1 KBS span dropped as contradicted: MHL) |
| `index_bar` | VNINDEX 6,360 cafef + 3 vnstock; HNX-INDEX 5,093 cafef + 2 vnstock |
| `symbol_industry` | 1 snapshot (2026-09-23), 1,722 symbols |
| `job_run` | 1 row (the nightly has never appended a session) |
| migrations | 001–009 |

**Gate re-run this run: 0 blocking failures, build 5 stays 'good'**,
reconciliation 87.48%. The price-limit warning is now split: **4,572 on dated
exchange days + 955 FLAGGED** (5,527 in total, as before).

## Exchange labels: what is dated vs flagged
- Dated by evidence: CafeF documented transfers first, then KBS
  `listing_date`.
- Two corroboration rules, because KBS `listing_date` is sometimes the ORIGINAL
  listing date (16 of 95 documented transfers):
  - rule A: drop a KBS span that CafeF's filing contradicts;
  - rule B: never date a vnstock backfill row by KBS.
- **Residual: 6.43% of liquid stock-days since 2012 are undated and FLAGGED**
  (57,738 / 897,588; 8.12% of all research-window stock-days). In liquid
  days:
  - no usable KBS date: 29,773 (294 symbols);
  - G4 Class B backfills: 15,492 (46 symbols);
  - CafeF-filed before the KBS move: 12,473 (52 symbols).
- **G4 gap found**: 52 symbols moved inside their history without G4 seeing
  them (CafeF re-filed their whole history: DPG, ITA, DAG…). Now flagged.
- Flagged days flow through the SAME `quarantine_flagged` gate as sector
  values, into G3 `fillability()`. The gate's price-limit check counts them
  apart.
- X4 unanswered, so `bar_raw.exchange` and the `trading_day` split are left
  as filed.

## Verified by running it this run
- `uv run pytest` → **156 passed, 0 failed, 0 skipped** (DB reachable). The
  exchange known-cases test flipped from its expected failure to pass. The
  Python/SQL agreement test now passes on real, rebuilt data.
- `uv run ruff check .` → clean.
- **Mutation proof: 15 exchange-label rules, each removed in turn; 15/15 tests
  fail as they should** (one survivor on the first pass led to a new test).

## Blockers / open
- **X4** (Ben): re-derive raw exchange labels, or keep raw as filed.
- **G19 (new)**: the price-limit check's factor tolerance (1e-6) is below
  CafeF's rounding jitter, so about 36% of day-pairs are never examined and the
  warning undercounts. Ben's call.
- A residual risk that cannot be detected: a transfer CafeF re-filed AND KBS
  dated at the original listing (about a dozen symbols at the observed rate).
  Tripwire: dated price-limit violations.
- G18 (nightly skips negotiated volume and the symbol master); G2 (restatement
  detection). Both untouched, as asked.
- G5, G9, G10, G11; backtest B1, B2, B3 (B3 now also covers flagged
  exchange-dependent fillability).

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews `features/exchange-labels` (X4, G19) and merges.
2. Then patterns: answer P1–P9 (session log run 8), then T1.
3. Whether to run and schedule the nightly (after G2 and G18).

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side; a
liquid-universe breadth measure; `sector_advance_share_10d`; sector rotation;
14 pre-2012 repeated index rows.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 8–9 of
`logs/sessions/2026-09-23-session-03.md`. 4. Only the knowledge files the task
needs. 5. Only the code the task touches, via `code-map.md`.
