# Code map (after the 2026-10-06 retirement of the pattern method)

Only the data layer remains. The old engine (patterns, backtest, report, chart tracks,
cross-sectional score) is in git history before commit "Retire the pattern method".

## src/vnstock_research
| File | Purpose |
|---|---|
| `data/cafef.py` | CafeF bulk-file readers |
| `data/db.py` | Postgres/Timescale connection |
| `data/checks.py` | Price-limit and sanity rules, the blocking data checks |
| `data/exchanges.py` | Dated exchange membership (HOSE/HNX/UPCoM) |
| `data/reconcile.py` | Compare CafeF with vnstock |
| `data/sectors.py` | Dated industry snapshot |
| `data/universe.py` | Point-in-time liquidity tiers |
| `features/bars.py` | Adjusted candles, point in time, adjustment build |

## scripts (all data-layer)
`daily_run.py` (load newest day; NOT scheduled), `catch_up_upto.py` (load missed sessions
from CafeF Upto files, detects restatements; dry run by default), `rescale_build.py` (new
adjustment build after restatements), `nightly_update.py` (superseded price append, do not
schedule), `load_history.py` (NEVER run: overwrites restated history), `snapshot_industry.py`,
`run_checks.py`, `repair_missed_actions.py` (exclusion_window now fixed 60 before / 6 after),
`backfill_*.py`, `check_backfill_seams.py`, `verify_date_shifts.py`, `probe_*.py`,
`investigate_*.py`, `fetch_listing_dates.py`, `count_exchange_transfers.py`,
`analyse_missed_actions.py`.

## config/rules
`costs.yaml` (0.15%/side + 0.1% sale tax), `holidays.yaml`, `market_rules.yaml`
(price limits by exchange/date), `universe.yaml` (liquidity tiers).

## other
`migrations/` (9 SQL files, DB schema), `tests/` (data-layer tests), `docker-compose.yml`.
Git-ignored data: `data/raw` (CafeF files), `data/backups` (DB dumps), `data/reports`.
