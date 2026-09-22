# Current state — 2026-09-22 (end of session 01, run 1)

## Phase
**Phase 1 — understand the doc, build memory. COMPLETE.**
**Blocked on Ben's confirmation before Phase 2.** Do not write application
code, dependency files, Docker files or the skeleton until he confirms.

## What exists
- `docs/knowledge/pattern-research-knowledge.md` — the source of truth, 11
  sections, 507 lines. Read in full. Never edit it.
- `CLAUDE.md` — permanent session instructions, written verbatim from Ben.
- `agent-memory/` — this memory system, fully populated:
  13 knowledge files, decisions table (13 entries), open questions (22 items),
  logs with session 01.

## What works
Nothing executable. There is no code, no data, no database, no dependencies.
This is deliberate — Phase 1 is reading and note-taking only.

## In progress
Nothing. Session 01 run 1 is finished and reported to Ben.

## Next steps (in order)
1. **Ben confirms** the Phase 1 summary, the risk list and the gaps.
2. **Phase 2 — skeleton:** Python 3.12 + uv; ruff, pytest, pre-commit; empty
   `src/vnstock_research/{data,features,patterns,backtest,report}` modules each
   with a docstring naming its doc section; `config/rules/` for pattern
   parameters as config; git-ignored `data/raw/` and `data/processed/`;
   `scripts/`, `tests/`, `notebooks/`; `docker-compose.yml` with PostgreSQL +
   TimescaleDB **only** (no Redis yet); `.env.example` with `SSI_CONSUMER_ID`
   and `SSI_CONSUMER_SECRET`; `.gitignore` covering `.env` and `data/`;
   `README.md` written for someone new to Docker. `agent-memory/` **is**
   committed.
3. **Phase 3 — SSI history probe** (`scripts/probe_ssi_history.py`): learn what
   data really exists before designing any schema. Assume no field names.
4. Only after the probe: schema and full download plan, designed with Ben.

## Open problems
- Six concrete gaps found in the document — see the "technical/factual" section
  of `knowledge/open-questions.md`. The ones that change the design are: volume
  adjustment alongside price adjustment; re-stated adjusted closes drifting on
  nightly updates; the forward-return definition not matching t+1 entry and
  T+2 settlement; and §8's overfitting defences not covering the §3.6 analog
  search.
- Two items stated both ways in the doc: market regime as filter vs reported
  dimension; "full history / from 2010" vs the 2012 start.
- "Rank by evidence strength" (doc §7.2 step 7) is undefined.

## Blockers
- **SSI FastConnect credentials.** Ben must register in person (doc §11.4
  step 2). Phase 3 cannot run without them, and everything in
  `knowledge/data-sources.md` stays unconfirmed until it does.
- **Broker-friend elicitation session** (doc §11.2) has not happened. It is the
  real source of edge and nothing else substitutes for it.
- Four of Ben's own open questions (holding period, minimum liquidity, risk
  tolerance, whether a daily pick is expected) must be answered before any
  parameter is fixed — `validation.md` requires parameters fixed *before*
  testing.

## Reading order for the next session
1. This file.
2. `knowledge/00-index.md`.
3. Only the knowledge files the task needs.
4. Only the code files the task touches, found via `knowledge/code-map.md`.
   Never scan the repo.
