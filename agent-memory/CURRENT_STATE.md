# Current state — 2026-09-23 (end of session 2026-09-23-03, run 11)

Rewritten from scratch. Git figures were checked with `git log`. No DB writes
this run; the DB figures are unchanged from run 10 (re-read then).

## Phase
**Phase 5 features (25 measures), the nightly hardening and dated exchange
labels are on main** (`168c2e9`). **Patterns T1 (approved) and T2 (built this
run) are on `features/patterns`, awaiting Ben's review.** T3–T6 not started.
The fingerprint is not assembled (that is T5).

## Git: ONE working branch (Ben, 2026-09-23)
- `main` = `168c2e9` (GitHub too). Only Ben merges.
- **`features/patterns`** is the only other branch (T1 `538f584`, then T2).

## Measures: 41 (REGISTRY 34 per-symbol + 6 market + 1 sector)
- Features: volume 7, trend/levels 10, index regime 4, breadth 2, sector 2.
- **Patterns T1 (10):**
  - anatomy: body/upper/lower-to-range, range_rel_20d, open_gap;
  - shapes: hammer_shape, inverted_hammer_shape, doji, marubozu_green/red;
  - each shape needs a RAW range ≥ 3 ticks (the dated exchange's tick; the
    largest tick where undated).
- **Patterns T2 (6):** bullish/bearish_engulfing, bullish/bearish_harami,
  piercing_line, dark_cloud_cover.
  - Dated on today; they read yesterday, so a pair across a trading gap is
    blank.
  - Yesterday's RAW body must be ≥ 3 ticks.
  - Cross-day comparisons use a 1e-4 tolerance for adjustment rounding.

**Liquid firing rates** (718,082 stock-days since 2012):

| pattern | rate |
| --- | --- |
| hammer | 5.03% |
| inverted hammer | 3.59% |
| doji | 10.95% |
| marubozu green / red | 5.15% / 5.59% |
| bullish / bearish engulfing | 2.40% / 2.36% |
| bullish / bearish harami | 4.48% / 3.89% |
| piercing line | 0.63% |
| dark cloud cover | 0.84% |

The prior-body floor removes 53–55% of engulfings, 23–26% of haramis and
about 2% of piercing / dark cloud.

## The database: build 5, promoted 'good' (unchanged)
`bar_raw` 2,886,721 rows / 1,709 symbols to 2026-09-21; research window
2,511,070 adjusted bars; `exchange_membership` 232 + 1,390; `symbol_industry`
1 snapshot; migrations 001–009. Last gate: 0 blocking failures (run 9).

## Verified by running it this run
- `uv run pytest` → **240 passed, 0 failed, 0 skipped** (DB reachable).
- `uv run ruff check .` → clean.
- **Mutation proof T2: 36 rules, each removed in turn; 36/36 caught**, with
  bytecode purged.
- **Process fix:** mutation runs now purge `__pycache__`. A same-size mutation
  written in the same second had reused the previous mutation's .pyc (3 false
  survivors). **All earlier proofs were re-run with the purge and are
  genuine:** T1 23/23, exchange labels 15/15, sector 22/22, universe/breadth
  all caught.

## Blockers / open
- X4, G19, G18, G2, G5, G9, G10, G11; backtest B1, B2, B3.
- Broker-friend questions: doji at 11%, engulfings of tiny prior bodies,
  harami colour, which shapes he watches, `near_support` at 40%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews T2 on `features/patterns`.
2. T3: three-candle (morning/evening star with the P4 gap relaxation,
   soldiers/crows, three inside up/down, which reuse the harami rule).
3. T4 consolidations, T5 fingerprint assembly, T6 after G5.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
flag/pause pattern (P7); pattern strength numbers (P9); a liquid-universe
breadth measure; `sector_advance_share_10d`; sector rotation.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 10–11 of
`logs/sessions/2026-09-23-session-03.md` (run 8 = the patterns proposal).
4. `knowledge/patterns.md`. 5. Only the code the task touches, via
`code-map.md`.
