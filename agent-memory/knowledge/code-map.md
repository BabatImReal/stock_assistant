# Code map

Every folder and file in the repo, one line each. Updated at the end of every
run in which a file was added, repurposed or removed.

**Phase 4 steps 1-3 complete (schema, historical load, checks + reconciliation).
Build 2 is promoted and holds 2.84M bars from 2000-07-28. The nightly job is
NOT built yet. The feature/pattern/backtest/report modules are still empty.**

Earlier note kept for context: **Phase 3 (free-source probe) complete. Real code:
`reconcile.py` and the probe script. The feature/pattern/backtest/report modules
are still docstrings only.**

Verified 2026-09-22: `uv sync` on Python 3.12, `uv run pytest` 13 passed,
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
| `data/__init__.py` | Download, storage, price adjustment (§7.5, §4.3). Owns blockers G1, G2 | pandas |
| `data/db.py` | Connection from `DATABASE_URL`, `.env` loader, and the migration runner (numbered .sql files recorded in `schema_migration`) | psycopg |
| `data/cafef.py` | Everything format-specific about CafeF's bulk files: BOM, AmiBroker headers that mean nothing in CC_/NN_, 3-letter filter, weekend rejection for the index | pandas |
| `data/checks.py` | The data-quality gate: 14 checks, `fail` blocks promotion, `warn` is recorded. Includes the traded-value invariant, the key proof that G1 was done right | psycopg |
| `data/reconcile.py` | **Real code.** Two-source reconciliation: `normalise`, `reconcile_column`, `reconcile`, `sample_by_year`, `missing_trading_days`, `write_report`, `ReconResult`. Tolerances `PRICE_TOLERANCE=0.5%`, `VOLUME_TOLERANCE=1%` with the reasoning in comments. Built for both the post-download sample check and the nightly all-stock check | pandas |
| `features/__init__.py` | Package docstring plus the registry exports; importing it registers the §4.1 measures | `data` |
| `features/base.py` | **The measure contract.** `Measure`, `REGISTRY`, the `@measure` decorator, `compute()`, `FeatureSet`. Enforces the three guarantees centrally: no look-ahead, no window spans a gap or an excluded row, volume measures NaN on non-adjustable spans. NaN / 0 / no-column are three distinct states | pandas, pyyaml |
| `features/bars.py` | Loads one symbol's bars from the **current promoted build only**, with `gap_before` in SESSIONS (from `trading_day`) and an `excluded` flag from `excluded_window`. Reads ADJUSTED matched volume so a window spanning a split has a consistent share basis | pandas, `data.db` |
| `features/trend.py` | The ten doc §5.1-5.2 per-symbol measures: ma_20/50, their slopes, price_vs_ma_20/50, price_change_10d/20d, near_support, near_resistance. PRICE only, so they remain available on backfilled spans | pandas, `features.base` |
| `features/volume.py` | The seven doc §4.1 measures: rvol, sustained_volume, up_down_volume_ratio, price_volume_agreement, price_volume_divergence, traded_value, volume_dry_up. Matched volume only | pandas, `features.base` |
| `patterns/__init__.py` | Pattern rules as arithmetic on OHLCV (§3). Thresholds from `config/rules/` | `features` |
| `backtest/__init__.py` | Forward returns, base rates, validation (§2, §8). Owns blocker G3 | `patterns` |
| `report/__init__.py` | The daily recommendation or "nothing today" (§7.4, §7.3) | `backtest` |

