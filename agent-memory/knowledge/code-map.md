# Code map

Every folder and file in the repo, one line each. Updated at the end of every
run in which a file was added, repurposed or removed.

**Phase 5 (features) in progress; 25 measures built (breadth + PIT universe on `features/breadth-pit-build`; sector on `features/sector-build`). Build 5 is promoted
(2.89M bars from 2000-07-28). The nightly job exists (not scheduled; G16: it never
writes `index_bar`). `patterns/` and `report/` are still docstrings only;
`backtest/` holds `forward_returns.py`.** (Updated 2026-09-23.)

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
| `agent-memory/logs/sessions/*.md` | One log per session; listed in `logs/INDEX.md` |

## Package — `src/vnstock_research/`

| Path | Purpose (doc section) | Depends on |
| --- | --- | --- |
| `__init__.py` | Package overview and the pipeline order | — |
| `data/__init__.py` | Download, storage, price adjustment (§7.5, §4.3). Owns blockers G1, G2 | pandas |
| `data/db.py` | Connection from `DATABASE_URL`, `.env` loader, the migration runner (numbered .sql files recorded in `schema_migration`), and `rebuild_trading_day()`: the ONE definition of the calendar, called by every script that writes `bar_raw` | psycopg |
| `data/cafef.py` | Everything format-specific about CafeF's bulk files: BOM, AmiBroker headers that mean nothing in CC_/NN_, 3-letter filter, weekend rejection for the index; `index_bars(day, pattern)` reads the history file (`INDEX_FILE`) or the nightly one (`DAILY_INDEX_FILE`) | pandas |
| `data/checks.py` | The data-quality gate: 20 checks. Tick helpers: `_ticks`, `max_tick` (largest of any exchange), `floor_tick` (the dated exchange's own tick, the largest where undated), Python twins of `tick_sql`. The price-limit check (`price_limit_sql()`, shared with the tests) judges each move by the exchange IN FORCE (`exchanges.RESOLVE_JOIN_SQL`) and counts dated vs FLAGGED violations apart. Also: `calendar_matches_bar_raw`; the holiday checks via `holiday_list()`/`HOLIDAY_SESSIONS_SQL`; the factor>1 check with ONLY the seam-rescale exemption, `FACTOR_ABOVE_ONE_SQL`; `index_has_no_repeated_sessions`, `INDEX_REPEATED_SQL`; all shared with the tests), `fail` blocks promotion, `warn` is recorded. Includes the traded-value invariant, the key proof that G1 was done right | psycopg |
| `data/universe.py` | **The point-in-time universe, the ONE definition of "liquid".** `load_rows` (bar_raw + excluded flag, optional adjusted close, with warm-up sessions), `tradeable`, `panel` (sessions x symbols on the full calendar), `tradeable_panel`, `liquid_panel`, `liquid(conn, start)` (the research filter, per date), `liquid_on_latest`. Recomputed on demand, build-independent | pandas, pyyaml, `data.db` |
| `data/sectors.py` | **Sector membership (doc §5.4).** `sector_id` (ICB L2, with the ONE exception: steel L4 1757 split out of basic resources 1700), `load_labels` (all snapshots), `panel` (sessions x symbols: sector + `labels_current` = borrowed pre-snapshot label), `assign` (one symbol), `current_groups` (latest labels for the §7.1 fallback; must be noted as current labels), `fetch_vci` and `write_snapshot` (idempotent per day; shared by the script and the nightly) | pandas, numpy, vnstock |
| `data/exchanges.py` | **Dated exchange membership.** `kbs_rows` (KBS listing_date cache → open-ended spans; OTC/empty give none), `cafef_transfer_rows` (G4 Class A spans), `rebuild` (TRUNCATE + insert, like `rebuild_trading_day`), `load`, `resolve` (pandas: exchange + `exchange_unknown`; CafeF transfer spans first (longer wins), then KBS, never KBS on a backfill row (rule B), else the filed exchange borrowed), `CONTRADICTED_KBS_SQL` (rule A, applied by `rebuild`; `commit=False` for tests), `RESOLVE_JOIN_SQL` (the same in SQL, for the gate) | pandas, `data.db` |
| `data/reconcile.py` | **Real code.** Two-source reconciliation: `normalise`, `reconcile_column`, `reconcile`, `sample_by_year`, `missing_trading_days`, `write_report`, `ReconResult`. Tolerances `PRICE_TOLERANCE=0.5%`, `VOLUME_TOLERANCE=1%` with the reasoning in comments. Built for both the post-download sample check and the nightly all-stock check | pandas |
| `features/__init__.py` | Package docstring plus the registry exports; importing it registers every measure (volume, trend, market, breadth) | `data` |
| `features/base.py` | **The measure contract.** `Measure`, `REGISTRY`/`MARKET_REGISTRY`, `@measure`/`@market_measure` (market measures declare which `frame` they read: 'index' or 'breadth'), `compute()`, `compute_market()` (one frame or a dict of frames, outer-joined on trade_date), `SECTOR_REGISTRY`/`@sector_measure`/`compute_sector()` (per sector; values plus `flag__<name>`), the explicit sector JOIN in `compute()` (symbol → sector on each date → (trade_date, sector)), `FeatureSet` (with `flagged`), and `quarantine_flagged()`, the hard gate that blanks flagged values (takes a FeatureSet or plain names; used for sector values AND exchange-dependent fillability). Enforces the three guarantees centrally: no look-ahead, no window spans a gap or an excluded row, volume measures NaN on non-adjustable spans. NaN / 0 / no-column are three distinct states | pandas, pyyaml |
| `features/bars.py` | Loads one symbol's bars from the **current promoted build only**, with `gap_before` in SESSIONS (from `trading_day`) and an `excluded` flag from `excluded_window`. Reads ADJUSTED matched volume so a window spanning a split has a consistent share basis. `liquid_symbols()` = the liquid set on the latest session, delegated to `data.universe` (reporting only). Also carries RAW open/high/low/close and the resolved `exchange` / `exchange_unknown` (via `exchanges.RESOLVE_JOIN_SQL`) for the candle tick floor | pandas, `data.exchanges`, `data.universe` |
| `features/market.py` | Market regime from `index_bar` (doc §5.3): loader aligned to the trading calendar, `missing_sessions`, and four measures — index_above_ma_50, index_ma_50_slope, index_change_20d, index_drawdown_from_high. Computed once per run and joined by trade_date | pandas, `features.base` |
| `features/breadth.py` | Doc §5.3 breadth. `counts()` builds the breadth frame (advancers/decliners/unchanged/counted per session, over ALL tradeable stocks, on ADJUSTED close, only stocks that traded the previous session). `load()` loads it with 40 warm-up sessions. `count_ok` (the thin-day guard, shared with sector; optional `min_members`) and `guard_lookback`. Measures `breadth_advance_share` and `breadth_advance_share_10d`, blanked on thin days (a lost exchange file) | pandas, `data.universe`, `features.base` |
| `features/sector.py` | Doc §5.4. `SectorInput` (frame, labels, basis), `build_frame` (the OWN (trade_date, sector) frame: counted, median_return over ALL tradeable members on the adjusted close, labels_current), `load` (60 warm-up sessions). `sector_change_20d` (SECTOR_REGISTRY) and `stock_vs_sector_20d` (per-symbol, reads the joined sector value) | pandas, numpy, `data.sectors`, `data.universe`, `features.breadth` |
| `features/trend.py` | The ten doc §5.1-5.2 per-symbol measures: ma_20/50, their slopes, price_vs_ma_20/50, price_change_10d/20d, near_support, near_resistance. PRICE only, so they remain available on backfilled spans | pandas, `features.base` |
| `features/volume.py` | The seven doc §4.1 measures: rvol, sustained_volume, up_down_volume_ratio, price_volume_agreement, price_volume_divergence, traded_value, volume_dry_up. Matched volume only | pandas, `features.base` |
| `patterns/__init__.py` | Pattern rules as arithmetic on OHLCV (§3). Thresholds from `config/rules/features.yaml` | `features` |
| `patterns/two_candle.py` | **Tranche 2 (doc §3.2).** `bullish/bearish_engulfing`, `bullish/bearish_harami` (LONG vs the 20-session mean body BEFORE yesterday), `piercing_line`, `dark_cloud_cover`. Dated on today; lookback >= 1, so a pair across a gap is blank. A prior-body tick floor (`min_prior_body_ticks`); cross-day `REL_TOL` 1e-4 for adjustment rounding; implied colour clauses documented, not re-tested | numpy, pandas, `features.base`, `data.checks` |
| `patterns/candles.py` | **Tranche 1 (doc §3.1).** Anatomy numerics: body/upper/lower-to-range, `range_rel_20d` (vs the PREVIOUS 20 sessions), `open_gap`. Shapes (one flag each, P1): `hammer_shape`, `inverted_hammer_shape`, `doji`, `marubozu_green/red`, each with a RAW-range tick floor (`min_range_ticks`, `checks.floor_tick`). Registered in REGISTRY via `features/__init__` | numpy, pandas, `features.base`, `data.checks` |
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
| `src/vnstock_research/backtest/forward_returns.py` | **G3 implemented.** Settlement eras, `earliest_sell_offset`, `valid_horizons`, ceiling/floor detection, `limit_in_force(exchange, date)`, `fillability()` (limit, entry_at_ceiling, exit_at_floor per row, each FLAGGED where the exchange is not dated; `FILLABILITY` names for `quarantine_flagged`), gross→net with fees and sale tax | pyyaml, pandas, `features.base` |
| `scripts/nightly_update.py` | The nightly job: daily CafeF files, append, factors, `write_index` (G16), calendar, checks, promote; `refresh_labels` takes the ICB snapshot on EVERY run; a heartbeat row every run. Does NOT yet update negotiated volume or the symbol master (G18). Not scheduled | requests, pandas, `data.*` |
| `scripts/check_backfill_seams.py` | Measures and rescales the level mismatch where a backfilled span meets CafeF; refuses to rescale across long gaps; tags rescale factors `source='seam_rescale'` with a reason (G17) | pandas, `data.db` |
| `scripts/measure_fillability.py` | How often the ceiling/floor rules bite, whole market vs liquid | pyyaml, `data.checks` |
| `migrations/005_job_run.sql` | The `job_run` heartbeat table | — |
| `migrations/009_exchange_membership.sql` | `exchange_membership`: dated exchange spans (cafef_transfer, kbs_listing) | — |
| `scripts/fetch_listing_dates.py` | Resumable fetch of KBS `overview().listing_date` per symbol into `data/raw/kbs_listing/` (git-ignored cache) | vnstock, `data.db` |
| `migrations/008_factor_provenance.sql` | `adjustment_factor.reason`, source 'seam_rescale', and the retag of the existing rescale rows (G17) | — |
| `config/rules/holidays.yaml` | 121 dated weekday market holidays 2012–2026 (statutory + compensation + the 2025 swap), each verified in CafeF and vnstock. A MINIMUM list; extend yearly | — |
| `migrations/007_symbol_industry.sql` | `symbol_industry`: dated ICB snapshots (L2 + L4) | — |
| `scripts/snapshot_industry.py` | Manual run of the same snapshot the nightly takes (`data.sectors.write_snapshot`), plus the KBS rough cross-check and our coverage; `--dry-run` | pandas, vnstock, `data.sectors`, `data.db` |
| `migrations/006_index_bar_source.sql` | `index_bar.source` ('cafef'/'vnstock') so backfilled index sessions stay visible | — |
| `scripts/investigate_index_gaps.py` | READ-ONLY. For each calendar session with no index row: symbols per exchange vs neighbours, shifted/backfilled/zero-volume counts, adjacent index dates, and a PHANTOM / INDEX-GAP / UNCLEAR hint (`classify`) | psycopg, `data.db` |
| `scripts/backfill_index_gaps.py` | Fills lost VNINDEX sessions from vnstock (volume > 0, neighbours reconcile). `--stale` repairs CafeF stale copies (a row repeating a neighbour's OHLC) for both indices, only where VCI and KBS agree and ours is off VCI on OHLC. `source='vnstock'`; `--dry-run` | pandas, vnstock, `data.db`, `data.reconcile` |
| `tests/test_index_gap_diagnostic.py` | 5 tests of the hint logic: stray rows on a holiday → phantom; rows all date-shifted onto the date → phantom; normal session without index → index gap; the middle stays unclear; no neighbours is unclear, not a crash | — |
| `config/rules/features.yaml` | Which measures are on and with what parameters — switching one off is a config change, never a code change. Now also the tranche-1 pattern thresholds (P2) | — |
| `scripts/report_features.py` | Occurrence rates and distributions per measure (index, breadth and sector inputs supplied), the flagged share per flagged measure, plus the NaN share and why | pandas, `features` |
| `tests/_helpers.py` | The shared synthetic-symbol frame, so both feature suites test against the same fixture | — |
| `tests/test_features_market.py` | 8 tests for §5.3: the join, NaN on a symbol date the index lacks (never forward-filled), an index gap fatal to the window, a loud failure when a market measure is enabled with no market frame, and the fingerprint covering both registries | — |
| `tests/test_universe.py` | 11 tests, one per universe rule: zero volume, date-shifted, excluded, delisted membership, 40/60 sessions, average over traded days, value floor, sessions not calendar days, tradeable on D, a short history is not judged, no look-ahead | — |
| `tests/test_breadth.py` | 13 tests: adjusted-close direction (ex-dividend), counting, resumption after suspension and zero-volume placeholders not counted, all-tradeable not liquid-only, the share arithmetic, thin-day blanking (daily and 10d), declared lookback covers every row read, no look-ahead, an index gap does not blank breadth, a missing breadth frame raises, the join | — |
| `tests/test_exchanges.py` | 12 tests: rule B (backfill never dated by KBS); the longer span wins; plus listing before history → no flag; before listing → unknown + borrowed; Class A spans date the earlier exchange; trading spans outrank KBS; no evidence → unknown; only listed exchanges with dates become spans; limit in force; fillability uses the given exchange; every result on an unknown exchange flagged; quarantine blanks them | — |
| `tests/test_two_candle.py` | 54 test cases, one per rule: each pattern fires; each clause (colour where not implied, open/close bounds, inside bounds, body ratio, LONG, the baseline before yesterday) fails alone; the prior-body floor; the rounding-nudged tie; the gap, excluded-yesterday and no-look-ahead rules for all six | — |
| `tests/test_candles.py` | 30 tests, one per candle rule: anatomy ratios, NaN on a flat bar / flat baseline, range_rel vs previous sessions only, gap blanking, no look-ahead; per shape each clause (wicks, body position, colour, body share) and the tick floor (raw range, own tick when dated, largest when undated, the 1-tick degenerate hammer); excluded → NaN; a single candle is still judged after a gap | — |
| `tests/test_nightly.py` | The nightly index step (G16) with a daily-file fixture, idempotent; the snapshot is idempotent per day; `main()` snapshots even with no new session (a no-commit connection, nothing persisted) | — |
| `tests/test_holidays.py` | The holiday file itself: weekdays only, filed under the right year, no duplicates, anchors of each kind present | — |
| `tests/test_sector.py` | 22 tests, one per sector rule: the steel exception only, snapshot as-of resolution, pooling on latest labels, median not mean, adjusted close, all tradeable members, resumption not counted, frame flags, compounding, thin sector-day (floor and drop), declared lookback, no look-ahead, the join by date, stock minus sector, the stock's own window guard, matching windows, the loud failure, per-measure flags, a straddling window still flagged, own borrowed label flagged, the quarantine gate, basis in the fingerprint | — |
| `tests/test_features_trend.py` | 11 tests for §5.1-5.2, including that trend measures STILL compute on a non-adjustable-volume span (the complement of the volume guard) and that support does not count an unconfirmed pivot | — |
| `tests/test_features_volume.py` | 16 tests: the arithmetic, and failing-without-the-guard tests for both contracts (gap→NaN, non-adjustable volume→NaN), NaN vs 0 vs disabled, and a truncation-based look-ahead test | — |
| `config/rules/costs.yaml` | Broker fee (provisional) and the 0.1% sale tax | — |
| `config/rules/market_rules.yaml` | Price limits **with the date each took effect** and tick sizes by price band; settlement cycle. Used by the price-limit check | — |
| `scripts/analyse_missed_actions.py` | For beyond-limit moves in the liquid universe, compares our adjusted series against vnstock's to tell "CafeF missed a corporate action" from "the move was real" | pandas, vnstock, `data.checks` |
| `tests/test_data_integrity.py` | Live-database checks, skipped when no DB: `date_shifted` really is written, no weekend bars survive, the price-limit SQL uses the rule in force, the calendar matches `bar_raw` (failed with 7,352 drifted exchange-days before the 2026-09-23 fix), the latest liquid set all traded that session, the latest industry snapshot labels ≥ 99% of the symbols that traded that session, no unexplained factor > 1 (and the exemption covers only tagged rescales on backfills), no session or bar on a listed holiday (plus an injected one is caught), no repeated index session since 2012, the known exchange cases (DPG, ACB, SHB, VNM, ACG, MHL), the Python and SQL resolvers agree, the WHOLE transfer set (no backfill dated, nothing before a KBS move dated with the current exchange, Class A rows dated as filed except the 3 stray rows), rule A in a rolled-back rebuild, flagged days land in the gate's flagged count, the gate judges by the dated exchange not the filed one, and real DPG fillability is quarantined before 2018-05-22 | psycopg |
| `config/rules/universe.yaml` | Liquidity floor, 60-SESSION window and 40-day minimum (read by `data/universe.py`), research start date, and `exclude_date_shifted` | — |
| `scripts/count_exchange_transfers.py` | Counts symbols affected by exchange transfers (G4): class A from CafeF alone, class B by asking vnstock for the window before CafeF's first date | pandas, vnstock |
| `tests/test_db.py` | Schema checks that need no server: migrations ordered, 3-letter constraint present, negotiated volume cannot be faked with a zero row | — |
| `scripts/probe_matched_vs_deal.py` | **G12 test.** Fetches CafeF's per-stock history endpoint (which publishes matched and negotiated separately), finds the largest-deal stock-days, and compares bulk volume against matched-only vs matched+deal. Also identifies `NN_<High>`/`NN_<Low>` as matched/negotiated and reports their coverage by year | requests, pandas |
| `scripts/probe_free_sources.py` | **Phase 3 probe.** Parses the CafeF download page for the newest complete date, downloads and unzips the five "Upto" files (cached), reports columns/coverage/delisted candidates/adjustment factors/missing sessions, decodes the CC_ and NN_ columns by value comparison, fetches vnstock in 4-year chunks, and reconciles both CafeF variants against it | requests, pandas, vnstock, `data.reconcile` |
| `data/raw/.gitignore` | Keeps the folder in git while ignoring its contents |
| `data/processed/.gitignore` | Same, for derived data |
| `scripts/.gitkeep` | Placeholder from Phase 2 |
| `data/reports/` | Git-ignored probe and reconciliation reports |
| `notebooks/.gitkeep` | Placeholder for exploration notebooks |
