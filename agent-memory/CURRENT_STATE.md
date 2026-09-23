# Current state — 2026-09-23 (end of session 2026-09-23-03, run 12)

Rewritten from scratch. Git figures were checked with `git log`. No DB writes
this run; the DB figures are unchanged (last re-read in run 10).

## Phase
**Phase 5 features (25 measures), the nightly hardening and dated exchange
labels are on main** (`168c2e9`). **Patterns T1 and T2 (approved) and T3
(built this run) are on `features/patterns`, awaiting Ben's review.** T4–T6
not started. The fingerprint is not assembled (that is T5).

## Git: ONE working branch (Ben, 2026-09-23)
- `main` = `168c2e9` (GitHub too). Only Ben merges.
- **`features/patterns`** is the only other branch (T1 `538f584`, T2
  `449f8c8`, then T3).

## Measures: 47 (REGISTRY 40 per-symbol + 6 market + 1 sector)
- Features: volume 7, trend/levels 10, index regime 4, breadth 2, sector 2.
- **Patterns T1 (10):** 5 anatomy numerics + hammer / inverted hammer / doji /
  marubozu green and red. Raw range ≥ 3 ticks.
- **Patterns T2 (6):** engulfing ×2, harami ×2, piercing line, dark cloud
  cover. Yesterday's raw body ≥ 3 ticks; a 1e-4 cross-day tolerance.
- **Patterns T3 (6):** morning/evening star (P4: the star opens beyond d1's
  close), three white soldiers / black crows, three inside up/down (the harami
  reused). The large candles need a raw body ≥ 3 ticks; the star does not.

Every pattern is dated on its last candle and reads nothing after it. A
multi-candle window with a gap or excluded row is blank.

**Liquid firing rates** (718,082 stock-days since 2012):

| pattern | rate |
| --- | --- |
| hammer | 5.03% |
| inverted hammer | 3.59% |
| doji | 10.95% |
| marubozu green / red | 5.15% / 5.59% |
| engulfing bull / bear | 2.40% / 2.36% |
| harami bull / bear | 4.48% / 3.89% |
| piercing line | 0.63% |
| dark cloud cover | 0.84% |
| morning / evening star | 0.14% / 0.22% |
| soldiers / crows | 0.21% / 0.43% |
| three inside up / down | 0.61% / 0.45% |

The three-candle patterns are rare: about 3 morning stars per stock in 14
years. Their statistics will rely on the sector/market fallback, which the
backtest must report.

## The database: build 5, promoted 'good' (unchanged)
`bar_raw` 2,886,721 rows / 1,709 symbols to 2026-09-21; research window
2,511,070 adjusted bars; migrations 001–009. Last gate: 0 blocking (run 9).

## Verified by running it this run
- `uv run pytest` → **326 passed, 0 failed, 0 skipped** (DB reachable).
- `uv run ruff check .` → clean.
- **Mutation proof T3: 55 rules, each removed in turn; 55/55 caught**, with the
  bytecode cache purged. T2's 36/36 was re-run after the shared floor-helper
  refactor: still 36/36.

## Blockers / open
- X4, G19, G18, G2, G5, G9, G10, G11; backtest B1, B2, B3.
- Broker-friend questions: doji at 11%; engulfings of tiny prior bodies; the
  harami colour; the new T3 values (star 30%, wick 25%); which shapes he
  watches; `near_support` at 40%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews T3 on `features/patterns`.
2. T4: consolidations (tight range, inside-day run, higher lows, breakout
   price-only per P6; flag/pause deferred per P7).
3. T5 fingerprint assembly; T6 after G5.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
flag/pause (P7); pattern strength numbers (P9); a liquid-universe breadth
measure; `sector_advance_share_10d`; sector rotation.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 10–12 of
`logs/sessions/2026-09-23-session-03.md` (run 8 = the patterns proposal).
4. `knowledge/patterns.md`. 5. Only the code the task touches, via
`code-map.md`.
