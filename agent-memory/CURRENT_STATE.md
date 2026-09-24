# Current state — 2026-09-24 (end of session 2026-09-23-03, run 25)

Rewritten from scratch. Checked this run: `git rev-parse` (main untouched),
the md5 of the original hypothesis log (unchanged, 16 holdout rows), the batch
log counts, and pytest.

## Phase
- **main (`00b3be2`):** everything through the daily scan + paper-trading
  ledger (daily_scan v2, HOSE first). Untouched; only Ben merges.
- **`features/new-hypotheses` (the ONE working branch, cut from main):** the
  new-hypothesis batch `complements_1`. Awaiting Ben's review.

## Git (features/new-hypotheses)
1. `68d3fe1`: REGISTER the batch (block, code, tests). Runs nothing.
2. `c4e6922`: the runs (discover, then validate) + reports.
3. The run-25 memory commits.

## Batch complements_1 (CANDIDATE GENERATION, not confirmation)
- **Rule:** each of the 8 registered conditions + its EXACT complement (same
  measure, other side). 21 triggers × every 1–2 of the 16 with ≥ 1
  complement and no self pair × k 3, 5 = **N 3,864**. Block hash
  `e29e367cba78c47f`. Hypotheses ever tested: 5,418.
- Hit = GROSS > 0 (fee out of scope; net at 0.40% is information only).
  Discover = BH q 0.10 over 3,864 + abs(edge) ≥ 3 pts; validate = same
  sign + gross expectancy > 0.
- **Discover 269** (175 +, 94 −) → **validate 188 held** → **151
  paper-trading candidates** (edge > 0; 49 families; 28 with validate
  p < 0.05).
- **NONE is materially stronger than the best of the six.**
  - The six's best: 3crows+breadth+rvol, edge +18.2%, gross +2.33%, 11/12
    years.
  - The best new one: k5 inverted_hammer+ma_50_rising+not_market_up, edge
    +10.5%, gross +2.19%, 11/12 years, 1,077 trades.
- Many candidates are near-duplicates of registered ones (near-universal
  complements such as not_at_support). The new region is the weak market
  (not_market_up).
- The rows are in `research/hypothesis_log_batches.csv` only. The original
  log is byte-identical, and the holdout has no new rows.
- Reports: `research/reports/batch-complements_1-{discover,validate}.txt`.

## The daily scan + paper trading (on main, unchanged)
- `daily_scan` v2: the 6 holdout ACCEPTs; HOSE first → validate expectancy →
  traded value → tier → symbol.
- `paper_trading`: Ben's pass rule; the forward record starts after
  2026-09-24; no verdict while the fee is PROVISIONAL.
- Ledger: 7 days before the freeze; FPT 09-18 is pending; no forward row yet.

## Verified by running it this run
- pytest **625 passed, 0 failed, 0 skipped** (DB up); `ruff check .` clean.
- Strict proofs:
  - batch 28/28;
  - re-run: holdout 33/33, E3 33/33, E4 23/23, describe 14/14, scan 41/41;
  - earlier and unchanged: E2 46, E1 50, fingerprint 27, universe/breadth 17,
    sector 23, exchange 15, guards 5, T1 23, T2 36, T3 55, T4 20.

## Blockers / open (open-questions.md)
- Ben: review the batch design for bias. Should any candidate enter the
  forward test? That needs a new daily_scan version, BEFORE forward rows
  exist.
- **Data must flow for the forward test.** After each session:
  1. `nightly_update`;
  2. `fingerprint.build` (~20 min);
  3. `forward_returns.build`;
  4. `report.scan`.

  Then `report.paper score`. Nothing is scheduled.
- Ben: the tier-direction wording, the UPCoM/undated exclusion, the real
  broker fee.
- G20 repair; X4, G19, G18, G2, G10, G11; the limit rounding / UPCoM
  reference.

## Ben's standing expectations
Research reaches 100%; "ready for money" at least 50–60%. Focus HOSE ~85% /
HNX ~12% / UPCoM ~3%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews `features/new-hypotheses` and decides on the candidates.
2. Run the daily pipeline so the forward record starts.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop;
the "crowded day" idea; moving `pool_before` past 2024.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 22–25 of
`logs/sessions/2026-09-23-session-03.md`. 4. `config/rules/protocol.yaml`
(`daily_scan`, `paper_trading`, `batches`). 5. Only the code the task touches,
via `code-map.md`.
