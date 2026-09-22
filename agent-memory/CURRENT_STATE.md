# Current state — 2026-09-22 (end of session 02, run 7)

## Phase
**Phase 4 — data foundation. Steps 1–3 DONE. Build 5 promoted (inferred factors).**
Step 4, the **nightly update, is NOT built** — Ben asked to stop and report the
checks and reconciliation first.

## What exists
- `docs/knowledge/pattern-research-knowledge.md` — source of truth.
- `CLAUDE.md` — carries the reconciliation principle; Phase 3 = free sources.
- `agent-memory/` — 14 knowledge files including **`data-model.md` (APPROVED)**,
  34 decisions, blockers G1–G15 (G12, G13, G15 closed or decided).
- Code: `data/{db,cafef,checks,reconcile}.py`, three migrations,
  `scripts/{load_history,run_checks,count_exchange_transfers,
  probe_free_sources,probe_matched_vs_deal}.py`, **18 tests passing**.
- Database: running, **build 2 promoted to 'good'**.
- Git: `86bd75d` P1, `87cac76` P2, `12fa239` P3, `29af8dc` G12,
  `5e7198d` P4 step 1, `d3d722f` P4 steps 2–3. Only run-4 memory is uncommitted.

## What is in the database (build 2)
- `bar_raw` **2,886,721 rows**, 1,709 symbols, **2000-07-28 → 2026-09-21**.
- Research window (2012+): **2,511,070** adjusted bars.
- Factors: 2,824,492 cafef, 47,334 vnstock, 14,775 inferred.
- `negotiated_volume` 4,228,174 rows (absence = unknown, never zero).
- `index_bar` 11,456 rows; `trading_day` 18,505 exchange-days; 116 symbols with
  more than one exchange span.

## Checks: all blocking checks PASS. Warnings that are real and known:
- 120 factors > 1 on **one** symbol (GGG), all pre-2012 — outside the window.
- 68 symbols whose latest factor ≠ 1.
- 4,028 exchange-days with < 20 symbols traded.
- 8,213 symbol-days since 2012 move beyond the price limit with no factor
  change — candidates for unadjusted corporate actions.
- 1,136 symbols missing > 20 sessions inside their listed range.
- 11,973 bars rejected at load with a close outside their own high-low range
  (6,160 of them since 2012) — a CafeF defect present in every year.

## Reconciliation (build 2, 10 symbols, 2012 → now, 34,314 days)
- **close 86.67%**, **volume 98.74%**.
- 2020 onwards is 99.7–100% every year. 2012–2014 is 65–69%.
- The gap is **three symbols with a constant-ratio adjustment-policy
  difference** — VNM ~0.9835, MBB ~1.08, PNJ ~1.031 — all ending January 2022.
  The other seven symbols are 98.9–100%.

## Exchange transfers (blocker G4) — COUNTED AND BACKFILLED
- **Backfilled 46 of the 47 liquid Class B symbols**: 47,334 bars, median gap
  3.1 years. ACB now runs from **2006-11-21** (14.1 years recovered), SHB 12.5y,
  VCG 12.3y. VLB skipped, no usable data.
- Backfilled spans carry `is_adjusted_source=true` and
  `volume_is_adjustable=false`: usable for price patterns and trend, and
  **volume signals must skip them**.

- **Class A = 116** (CafeF kept both spans; gaps now excused via
  `symbol_exchange`, no backfill needed).
- **Class B = 251** (pre-transfer history missing; 47 of them liquid).
  By exchange: UPCOM 164, HOSE 68, HNX 19. Verified by control test.
  Gap sizes are lower bounds — the probe asked a 3-year window.

## Missed corporate actions — HANDLED
Of 187 beyond-limit candidates in the liquid universe: 64 real moves,
**10 repaired** by inferring a round stock-dividend factor confirmed by a volume
jump (build 5, `source='inferred'`, `bar_raw` untouched), **113 excluded** as
unexplained in `excluded_window` (~16,025 calendar days). The volume test is
weak below ~20% dividend rates, which is why the repair rate is low.

## Open items needing Ben
- Suspension-resumption handling for the nightly job (open-questions).
- The 113 excluded windows would shrink a lot given a real corporate-action
  calendar.

## Next steps
1. Ben reviews the checks and reconciliation.
2. **Phase 4 step 4: the nightly update** (daily files are ~55 KB, not 176 MB).
3. Then the G4 backfill, then features.

## Open problems
- Blockers G1, G4, G14 have agreed approaches and are partly implemented; G11
  (survivorship) stands as partial; G5, G9, G10 remain untouched and are about
  research method, not data.
- 8,213 price-limit violations without a factor change have not been explained.

## Blockers
- Nothing on the data side.
- **Broker-friend elicitation** (doc §11.2) still has not happened.
- Ben's four questions (holding period, minimum liquidity, risk tolerance,
  daily-pick expectation) — G10, still blocking parameter fixing.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Only the knowledge files needed —
for data work that is `data-model.md`, `data-sources.md` and the G-blockers in
`open-questions.md`. 4. Only the code files the task touches, via `code-map.md`.
