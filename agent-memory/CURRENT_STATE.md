# Current state — 2026-09-23 (end of session 2026-09-23-03, run 13)

Rewritten from scratch. Git figures were checked with `git log`. No DB writes
this run; the DB figures are unchanged (last re-read in run 10).

## Phase
**Phase 5 features (25 measures), the nightly hardening and dated exchange
labels are on main** (`168c2e9`). **The pattern catalogue is complete on
`features/patterns`:** T1–T3 approved, and T4 (consolidations) built this run,
awaiting Ben's review. Next: T5, fingerprint assembly. T6 comes after G5.

## Git: ONE working branch (Ben, 2026-09-23)
- `main` = `168c2e9` (GitHub too). Only Ben merges.
- **`features/patterns`** is the only other branch (T1 `538f584`, T2
  `449f8c8`, T3 `4c0392d`, then T4).

## Measures: 51 (REGISTRY 44 per-symbol + 6 market + 1 sector)
- Features (25): volume 7, trend/levels 10, index regime 4, breadth 2,
  sector 2.
- Patterns (26):
  - T1: 5 anatomy numerics + 5 single-candle shapes;
  - T2: 6 two-candle patterns;
  - T3: 6 three-candle patterns;
  - T4: tight_range, inside_day_run, higher_lows, breakout.
- Every pattern is dated on its last candle, reads nothing after it, is
  blank across a gap or excluded row, and has a tick floor wherever tick noise
  could fire it.

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
| tight_range | 8.71% |
| inside_day_run | 2.67% |
| higher_lows | 1.26% |
| breakout | 5.60% (64.6% of them with rvol ≥ 1.5) |

## Verified by running it this run
- `uv run pytest` → **362 passed, 0 failed, 0 skipped** (DB reachable).
- `uv run ruff check .` → clean.
- **Mutation proofs, re-run STRICTLY** (only a genuine test failure counts; a
  crashed or non-compiling mutant never counts; cache purged; test IDs
  audited). Every rule in every tranche is genuinely caught:
  - universe/breadth 17/17, sector 22/22, exchange labels 15/15;
  - T1 23/23, T2 36/36, T3 55/55, T4 20/20.
- **Found this run:** the earlier scripts counted ANY failure as caught. 10
  rules had been "certified" on crashed mutants: 4 since their original runs,
  6 from my run-11 helper. All 10 were re-proved with valid mutants and all are
  genuine. Nothing was wrongly certified in the end, but it had been possible.

## Blockers / open
- X4, G19, G18, G2, G5, G9, G10, G11; backtest B1, B2, B3.
- Broker-friend questions:
  - doji at 11% and tight_range at 8.7%;
  - engulfings of tiny prior bodies;
  - the harami colour;
  - the NEW values for T3/T4;
  - which shapes he watches;
  - `near_support` at 40%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews T4 on `features/patterns`.
2. T5: fingerprint assembly (`build` / `load` / `validated` / `query`,
   Parquet + manifest, P8), with market/sector values computed once per build.
3. T6 (encode/neighbours, sequence, weekly) after G5.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
flag/pause (P7); pattern strength numbers (P9); a liquid-universe breadth
measure; `sector_advance_share_10d`; sector rotation.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 10–13 of
`logs/sessions/2026-09-23-session-03.md` (run 8 = the patterns and fingerprint
proposal). 4. `knowledge/patterns.md`. 5. Only the code the task touches, via
`code-map.md`.
