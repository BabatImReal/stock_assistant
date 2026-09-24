# Current state — 2026-09-24 (end of session 2026-09-23-03, run 18)

Rewritten from scratch. Checked this run: the hypothesis log (1,636 rows), the
discover and validate results files, `git log`, and pytest. The DB and stored
tables are unchanged since run 17 (build 5 'good').

## Phase
**On main (`f53b72a`):** features (25), the nightly hardening, dated exchange
labels, the pattern catalogue (T1–T4) and the fingerprint (T5).
**The analysis engine, on `features/analog-backtest`:**
- the design, E1 (limits + forward returns + storage) and E2 (G20 + the gate +
  base rates + fallback) are approved;
- **E3 (the discover/validate protocol) is built and RUN, awaiting Ben's
  review.**

Next: E4 (kNN), then the holdout, once, with Ben.

## Git: ONE working branch
- `main` = `f53b72a`. Only on Ben's say-so.
- **`features/analog-backtest`**, in order:
  1. the proposal `d6512e3`;
  2. E1 `b4b601c`;
  3. E2 `067f085`;
  4. **the E3 pre-registration `b3ca180`, ALONE, before any code**;
  5. the E3 code `c132439`;
  6. then the E3 runs + log.

## E3: the result (holdout NOT run)
- **Protocol** (`config/rules/protocol.yaml`, frozen; its hash is in every log
  row):
  - 1,554 hypotheses: 21 triggers × up to 2 of 8 conditions × k {3, 5};
  - hit = net > 0 (PROVISIONAL fee), liquid on t, through the gate;
  - de-clustered occurrences, two-sided, date-block bootstrap (10 sessions ×
    2,000);
  - BH q = 0.10 over N;
  - validate: same sign, edge ≥ +3 pts, net > 0.
- **Discover 2012–2019:** N = 1,554 → 1,454 testable → **82 passed** (8 of
  them with negative edges).
- **Validate 2020–2023:** **16 HELD** of 82. They are led by
  three_black_crows / marubozu_red + high rvol: "bearish" labels behaving
  bullishly (doc §6.3). About 5 nested families, not 16 independent edges.
- The log is `research/hypothesis_log.csv`; the reports are in
  `research/reports/` (both in git).

## The engine, as it stands
- **Limits:** `checks.limit_prices`, one tick-rounded definition (Python ==
  gate SQL).
- **Returns:** `forward_returns.outcomes` (`returns/5_de0d00cf56ae1553`): 10
  reason codes, known_on, net PROVISIONAL. Liquid k=3: 97.41% resolved, 11.80%
  UPCoM-flagged.
- **G20:** `checks.factor_triage`. 511 genuine factor defects are blanked like
  gaps; the factors themselves are not repaired.
- **The gate:** `evidence.validated`, the ONE join (same build; feature and
  fillability quarantine; liquid on t; known strictly before T).
- **Evidence:** `evidence.evidence`, with the stock → tier → market fallback
  and sector shown as exploratory.
- **Protocol:** `backtest/protocol.py` (run: `python -m
  vnstock_research.backtest.protocol discover|validate`; the holdout is
  refused).

## Verified by running it this run
- `uv run pytest` → **499 passed, 0 failed, 0 skipped** (DB up); `ruff check
  .` → clean.
- **Strict proofs** (no exemptions; compile-checked; cache purged):
  - E3 **33/33**, E2 46/46 (re-run after the de-cluster refactor);
  - unchanged since run 17 and still genuine: E1 50, fingerprint 27,
    universe/breadth 17, sector 23, exchange 15, guards 5, T1 23, T2 36,
    T3 55, T4 20.

## Blockers / open
- **For Ben (E3):**
  - a validate rule for negative-edge "avoid" survivors? It would be an
    addition, tested on unused data only;
  - the nesting of the 16;
  - the p-value floor (0.001);
  - validate has no significance test (as registered).
- **G20 repair** (re-derive the factors / a new build + a gate check): needs
  Ben.
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
1. Ben reviews E3 and merges; he answers the E3 questions.
2. **E4:** kNN (T6), registered and evaluated as ONE method.
3. **The holdout:** once, with Ben, under the pre-registered rule.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 17–18 of
`logs/sessions/2026-09-23-session-03.md` (run 15 = the engine proposal).
4. `knowledge/validation.md` and `config/rules/protocol.yaml`. 5. Only the code
the task touches, via `code-map.md`.
