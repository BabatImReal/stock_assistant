# Current state — 2026-09-23 (end of session 2026-09-23-03, run 10)

Rewritten from scratch. DB and git figures were re-checked at the end of this
run (vnstock-db reachable; `git log`). No DB writes this run.

## Phase
**Phase 5 features (25 measures), the nightly hardening and dated exchange
labels are on main** (PR #2 merged, fast-forward to `168c2e9`).
**Patterns tranche 1 (doc §3.1) is BUILT on `features/patterns`, awaiting
Ben's review.** Tranches T2–T6 not started. The fingerprint is not assembled
(that is T5).

## Git: ONE working branch (Ben, 2026-09-23)
- `main` = `168c2e9` (GitHub too). Only Ben merges.
- **`features/patterns`** is the only other branch; `features/exchange-labels`
  was deleted after PR #2 merged.

## Measures: 35 (REGISTRY 28 per-symbol + 6 market + 1 sector)
Features: volume 7, trend/levels 10, index regime 4, breadth 2, sector 2.
**New, patterns T1 (10):**
- anatomy: body_to_range, upper_wick_to_range, lower_wick_to_range,
  range_rel_20d, open_gap;
- shapes: hammer_shape, inverted_hammer_shape, doji, marubozu_green,
  marubozu_red.

Each shape has a floor: the RAW range must be ≥ 3 ticks, using the DATED
exchange's tick, or the largest tick of any exchange where undated
(`checks.floor_tick`).

**Liquid firing rates** (718,082 stock-days since 2012, 280 liquid names):

| shape | rate | without floor |
| --- | --- | --- |
| hammer | 5.03% | 10.49% |
| inverted hammer | 3.59% | 8.41% |
| doji | 10.95% | 19.07% |
| marubozu green | 5.15% | 7.40% |
| marubozu red | 5.59% | 7.67% |

27.1% of days have at least one shape. On the illiquid sample the floor
removes 83–91% of hammer, inverted and doji hits. Doji at 11% is a
broker-friend question; it is not tuned.

## The database: build 5, promoted 'good' (unchanged this run)
| | |
| --- | --- |
| `bar_raw` | 2,886,721 rows, 1,709 symbols, 2000-07-28 → 2026-09-21 |
| research window (2012+) | 2,511,070 adjusted bars |
| `exchange_membership` | 232 cafef_transfer + 1,390 kbs_listing |
| `symbol_industry` | 1 snapshot (2026-09-23), 1,722 symbols |
| migrations | 001–009 |
Last gate run (run 9): 0 blocking failures. Exchange residual: 6.43% of liquid
stock-days undated and flagged.

## Verified by running it this run
- `uv run pytest` → **186 passed, 0 failed, 0 skipped** (DB reachable).
- `uv run ruff check .` → clean.
- **Mutation proof: 23 tranche-1 rules, each removed in turn; 23/23 tests
  fail as they should.**

## Found this run
- The floor as first built (largest tick everywhere) overshot HOSE's real tick
  2–10x on 64% of dated liquid HOSE days, dropping about 1 real candle in 10 on
  HOSE only. It was measured and changed to the dated exchange's tick.
- With the textbook values, "body in the top third" already implies "lower
  wick ≥ 2× body". The clause is kept (it binds if a threshold changes) and
  tested at 3×.

## Blockers / open
- X4 (re-derive raw exchange labels, or keep as filed); G19 (price-limit factor
  tolerance); G18; G2; G5, G9, G10, G11; B1, B2, B3.
- Broker-friend questions: the doji threshold, which shapes he watches,
  `near_support` firing on 40%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews `features/patterns` (T1).
2. T2: two-candle patterns (engulfing ×2, harami ×2, piercing, dark cloud),
   with "long body" = ≥ the 20-day average body (P3).
3. Then T3 (three-candle, P4 gap relaxation), T4 (consolidations), T5
   (fingerprint assembly), T6 (after G5).

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
flag/pause pattern (P7); pattern strength numbers (P9); a liquid-universe
breadth measure; `sector_advance_share_10d`; sector rotation.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Run 10 of
`logs/sessions/2026-09-23-session-03.md` (and run 8, the patterns proposal).
4. `knowledge/patterns.md`. 5. Only the code the task touches, via
`code-map.md`.
