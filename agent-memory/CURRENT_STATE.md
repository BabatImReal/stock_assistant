# Current state — 2026-09-24 (end of session 2026-09-23-03, run 16)

Rewritten from scratch. The figures were checked this run against the DB
(build 5 'good'; 2,511,070 bar_adjusted rows since 2012; 1,705 symbols), the
stored returns and fingerprint, and `git log`.

## Phase
**On main (`f53b72a`):** features (25), the nightly hardening, dated exchange
labels, the pattern catalogue (T1–T4) and the fingerprint (T5).
**Now: the ANALYSIS ENGINE on `features/analog-backtest`.** The design was
approved (A1–A12 + five additions; decisions.md run 16). **E1 is built and
awaiting Ben's review:** the shared limit function, the forward-return
generator and storage. Next: E2.

## Git: ONE working branch
- `main` = `f53b72a`. Only on Ben's say-so.
- **`features/analog-backtest`**: the proposal (`d6512e3`), then E1.

## E1: what exists
- **`checks.limit_prices`**: the ONE ceiling/floor.
  - The dated limit, or the first-day band (resumption ≥ 25 sessions skipped).
  - Ceiling rounded DOWN and floor UP to the tick of the limit price; one tick
    from the reference when rounding lands on it.
  - "At" = within half a tick.
  - `limits_sql` is its twin, used by the gate. A live test shows Python ==
    gate SQL row for row.
  - The rounding rules are to confirm with the exchange rulebooks.
- **B1 was a ~7x undercount:** liquid entries at the ceiling 0.929% (was
  0.133%), exits at the floor 2.272% (was 0.342%). Gate (warn): 4,521 dated /
  913 flagged (was 4,572 / 955).
- **`forward_returns.outcomes`**: per signal day t and k ∈ {3, 5}:
  - ret (adjusted), net (PROVISIONAL fee), mfe, mae, exit_offset, deferred,
    known_on (actual resolution), reason, upcom, flag__fill;
  - the reference price = adj prev close / today's factor (ex-dates);
  - flagged on undated exchanges, UPCoM, or no limits.
- **`store.py`**: the shared Parquet-by-year + manifest code (fingerprint +
  returns). `forward_returns.join` refuses two builds.
- **Real returns** `data/processed/returns/5_de0d00cf56ae1553/`: 2,511,070
  rows. k=3, liquid on t (897,588):
  - 97.42% resolved;
  - no outcome: window_gap 1.16%, entry_at_ceiling 0.78%, no_next_session
    0.44%, pending 0.12%, exit_floor_unresolved 0.04%, window_excluded
    0.02%, not_tradeable 0.01%, data_ends (G11) 97 rows, not_sellable 0;
  - 17.12% of liquid resolved outcomes are flagged, **11.80% on UPCoM**;
  - k=5: 96.63% resolved, UPCoM 11.64%.
- The fingerprint was rebuilt for the new code hash
  (`fingerprint/5_d51a9d818b0a54de`).

## Verified by running it this run
- `uv run pytest` → **424 passed, 0 failed, 0 skipped** (DB up).
- `uv run ruff check .` → clean. `ruff format --check` still flags older
  scripts (untouched; measure_fillability.py was already unformatted).
- **Strict proofs** (no exemptions; compile-checked; cache purged):
  - E1 50/50;
  - fingerprint 30/30, exchange 15/15, sector 23/23, universe/breadth 17/17,
    guards 5/5;
  - T1 23/23, T2 36/36, T3 55/55, T4 20/20.

## Blockers / open
- **G20 (NEW, not fixed):** the adjusted series jumps on factor-change days:
  1,818 stock-days, 525 symbols (BNA 2021-10-07: +111%). No gate check covers
  it. Needs Ben before any build change.
- X4, G19, G18, G2, G5 (the design is approved, not built), G9, G10, G11; B3
  (E2).
- **Environment:** the DB container was recreated 2026-09-24. Its 64 MB
  /dev/shm breaks big parallel joins, so heavy queries set
  `max_parallel_workers_per_gather = 0`. A `shm_size` fix needs Ben's OK.
- **To confirm:** the limit rounding rules; UPCoM's average-price reference.
- **Broker-friend questions:** in open-questions.md.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews E1 and merges.
2. **E2:** the validated gate (Validated features + returns, blank flagged
   fillability rows, purge by known_on, refuse mismatched builds), base rates
   on the identical population, the stock → liquidity tier → market fallback
   (≥ 30 de-clustered), a level on every number.
3. **E3:** the pre-registered holdout rule + hypothesis registry, exact
   combinations, discover/validate, BH-FDR, the survival count.
4. **E4:** kNN (T6). The holdout runs once, with Ben.

## Parked
TypeSafe / Jev; SSI FastConnect; the broker fee is provisional at 0.15%/side;
flag/pause (P7); pattern strength numbers (P9); precomputing market/sector
per fingerprint build; target-before-stop (waits for Ben's stop/target).

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Runs 15–16 of
`logs/sessions/2026-09-23-session-03.md` (run 15 = the engine proposal).
4. `knowledge/validation.md`. 5. Only the code the task touches, via
`code-map.md`.
