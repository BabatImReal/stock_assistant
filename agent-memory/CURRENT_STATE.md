# Current state — 2026-09-22 (end of session 02, run 2)

## Phase
**Phase 3 — free-source probe. COMPLETE, RUN, and committed (`12fa239`).**
G12 tested and CLOSED. Ben's decisions recorded.
**Next is the schema and full download plan, to be designed WITH Ben.** Still do
not bulk-download or design the schema unprompted.

## What exists
- `docs/knowledge/pattern-research-knowledge.md` — source of truth. Ben replaced
  it this session; the new part is §7.5 "Data source decision (2026-09-22)".
- `CLAUDE.md` — now carries the reconciliation principle and Phase 3 = free
  sources.
- `agent-memory/` — 13 knowledge files, 24 decisions, 15 blockers (G1–G15).
- Code: `src/vnstock_research/data/reconcile.py` (real), the five pipeline
  modules (still docstrings only), `scripts/probe_free_sources.py`,
  `tests/test_skeleton.py` + `tests/test_reconcile.py` = **13 tests passing**.
- Data on disk (git-ignored): `data/raw/cafef/2026-09-21/` ~176 MB,
  `data/reports/` probe + reconciliation reports.
- Git: Phase 1 `86bd75d`, Phase 2 `87cac76`. **Session 02 is uncommitted.**

## What the probe confirmed
- **CafeF** is a real primary source: HSX back to 2000-07-28, HNX 2001, UPCOM
  2002 — far past the 2012 window. 474 real HOSE tickers (the other ~2,000 are
  covered warrants and must be filtered).
- **Adjusted ÷ unadjusted = the corporate-action factor**, exactly as hoped.
- **Delisted stocks: partially present** — real history for many, stubs for some.
- **CafeF vs vnstock: close 87.8%, volume 99.8%** over 16,098 symbol-days,
  2012→now. FPT/SSI/HPG/ACB are 98.9–100%. VNM's 47.7% is ONE adjustment-policy
  difference, not corruption.

## What the probe found wrong (all now blockers)
- **G12 CLOSED** — measured, not assumed: CafeF bulk volume is **matched-only**
  (20/20 on the largest-deal days, 0/20 for matched+deal). No scraper, no SSI
  purchase. And the `NN_` files carry the split after all: `<High>` = matched,
  `<Low>` = negotiated. **This corrects a wrong claim in my Phase 3 report.**
- **G13 DECIDED** — foreign flow excluded from all signals until a live source
  exists; recorded as a later layer.
- **G14 the index file has phantom weekend sessions** — the trading calendar
  cannot come from it as-is.
- **G15 DECIDED** — CafeF is canonical for adjustment; the VNM 1.65% gap is a
  policy difference, not an error.
- **G1 confirmed unsolved: CafeF does not adjust volume** (adjusted volume ==
  unadjusted volume on 100% of days).
- **G4 confirmed real: ACB's pre-2020 HNX history is in no CafeF bulk file.**

## Traps to remember about the sources
- vnstock's 8-year cap is **stateful**: one long request silently truncates every
  later call in the process. Fetch in 4-year chunks; never make a long request
  first. The wrong answer looks entirely plausible.
- Unregistered vnstock is **20 req/min**, not 60. It aborts rather than backs off.
- CafeF CSVs have a UTF-8 BOM and AmiBroker `<Header>` names that mean nothing in
  the CC_/NN_ files.

## Decisions Ben has made (session 02, run 2)
- Store **everything from 2000**; the research window stays **2012 → now**.
- **CafeF canonical** for adjustment; the VNM divergence is a policy difference.
- **Foreign flow excluded** from all signals until a live source is confirmed.
- Download-plan recommendations **1–6 accepted**.
- **Register the free vnstock key** before the G4 backfill; Ben adds
  `VNSTOCK_API_KEY` to `.env`.
- **G12 tested before choosing** — and it closed.

## Next steps
1. Ben reviews the G12 result.
2. **Schema and full download plan, designed together.** Nothing on the data
   side blocks it now: G1 (we compute the volume factor ourselves), G4 (vnstock
   backfill for exchange transfers) and G14 (calendar from stock rows) all have
   agreed approaches.
3. Then the download itself, then features.

## Parked, not forgotten
- **TypeSafe / Jev** for the later news-veto worker — see "Tools to evaluate
  later" in `knowledge/open-questions.md`.
- **SSI FastConnect** — paused, notes kept in `knowledge/data-sources.md`. Its
  main advantage (the matched/negotiated split) is no longer a reason to buy it:
  CafeF has that. Foreign flow is now the only thing it clearly offers that the
  free sources do not.

## Blockers
- Nothing on the data side. What remains is Ben's input on the schema.
- **Broker-friend elicitation session** (doc §11.2) still has not happened. It
  is the real source of edge.
- Ben's four original questions (holding period, minimum liquidity, risk
  tolerance, whether a daily pick is expected) — parameters cannot be fixed
  before they are answered (blocker G10).

## Reading order for the next session
1. This file.
2. `knowledge/00-index.md`.
3. Only the knowledge files the task needs — for data work that is
   `data-sources.md` and the G-blockers in `open-questions.md`.
4. Only the code files the task touches, found via `knowledge/code-map.md`.
   Never scan the repo.
