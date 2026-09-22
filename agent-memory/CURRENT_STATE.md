# Current state — 2026-09-22 (end of session 01, run 4)

## Phase
**Phase 2 — skeleton. COMPLETE and FULLY VERIFIED.**
**Blocked on Ben's confirmation before Phase 3.** Do not write the SSI probe or
anything that touches the API until he confirms.

## What exists
- `docs/knowledge/pattern-research-knowledge.md` — source of truth, read in
  full, never edited.
- `CLAUDE.md` — permanent session instructions (verbatim from Ben).
- `agent-memory/` — this memory system: 13 knowledge files, 21 decisions,
  open questions including 11 marked blockers, logs.
- Project skeleton: `pyproject.toml`, `.pre-commit-config.yaml`, `.gitignore`,
  `.env.example`, `docker-compose.yml`, `README.md`,
  `src/vnstock_research/{data,features,patterns,backtest,report}` (docstrings
  only), `config/rules/patterns.yaml`, `tests/test_skeleton.py`,
  git-ignored `data/raw/` and `data/processed/`, `scripts/`, `notebooks/`.
- Git: Phase 1 committed as `86bd75d`. **Phase 2 is not committed yet.**
- `.python-version` pins 3.12 — without it uv chose 3.13, which is not what Ben
  specified. `uv.lock` is committed so every machine gets the same tools.

## What works
Verified by running it, 2026-09-22:
- `uv sync` → Python **3.12.14**, 17 dev packages installed.
- `uv run pytest` → 4 passed.
- `uv run ruff check .` → clean. `uv run ruff format --check .` → 26 files
  already formatted.
- `uv run pre-commit run --all-files` → 7 hooks passed.
- `docker compose config` → valid, defaults expand correctly.
- `docker compose up -d` (run by Ben) → `vnstock-db` up and **healthy** on
  5432; PostgreSQL 16.15 with the **timescaledb 2.30.1 extension already
  created**, so no `CREATE EXTENSION` step is needed; named volume
  `stock_assistant_vnstock-db-data` created. The README's
  `docker compose exec db psql -U vnstock -d vnstock` works as written.

## What is NOT verified
Nothing in Phase 2. Everything written has been run.

## In progress
Nothing. Session 01 run 2 is finished and reported.

## Next steps (in order)
1. **Ben confirms** Phase 3, and supplies SSI FastConnect credentials in `.env`
   (registration is in person — doc §11.4 step 2).
2. **Phase 3 — SSI history probe** (`scripts/probe_ssi_history.py`): auth, then
   DailyStockPrice vs DailyOhlc for VNM, SSI, FPT, HPG, ACB at Jan 2012, Jan
   2013, Jan 2015, Jan 2020 and last week; one delisted symbol; DailyStockPrice
   with no symbol for a single day to test whole-market and paging; DailyIndex
   for VNINDEX on the same dates. Save every raw JSON unchanged to
   `data/raw/probe/`. ~1s between requests. Print a plain-English report:
   earliest date per symbol, fields actually returned vs doc §7.5, whether
   matched-vs-deal, foreign flow and adjusted close exist in older years, and
   any errors, range limits or rate limits. Then update
   `knowledge/data-sources.md` with confirmed findings.
3. Only after the probe: schema and full download plan, designed with Ben.

## Open problems
- **11 blockers** in `knowledge/open-questions.md` under "must resolve before
  any measurement" (G1–G11). The ones that change the design: G1 volume must be
  adjusted alongside price; G2 adjusted close may be re-stated and drift on
  every nightly update; G3 the forward-return definition is not tradeable under
  t+1 entry and T+2; G5 the analog search has no overfitting defences; G9 the
  final ranking function is undefined.
- Eight tooling decisions were made in run 2 without asking Ben (see
  `knowledge/decisions.md`, Phase 2 section). They are conventional and within
  his stated stack, but CLAUDE.md says to ask before architectural decisions —
  raised in the reply for him to overrule.

## Blockers
- **SSI FastConnect credentials** — Ben must register in person. Phase 3 cannot
  run without them; `knowledge/data-sources.md` stays entirely unconfirmed.
- **Broker-friend elicitation session** (doc §11.2) has not happened. It is the
  real source of edge.
- Four of Ben's own questions (holding period, minimum liquidity, risk
  tolerance, whether a daily pick is expected) must be answered before any
  parameter is fixed — `validation.md` requires parameters fixed *before*
  testing, and `config/rules/patterns.yaml` currently holds provisional guesses.


## Reading order for the next session
1. This file.
2. `knowledge/00-index.md`.
3. Only the knowledge files the task needs.
4. Only the code files the task touches, found via `knowledge/code-map.md`.
   Never scan the repo.
