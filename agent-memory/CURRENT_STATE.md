# Current state — 2026-09-24 (end of session 2026-09-23-03, run 15)

Rewritten for run 15 (a proposal run; nothing built). The git figures were
checked with `git ls-remote` this run. The DB figures are from run 14 (build 5
'good'; 2,511,070 bar_adjusted rows since 2012; 1,705 symbols).

## Phase
**On main (`f53b72a`):** features (25), the nightly hardening, dated exchange
labels, the pattern catalogue (T1–T4) and the fingerprint (T5). **Now: the
ANALYSIS ENGINE, PROPOSED on `features/analog-backtest` (run 15), no code;
waiting for Ben's answers to A1–A12** (session log run 15). This covers the
return generator (B2 + B1), exact-combination evidence plus kNN look-alikes
(G5 / T6) with the §8 defences, base rates with a labelled fallback, and one
quarantine gate.

## Git: ONE working branch (Ben, 2026-09-23)
- `main` = `f53b72a` (GitHub too). I fast-forwarded it on 2026-09-24 at Ben's
  choice (he had said "merged" but it was not). Only on Ben's say-so.
- **`features/analog-backtest`** is the only other branch (the proposal
  commit). `features/patterns` is deleted.

## Measures: 51 (REGISTRY 44 per-symbol + 6 market + 1 sector)
- Features (25): volume 7, trend/levels 10, index regime 4, breadth 2,
  sector 2.
- Patterns (26): 5 anatomy numerics, 5 single-candle shapes, 6 two-candle,
  6 three-candle, 4 consolidations.
- 16 patterns carry a traditional `direction` (bullish/bearish), which is
  report-only and never a value.
- Liquid firing rates are in `knowledge/patterns.md` and run 10–13 of the
  session log. For example: doji 10.95%, tight_range 8.71%, breakout 5.60%,
  morning star 0.14%.

## The fingerprint (T5, `patterns/fingerprint.py`)
- It is `compute()` per symbol, stacked: one row per stock-day, EVERY stock
  since 2012, plus `flag__` columns. The schema is generated from the
  registries.
- Stored at `data/processed/fingerprint/<build>_<featureset>/<year>.parquet`
  with `manifest.json` (build, feature set, code hash, per-file sha256).
  `load(*expected(conn))` refuses anything stale.
- `validated()` is the ONLY path to validated values (quarantine by the
  manifest's list). `query()` gives exact combinations (1/0/NaN) with
  occurrences, judged and per-symbol counts.
- **Real build `5_d51a9d818b0a54de`:**
  - 2,511,070 rows (= the DB, per year too), 1,705 symbols, 55 columns, 0
    duplicate keys, 213 MB;
  - 14 min to build.
- The sector measures are 100% flagged: every history date is before the
  first ICB snapshot (2026-09-23). So validated() blanks them all, which is
  correct.
- Rebuild with `uv run python -m vnstock_research.patterns.fingerprint`. Any
  edit under `data/`, `features/` or `patterns/` requires a rebuild.

## Verified by running it this run
- `uv run pytest` → **387 passed, 0 failed, 0 skipped** (DB up). That includes
  the live spot check: the stored rows equal a fresh compute of the top liquid
  stock.
- `uv run ruff check .` → clean. `ruff format --check` flags 20+ older
  files (mostly scripts); they are untouched.
- **Strict mutation proofs** (only the test's own assert counts; no
  exemptions; compile-checked; cache purged):
  - T5 28/28;
  - universe/breadth 17/17, sector 23/23, exchange 15/15, guards 5/5;
  - T1 23/23, T2 36/36, T3 55/55, T4 20/20.
- **Fixed this run:**
  - guard tests now judge the error (`fails_with`);
  - `compute()` crashed on the 125 symbols with no sector label (found by the
    real build; fixed in `sectors.assign`; proven).

## Environment note
On 2026-09-24 the `vnstock-db` container had disappeared while Docker was
running. The named volume `stock_assistant_vnstock-db-data` was intact, and
`docker compose up -d` recreated the container with all data present. If the
DB refuses connections, check `docker ps -a` first.

## Blockers / open
- X4, G19, G18, G2, G5, G9, G10, G11; backtest B1, B2, B3.
- **For Ben (T5):**
  - keep the code hash in the manifest (strict: any edit forces a rebuild)?
  - every stock rather than only liquid ones?
  - the direction labels;
  - the rebuild speed.
- Broker-friend questions:
  - doji at 11% and tight_range at 8.7%;
  - engulfings of tiny prior bodies;
  - the harami colour;
  - the NEW values for T3/T4;
  - the direction labels;
  - `near_support` at 40%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben answers A1–A12 (the engine proposal). No engine code before that.
2. E1: the shared B1 limit function + the return generator + returns storage.
3. E2: the gate + base rates + fallback. E3: the hypothesis registry, exact
   combinations, discover/validate, FDR. E4 (= T6): encode/neighbours.
   The holdout runs once, at the end.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
flag/pause (P7); pattern strength numbers (P9); a liquid-universe breadth
measure; `sector_advance_share_10d`; sector rotation; precomputing
market/sector values once per build (a `ponytail:` note in `build`).

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 14–15 of
`logs/sessions/2026-09-23-session-03.md` (run 8 = the patterns and fingerprint
proposal). 4. `knowledge/patterns.md`. 5. Only the code the task touches, via
`code-map.md`.
