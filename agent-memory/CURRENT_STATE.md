# Current state — 2026-09-24 (end of session 2026-09-23-03, run 17)

Rewritten from scratch. The figures were checked this run against the DB
(build 5 'good'), the rebuilt returns and fingerprint, and `git`.

## Phase
**On main (`f53b72a`):** features (25), the nightly hardening, dated exchange
labels, the pattern catalogue (T1–T4) and the fingerprint (T5).
**The analysis engine, on `features/analog-backtest`:**
- the design is approved;
- E1 (the limit function, the forward returns, storage) is approved;
- **E2 (G20 detector + the gate + base rates + fallback) is built and awaiting
  Ben's review.**

Next: E3.

## Git: ONE working branch
- `main` = `f53b72a`. Only on Ben's say-so.
- **`features/analog-backtest`**: the proposal `d6512e3`, E1 `b4b601c`, then
  E2.

## What exists (the engine)
- **Limits (B1):** `checks.limit_prices` / `limits_sql`: one tick-rounded
  ceiling/floor, Python == gate SQL.
- **Returns (E1):** `forward_returns.outcomes`, stored at
  `returns/5_de0d00cf56ae1553`.
  - k = 3, 5 on adjusted prices; net PROVISIONAL.
  - Also stored: MFE/MAE and known_on (actual resolution).
  - 10 reason codes, including `factor_break`.
  - Liquid k=3: 874,308 resolved (97.41%); 17.12% of those are flagged,
    11.80% on UPCoM.
- **G20 (E2 part 0):** `checks.factor_triage`. `bars.load` marks
  `factor_break`, and every feature/return window treats it as a gap.
  - Triage of the 1,818: 1,305 resumptions, 2 new-exchange first days,
    **511 genuine defects on 313 symbols**.
  - 82 liquid k=3 outcomes lost (0.009%).
  - The factors themselves are NOT repaired.
- **The gate (E2):** `backtest.evidence.validated(fp, returns, universe,
  before)`: the ONE join. It:
  - refuses two builds;
  - blanks flagged features;
  - blanks outcomes that are fill-flagged / not liquid / not known before T,
    each with a reason;
  - drops rows from T on;
  - produces a `Validated`, which only it can make.
- **The numbers (E2):** `evidence()`:
  - hit = net > 0 vs the base rate on the identical population (judged days,
    same level/period/horizon/gate);
  - edge, gross, expectancy, avg win/loss, MFE/MAE;
  - n raw + de-clustered, and drops per level;
  - the fallback stock → PIT liquidity tier → market (>= 30 de-clustered);
  - sector beside, EXPLORATORY; the PROVISIONAL stamp.
- **Tiers:** `universe.tiers`: PIT terciles of the day's liquid set.

## Verified by running it this run
- `uv run pytest` → **456 passed, 0 failed, 0 skipped** (DB up). `ruff check
  .` → clean.
- **Strict proofs** (no exemptions; compile-checked; cache purged):
  - E2 46/46, E1 50/50, fingerprint 27/27;
  - universe/breadth 17/17, sector 23/23, exchange 15/15, guards 5/5;
  - T1 23/23, T2 36/36, T3 55/55, T4 20/20.
- **`shm_size: 1gb`:** the query that failed on shared memory now runs in 8 s.
- **E2 sanity on the DISCOVER years only** (before 2020-01-01): 1,059,379 gated
  rows; the fallback works (VNM hammer + support → tier). These are one-off
  in-sample checks, NOT evidence.

## Blockers / open
- **G20 repair:** re-derive the 511 defect factors, or a new build, plus a gate
  check. Needs Ben.
- X4, G19, G18, G2, G9, G10, G11.
- To confirm:
  - the limit rounding rules;
  - UPCoM's average-price reference;
  - the broker fee (NET is provisional).
- Broker-friend questions are in open-questions.md.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews E2 and merges.
2. **E3:** write the holdout rule down BEFORE any discover run
   (pre-registered). Then:
   - the hypothesis registry (21 triggers × up to 2 of ~8 conditions, N
     logged);
   - discover (2012–2019) / validate (2020–2023) with embargo;
   - BH-FDR q = 0.10;
   - the validate thresholds (same sign, minimum edge, net > 0);
   - the discover → validate SURVIVAL count;
   - year/regime reporting.
3. **E4:** kNN (T6). The holdout runs once, with Ben.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 16–17 of
`logs/sessions/2026-09-23-session-03.md` (run 15 = the engine proposal).
4. `knowledge/validation.md`. 5. Only the code the task touches, via
`code-map.md`.
