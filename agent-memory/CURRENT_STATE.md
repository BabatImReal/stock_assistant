# Current state — 2026-09-24 (end of session 2026-09-23-03, run 19)

Rewritten from scratch. Checked this run: `git log`, the hypothesis and
neighbour logs, the reports under research/, and pytest. The DB and stored
tables are unchanged since run 17 (build 5 'good').

## Phase
**On main (`f53b72a`):** features (25), the nightly hardening, dated exchange
labels, the pattern catalogue (T1–T4) and the fingerprint (T5).
**The analysis engine, on `features/analog-backtest`:**
- the design, E1, E2 and E3 are approved (E3 verified by Ben against the log
  and the git order);
- **E4 (the look-alike search + the E3 display layer) is built, awaiting Ben's
  review.**

Next: the holdout, once, with Ben.

## Git: ONE working branch
- `main` = `f53b72a`. Only on Ben's say-so.
- **`features/analog-backtest`**, in order:
  1. the proposal `d6512e3`;
  2. E1 `b4b601c`;
  3. E2 `067f085`;
  4. E3 registration `b3ca180`, then code `c132439`, then runs `0f9c763`;
  5. **E4 registration `a828418` (alone), then code `e4671e5`**, then the
     sanity runs and memory.

## The research result so far (holdout NOT run)
- **E3:** N = 1,554 → 1,454 testable → **82 passed discovery** → **16 held on
  validate**.
  - Displayed as **6 families**: marubozu_red (7), breakout + volume_dry (3),
    three_black_crows + rvol (3), and one each for higher_lows,
    inside_day_run and tight_range.
  - Led by "bearish" labels behaving bullishly.
- **8 negative-edge discover survivors:** EXPLORATORY "avoid" candidates only.
  5 kept a negative sign on validate. No avoid rule is registered.
- The holdout rule is pre-registered (keep sign + net > 0, ≥ 30 de-clustered,
  on 2024 → freeze).

## E4: the look-alike search (ILLUSTRATIVE, never a claim)
- `config/rules/protocol.yaml` `neighbours`: its own frozen block (hash in
  `research/neighbours_log.csv`).
  - The exact fired set of the 21 triggers (every trigger known).
  - 13 numerics as the same-day percentile among liquid stocks; 4 booleans.
  - Mean absolute distance over columns known on both, ≥ 80% known, equal
    weights, k = 50.
  - The pool goes through the gate, is resolved before the query day, and
    **stops before 2024 until the holdout is run**.
- `python -m vnstock_research.backtest.neighbours SYMBOL DAY`.
- Sanity: TNH 2026-09-21, FPT 2026-09-18, ACB 2026-09-21: 50 neighbours each,
  all rules visible in the output
  (`research/reports/neighbours-sanity-2026-09-24.txt`).

## The engine
- **Limits:** `checks.limit_prices`.
- **Returns:** `forward_returns` (10 reasons, known_on, net PROVISIONAL).
- **G20:** 511 factor defects blanked like gaps.
- **Gate + evidence:** `backtest/evidence.py`.
- **Protocol:** `backtest/protocol.py` (discover / validate / summary; the
  holdout refused).
- **Look-alikes:** `backtest/neighbours.py`.

## Verified by running it this run
- `uv run pytest` → **516 passed, 0 failed, 0 skipped** (DB up); `ruff check
  .` → clean.
- **Strict proofs:**
  - E4 **23/23**, E3 33/33 (re-run);
  - earlier and unchanged: E2 46, E1 50, fingerprint 27, universe/breadth 17,
    sector 23, exchange 15, guards 5, T1 23, T2 36, T3 55, T4 20.

## Blockers / open
- **For Ben:**
  - the E3 questions (open-questions);
  - whether `pool_before` moves after the holdout (a new neighbours version).
- **G20 repair** (re-derive the factors / a new build + a gate check).
- X4, G19, G18, G2, G9, G10, G11.
- To confirm:
  - the limit rounding rules;
  - UPCoM's average-price reference;
  - the broker fee (NET is provisional).

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews E4 and merges.
2. **The holdout, together, once**: freeze the end date, run the 16 validated
   survivors under the pre-registered rule, record the result in the log.
   Nothing is tuned after.
3. Then G9 (ranking to one pick) and the daily scan.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 18–19 of
`logs/sessions/2026-09-23-session-03.md`. 4. `config/rules/protocol.yaml` and
`knowledge/validation.md`. 5. Only the code the task touches, via
`code-map.md`.
