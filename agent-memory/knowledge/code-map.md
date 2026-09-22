# Code map

Every folder and file in the repo, one line each. Updated at the end of every
run in which a file was added, repurposed or removed.

**There is no application code yet** (Phase 1). Current contents:

| Path | Purpose | Depends on |
| --- | --- | --- |
| `CLAUDE.md` | Permanent instructions for every session: project framing, memory procedure, non-negotiable principles, roadmap | — |
| `docs/knowledge/pattern-research-knowledge.md` | **Source of truth.** The full knowledge document, 11 sections. Never edit. | — |
| `agent-memory/CURRENT_STATE.md` | Where the project is right now; read first in every session | — |
| `agent-memory/knowledge/00-index.md` | One line per knowledge file | — |
| `agent-memory/knowledge/project.md` | Goal, user, framing, scope (doc §1) | the doc |
| `agent-memory/knowledge/patterns.md` | Pattern catalogue and the layered fingerprint idea (doc §2-3) | the doc |
| `agent-memory/knowledge/money-flow.md` | Volume measures, matched vs deal, foreign flow (doc §4) | the doc |
| `agent-memory/knowledge/context-vietnam.md` | Trend, S/R, regime, sector, news, VN trading rules (doc §5) | the doc |
| `agent-memory/knowledge/research-findings.md` | What the studies found about pattern reliability (doc §6) | the doc |
| `agent-memory/knowledge/funnel-and-scale.md` | Research phase, daily funnel, report contents, scale (doc §7) | the doc |
| `agent-memory/knowledge/validation.md` | Traps, testing sequence, metrics (doc §8) | the doc |
| `agent-memory/knowledge/architecture.md` | Agent roles, code-vs-LLM split, data layer (doc §9-10) | the doc |
| `agent-memory/knowledge/data-sources.md` | SSI endpoints and fields; confirmed vs unconfirmed | the doc, later the Phase 3 probe |
| `agent-memory/knowledge/code-map.md` | This file | — |
| `agent-memory/knowledge/decisions.md` | Date, decision, reason, rejected alternatives | — |
| `agent-memory/knowledge/open-questions.md` | Unresolved items for Ben, the broker friend, or data | — |
| `agent-memory/logs/INDEX.md` | One line per session | — |
| `agent-memory/logs/sessions/2026-09-22-session-01.md` | Session 01 log | — |

Not yet created (Phase 2): `src/vnstock_research/`, `config/rules/`, `data/`,
`scripts/`, `tests/`, `notebooks/`, `docker-compose.yml`, `.env.example`,
`.gitignore`, `README.md`, `pyproject.toml`.