## Everything else
| Path | Purpose |
| --- | --- |
| `config/rules/patterns.yaml` | Provisional textbook thresholds for candles, consolidations, volume and reliability (doc §3.5). Values are choices, not facts; fixed before testing |
| `tests/test_skeleton.py` | The Phase 2 checks: package imports, every stage has a docstring citing a doc section, thresholds live in config, `.gitignore` covers `.env` and `data/` |
| `tests/test_reconcile.py` | 9 checks on reconciliation: identical sources match, tolerance boundaries, one-sided days never count as agreement, a zero is a mismatch not a crash, an empty comparison is not a perfect score, volume uses its own looser band, a constant ratio surfaces as `median_ratio`, gaps only count inside a symbol's listed range, sampling touches every year |
| `migrations/001_initial.sql` | All tables from the approved data model, with the reasoning in comments | — |
| `migrations/002_hypertables.sql` | Timescale hypertables chunked by year, plus indexes | — |
| `migrations/003_fix_precision_and_date_shift.sql` | Widens `bar_adjusted.matched_volume` to numeric(24,6) (2dp broke the traded-value invariant on small-volume days) and adds `bar_raw.date_shifted` | — |
| `scripts/load_history.py` | The one-time historical load: bar_raw → factors → negotiated → index → calendar → symbol master → bar_adjusted. Creates a build at status 'building' | pandas, `data.cafef`, `data.db` |
| `scripts/run_checks.py` | Runs the checks and the cross-source reconciliation, stores both, and promotes the build to 'good' only if nothing blocking failed | `data.checks`, `data.reconcile`, vnstock |
| `scripts/verify_date_shifts.py` | Checks every `date_shifted` bar against vnstock on exact volume match; deletes the ones that cannot be verified, cascading to `adjustment_factor` and `bar_adjusted` | pandas, vnstock, `data.db` |
| `scripts/investigate_warnings.py` | Classifies the beyond-price-limit moves, explains the latest-factor≠1 symbols, and reports every warning whole-market vs liquid universe | pandas, pyyaml, `data.db` |
| `migrations/004_inferred_factors_and_exclusions.sql` | `adjustment_factor.source` ('cafef'/'inferred'/'vnstock') and the `excluded_window` table | — |
| `scripts/repair_missed_actions.py` | Infers the factor for a missed corporate action from a round stock-dividend ratio confirmed by a volume jump; writes a new build; excludes what it cannot repair | pandas, vnstock, `data.checks` |
| `scripts/backfill_transfers.py` | Backfills pre-transfer history from vnstock for the liquid Class B symbols, flagged so volume signals skip those spans | pandas, vnstock, `data.db` |
| `src/vnstock_research/backtest/forward_returns.py` | **G3 implemented.** Settlement eras, `earliest_sell_offset`, `valid_horizons`, ceiling/floor detection, gross→net with fees and sale tax | pyyaml |
| `scripts/nightly_update.py` | The nightly job: daily CafeF files, append, factors, checks, promote — with a heartbeat row every run | requests, pandas, `data.*` |
| `scripts/check_backfill_seams.py` | Measures and rescales the level mismatch where a backfilled span meets CafeF; refuses to rescale across long gaps | pandas, `data.db` |
| `scripts/measure_fillability.py` | How often the ceiling/floor rules bite, whole market vs liquid | pyyaml, `data.checks` |
| `migrations/005_job_run.sql` | The `job_run` heartbeat table | — |
| `config/rules/features.yaml` | Which measures are on and with what parameters — switching one off is a config change, never a code change | — |
| `scripts/report_features.py` | Occurrence rates and distributions per measure, plus the NaN share and why | pandas, `features` |
| `tests/_helpers.py` | The shared synthetic-symbol frame, so both feature suites test against the same fixture | — |
| `tests/test_features_trend.py` | 11 tests for §5.1-5.2, including that trend measures STILL compute on a non-adjustable-volume span (the complement of the volume guard) and that support does not count an unconfirmed pivot | — |
| `tests/test_features_volume.py` | 16 tests: the arithmetic, and failing-without-the-guard tests for both contracts (gap→NaN, non-adjustable volume→NaN), NaN vs 0 vs disabled, and a truncation-based look-ahead test | — |
| `config/rules/costs.yaml` | Broker fee (provisional) and the 0.1% sale tax | — |
| `config/rules/market_rules.yaml` | Price limits **with the date each took effect** and tick sizes by price band; settlement cycle. Used by the price-limit check | — |
| `scripts/analyse_missed_actions.py` | For beyond-limit moves in the liquid universe, compares our adjusted series against vnstock's to tell "CafeF missed a corporate action" from "the move was real" | pandas, vnstock, `data.checks` |
| `tests/test_data_integrity.py` | Live-database checks, skipped when no DB: `date_shifted` really is written, no weekend bars survive, the price-limit SQL uses the rule in force | psycopg |
| `config/rules/universe.yaml` | Liquidity floor (defines the "liquid universe"), research start date, and `exclude_date_shifted` | — |
| `scripts/count_exchange_transfers.py` | Counts symbols affected by exchange transfers (G4): class A from CafeF alone, class B by asking vnstock for the window before CafeF's first date | pandas, vnstock |
| `tests/test_db.py` | Schema checks that need no server: migrations ordered, 3-letter constraint present, negotiated volume cannot be faked with a zero row | — |
| `scripts/probe_matched_vs_deal.py` | **G12 test.** Fetches CafeF's per-stock history endpoint (which publishes matched and negotiated separately), finds the largest-deal stock-days, and compares bulk volume against matched-only vs matched+deal. Also identifies `NN_<High>`/`NN_<Low>` as matched/negotiated and reports their coverage by year | requests, pandas |
| `scripts/probe_free_sources.py` | **Phase 3 probe.** Parses the CafeF download page for the newest complete date, downloads and unzips the five "Upto" files (cached), reports columns/coverage/delisted candidates/adjustment factors/missing sessions, decodes the CC_ and NN_ columns by value comparison, fetches vnstock in 4-year chunks, and reconciles both CafeF variants against it | requests, pandas, vnstock, `data.reconcile` |
| `data/raw/.gitignore` | Keeps the folder in git while ignoring its contents |
| `data/processed/.gitignore` | Same, for derived data |
| `scripts/.gitkeep` | Placeholder from Phase 2 |
| `data/reports/` | Git-ignored probe and reconciliation reports |
| `notebooks/.gitkeep` | Placeholder for exploration notebooks |
