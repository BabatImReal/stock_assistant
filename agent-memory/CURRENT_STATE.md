# Current state — 2026-09-23 (end of session 2026-09-23-03, run 6)

Rewritten from scratch. DB and git figures were re-checked at the end of this
run (vnstock-db reachable; `git log`).

## Phase
**Phase 5: features (§4–5) complete, 25 measures, reviewed by Ben.** This run:
the nightly-hardening / integrity block on `features/nightly-hardening`.
Next: Ben's review and his decision on historical exchange labels (X1–X4),
then patterns (doc §3).

## Git (Ben reviews on the branch and merges; I do not touch main)
- `main` = `4f36815` (GitHub too).
- The stack, oldest first: `features/pit-universe-breadth` `f4f52af` →
  `features/breadth-pit-build` `163546e` → `features/sector-build` `1003b72` →
  **`features/nightly-hardening`** (this run). Merge in that order.

## The database: build 5, promoted 'good', gate re-run clean this run
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars |
| `adjustment_factor` (build 5) | cafef 2,824,492; inferred 14,775; **seam_rescale 27,518 (33 symbols, new tag)**; vnstock 19,816 (13 symbols, factor 1) |
| `index_bar` | 11,458 rows: VNINDEX 6,360 cafef + 3 vnstock; HNX-INDEX 5,093 cafef + 2 vnstock |
| `symbol_industry` | 1 snapshot (2026-09-23), 1,722 symbols |
| `job_run` | 1 row (the nightly has still never appended a session) |
| migrations | 001–008 |

**Gate (run_checks.py, re-run twice this run): 0 blocking failures**, reconciliation
87.48% (bar 85%), build 5 stays 'good'. 20 checks.

## Done this run (details in decisions.md, run 6)
1. **G17 FIXED.** Migration 008 gives seam-rescale factors their own source and
   a reason. The gate exempts ONLY those, and only on backfilled vnstock bars.
   Proof: the live test failed with 15,670 rows before and passes after, and a
   rolled-back injection shows any other factor above 1 still fails.
2. **G16 FIXED.** The nightly writes the session's VN-Index and HNX-Index rows
   (`write_index`). Tested with a daily-file fixture; idempotent.
3. **Holidays DONE.** `config/rules/holidays.yaml` holds 121 verified weekday
   closures for 2012–2026. Two blocking checks. An injected holiday row is
   caught. **Extend it every year.**
4. **Snapshot scheduling DONE.** The nightly takes the ICB snapshot on every run.
   Proven three ways: `main()` in a no-commit test, and the real step run twice
   (1,722 rows, unchanged).
5. **2026-07-31 FIXED.** CafeF stale copies: 07-31 repeated 07-30 for both
   indices, and HNX 2023-05-08 carried 05-09. Repaired from VCI (KBS agrees to
   0.000%). New warn check `index_has_no_repeated_sessions` went from 3 to 0.
6. **Historical exchange labels: PROPOSED, not built** (session log run 6).
   KBS `listing_date` dates each symbol's move to its current exchange, but not
   the exchange before it.

## NOT done, on purpose
- **The full nightly has not been run end to end.** CafeF has 2026-09-22
  ready; a real run appends it to the research DB. That is Ben's call.
- The nightly is not scheduled (cron/launchd).

## Verified by running it this run
- `uv run pytest` → **137 passed, 0 skipped** (DB reachable; 11 live-DB
  integrity tests + 3 live nightly tests).
- `uv run ruff check .` → clean.

## Blockers / open
- **X1–X4 (exchange labels)**: awaiting Ben.
- **G18 (new)**: the nightly does not update negotiated volume or the symbol
  master. Its docstring now says so.
- G2 (restatement detection) is still not implemented. It matters as soon as
  the nightly runs for real.
- G5, G9, G10 (the liquidity floor is provisional), G11; backtest B1, B2, B3.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays. A missing day is
only a defect when it is a weekday the market was open. Listed holidays are
in `config/rules/holidays.yaml`.

## Next steps
1. Ben reviews `features/nightly-hardening`, decides X1–X4, and says whether
   to run and schedule the nightly (note G2 and G18 first).
2. Patterns (doc §3), then the backtest (B1, B2, B3; `universe.liquid` per
   date; `quarantine_flagged`).

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side; a
liquid-universe breadth measure; `sector_advance_share_10d`; sector rotation
as a report view; 14 pre-2012 repeated index rows.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Run 6 of
`logs/sessions/2026-09-23-session-03.md`. 4. Only the knowledge files the task
needs. 5. Only the code the task touches, via `code-map.md`.
