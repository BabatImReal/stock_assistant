# Current state — 2026-09-22 (end of session 02, run 1)

## Phase
**Phase 3 — free-source probe. COMPLETE and RUN against the live sources.**
**Blocked on Ben's decisions before Phase 4.** Do not design the schema, do not
bulk-download, do not write a scraper.

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
- **G12 no free source splits matched vs negotiated volume** — collides with a
  non-negotiable principle. Needs Ben's decision.
- **G13 foreign flow in CafeF's NN_ files is all-zero since January 2025** —
  populated 2015–2024, then stops.
- **G14 the index file has phantom weekend sessions** — the trading calendar
  cannot come from it as-is.
- **G15 CafeF and vnstock use different adjustment policies** — VNM differs by a
  constant 1.65% before 2019-09-13.
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

## Next steps — Ben decides first
1. **G12**: scrape CafeF per-stock pages for the split, accept total volume with
   the limitation stated, or pay for SSI.
2. **G15**: which adjustment policy is canonical (proposal: CafeF, because its
   adjusted/unadjusted pair also yields the volume factor G1 needs).
3. **The full download plan**, from the report.
4. Only then: schema.

## Parked, not forgotten
- **TypeSafe / Jev** for the later news-veto worker — see "Tools to evaluate
  later" in `knowledge/open-questions.md`.
- **SSI FastConnect** — paused, notes kept in `knowledge/data-sources.md`. It is
  the only confirmed source of the matched/negotiated split.

## Blockers
- The four decisions above.
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
