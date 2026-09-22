# Code map

Every folder and file in the repo, one line each. Updated at the end of every
run in which a file was added, repurposed or removed.

**Phase 2 (skeleton) complete and verified. All modules are intentionally empty
— docstrings only. No application logic exists yet.**

Verified 2026-09-22: `uv sync` on Python 3.12, `uv run pytest` 4 passed,
`ruff check` and `ruff format --check` clean, `pre-commit run --all-files`
7 hooks passed, `docker compose config` valid. Container verified running:
PostgreSQL 16.15 + timescaledb 2.30.1, healthy, named volume created.

## Root
| Path | Purpose | Depends on |
| --- | --- | --- |
| `CLAUDE.md` | Permanent session instructions: framing, memory procedure, principles, roadmap | — |
| `README.md` | How to run everything, written for someone new to Docker | — |
| `pyproject.toml` | Project definition + ruff and pytest config, managed by uv. Runtime deps empty on purpose | uv |
| `.python-version` | Pins the project to Python 3.12; uv downloads it if missing | uv |
| `uv.lock` | Exact resolved versions of the dev tools. Committed on purpose so every machine gets the same ruff and pytest | uv |
| `.pre-commit-config.yaml` | Pre-commit hooks: ruff lint+format, trailing whitespace, large-file and private-key guards | pre-commit |
| `.gitignore` | Ignores `.env`, `data/`, venv and caches | — |
| `.env.example` | Template for `.env`: SSI credentials + local Postgres settings. Real `.env` is never committed | — |
| `docker-compose.yml` | One service: PostgreSQL + TimescaleDB (`timescale/timescaledb:latest-pg16`), named volume, healthcheck. No Redis (doc §11.5) | Docker |

## Source of truth and memory
| Path | Purpose |
| --- | --- |
| `docs/knowledge/pattern-research-knowledge.md` | The knowledge document, 11 sections. **Never edit.** |
| `agent-memory/CURRENT_STATE.md` | Where the project is now; read first every session |
| `agent-memory/knowledge/00-index.md` | One line per knowledge file |
| `agent-memory/knowledge/project.md` | Goal, user, framing, scope (doc §1) |
| `agent-memory/knowledge/patterns.md` | Pattern catalogue and layered fingerprint (doc §2-3) |
| `agent-memory/knowledge/money-flow.md` | Volume measures, matched vs deal, foreign flow (doc §4) |
| `agent-memory/knowledge/context-vietnam.md` | Trend, S/R, regime, sector, news, VN rules (doc §5) |
| `agent-memory/knowledge/research-findings.md` | What the studies found (doc §6) |
| `agent-memory/knowledge/funnel-and-scale.md` | Research phase, daily funnel, report, scale (doc §7) |
| `agent-memory/knowledge/validation.md` | Traps, testing sequence, metrics (doc §8) |
| `agent-memory/knowledge/architecture.md` | Agent roles, code-vs-LLM split, data layer (doc §9-10) |
| `agent-memory/knowledge/data-sources.md` | SSI endpoints and fields; confirmed vs unconfirmed |
| `agent-memory/knowledge/code-map.md` | This file |
| `agent-memory/knowledge/decisions.md` | Date, decision, reason, rejected alternatives |
| `agent-memory/knowledge/open-questions.md` | Open items; 11 marked "must resolve before any measurement" |
| `agent-memory/logs/INDEX.md` | One line per session |
| `agent-memory/logs/sessions/2026-09-22-session-01.md` | Session 01 log |

## Package — `src/vnstock_research/`
All files are `__init__.py` with a docstring only. No functions yet.

| Path | Purpose (doc section) | Depends on |
| --- | --- | --- |
| `__init__.py` | Package overview and the pipeline order | — |
| `data/__init__.py` | SSI client, download, storage, price adjustment (§7.5, §4.3). Owns blockers G1, G2 | none yet; later the SSI API + Timescale |
| `features/__init__.py` | Volume, trend and context measures (§4-5). Matched volume only | `data` |
| `patterns/__init__.py` | Pattern rules as arithmetic on OHLCV (§3). Thresholds from `config/rules/` | `features` |
| `backtest/__init__.py` | Forward returns, base rates, validation (§2, §8). Owns blocker G3 | `patterns` |
| `report/__init__.py` | The daily recommendation or "nothing today" (§7.4, §7.3) | `backtest` |

## Everything else
| Path | Purpose |
| --- | --- |
| `config/rules/patterns.yaml` | Provisional textbook thresholds for candles, consolidations, volume and reliability (doc §3.5). Values are choices, not facts; fixed before testing |
| `tests/test_skeleton.py` | The one Phase 2 check: package imports, every stage has a docstring citing a doc section, thresholds live in config, `.gitignore` covers `.env` and `data/` |
| `data/raw/.gitignore` | Keeps the folder in git while ignoring its contents |
| `data/processed/.gitignore` | Same, for derived data |
| `scripts/.gitkeep` | Placeholder; `probe_ssi_history.py` lands here in Phase 3 |
| `notebooks/.gitkeep` | Placeholder for exploration notebooks |
