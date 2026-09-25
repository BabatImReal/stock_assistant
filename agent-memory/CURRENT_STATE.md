# Current state — 2026-09-25 (end of session 2026-09-23-03, run 26)

Rewritten from scratch. Checked this run: `git rev-parse` (main at `dfabd5b`,
untouched after the merge Ben chose), the md5 of the original hypothesis log
(unchanged, 16 holdout rows) and of the complements_1 rows (unchanged), the
old fingerprint loading, and pytest.

## Phase
- **main (`dfabd5b`):** everything through complements_1. `new-hypotheses`
  was merged at Ben's choice at the start of run 26, then deleted.
- **`features/structural-features` (the ONE working branch):** the
  structural features + batch `structural_1`. Awaiting Ben's review.

## Git (features/structural-features)
1. `1b04481`: structural features + the new fingerprint + tests.
2. `af8d7bf`: REGISTER batch structural_1. Runs nothing.
3. `7333818`: the runs + reports (+ the ever-tested count fix).
4. The run-26 memory commit.

## Structural features (src/vnstock_research/structural.py)
- **Measures:**
  - rs_index_20d/60d/120d (stock minus VN-Index return);
  - down_day_rs_20d (stock minus index on index-down days);
  - price_vs_ma_200;
  - ma_200_slope;
  - trend_stage 1–4.
- They follow the full base.py discipline, with a look-ahead test each.
- **They sit OUTSIDE features/**, so the registered featureset (holdout,
  neighbours, scan) keeps loading. Their code hash rides in the params.
- Fingerprint `5_f6181075e5962796` = features.yaml + structural.yaml on
  build 5. The old one, `5_d51a9d818b0a54de`, still loads; the registered
  columns are identical.
- Skipped: base quality (free parameters), sector RS (current-only labels,
  B3).

## Batches (candidate generation; the holdout stays sealed)
- **complements_1** (N 3,864): 151 candidates.
- **structural_1** (N 3,024, hash `1ff6d6de2472c886`): trigger × ONE of 8
  structural conditions × (none or ONE registered) × k 3,5.
  - Discover 295 → validate 260 held → **236 candidates** (63 with
    validate p < 0.05).
  - **NONE is materially stronger than the six or complements_1.**
  - The signal sits in relative strength (rs_60 57 candidates, rs_120 43,
    rs_20 40, resists 36) and stage 2 (47). Stage 1 and 4 have none.
- Hypotheses ever tested: 8,442. BH is within each batch, with nothing
  across batches, so survivors are candidates only.
- Rows are in `research/hypothesis_log_batches.csv` only; the original log
  is byte-identical.

## Verified by running it this run
- pytest **657 passed, 0 failed, 0 skipped** (DB up); `ruff check .` clean.
- Strict proofs:
  - structural 23/23, structural batch 9/9;
  - re-run: complements 28/28, holdout 33/33, E3 33/33, E4 23/23,
    describe 14/14, scan 41/41.

## The daily scan + paper trading (unchanged)
- daily_scan v2 trades the 6 holdout ACCEPTs, HOSE first.
- The forward record starts after 2026-09-24. There are no forward rows
  yet, because the pipeline does not run.

## Blockers / open (open-questions.md)
- Ben: whether any candidate joins the forward test (a new daily_scan
  version, before forward rows exist).
- **Data must flow for the forward test.** After each session:
  1. `nightly_update`;
  2. `fingerprint.build` (~20 min);
  3. `forward_returns.build`;
  4. `report.scan`.

  The structural fingerprint is a separate ~24-min build. Nothing is
  scheduled.
- Ben: the tier-direction wording, the UPCoM/undated exclusion, the real
  broker fee.
- G20 repair; X4, G19, G18, G2, G10, G11.

## Ben's standing expectations
Research reaches 100%; "ready for money" at least 50–60%. Focus HOSE ~85% /
HNX ~12% / UPCoM ~3%.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews `features/structural-features`.
2. Run the daily pipeline so the forward record starts.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); base quality / VCP; sector RS (needs point-in-time labels);
precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 24–26 of
`logs/sessions/2026-09-23-session-03.md`. 4. `config/rules/protocol.yaml`
(`batches`), `config/rules/structural.yaml`. 5. Only the code the task
touches, via `code-map.md`.
