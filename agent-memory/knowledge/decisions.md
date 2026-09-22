# Decisions

Format: Date | Decision | Reason | Rejected alternatives

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 (from doc) | Research tool, not prediction/auto-trading | Claims about measured history are checkable; also keeps clear of VN investment-advisory licensing since Ben is the only user | advisory product, auto-trading bot |
| 2026-09-22 (from doc) | **Rules-based** pattern detection in deterministic code | Exact, repeatable, free, explainable to the broker friend | vision model on chart images (a blurrier copy of data we already have exactly); ML training (memorises noise, cannot explain itself) — ML reconsidered later only to *rank* rule signals |
| 2026-09-22 (from doc) | History window **2012 → now**, daily/weekly/monthly | Broker friend studied from ~2010; 2012 skips the most distorted post-crisis years | 2010 start; shorter 5-year window |
| 2026-09-22 (from doc) | **EOD daily data first**; real-time streaming layer deferred | A 3–5 day horizon does not need intraday; minute data is ~200× larger | building the streaming pipeline first |
| 2026-09-22 (from doc §11.5) | **No message broker**; go direct, Redis pub/sub as a seam later | Avoids infrastructure the current scope does not need | Kafka/RabbitMQ from the v0.1 brief |
| 2026-09-22 (from doc) | Stack: SSI FastConnect → PostgreSQL + TimescaleDB, ~$6/month hosting, Telegram + web report | Carried over from the v0.1 platform brief as the data foundation | other data vendors (kept as backup if SSI history is short) |
| 2026-09-22 (from doc §4.3) | Money flow uses **matched volume only** | Negotiated block deals are not market demand and would fake accumulation | using total reported volume |
| 2026-09-22 (from doc §7.1) | Per-stock statistics with **stock → group → market** fallback | Most patterns fire only a few dozen times per stock in 15 years | global statistics only |
| 2026-09-22 (from doc §8.2) | Discover / validate / untouched-holdout split + walk-forward + paper trading before any real money | Tens of thousands of combinations guarantee lucky-looking results | single backtest over all history |
| 2026-09-22 (from doc §3.5) | Pattern thresholds fixed at textbook values first, stored as **config not code** | Choosing thresholds that look best on history is the classic self-deception | tuning parameters during discovery |
| 2026-09-22 (from doc §7.3) | "No recommendation today" is a valid output | A tool forced to pick daily will invent bad picks | always produce a top-ranked stock |
| 2026-09-22 (from doc §9.2) | Build the **deterministic pipeline first**, add agents only where judgement is needed | Most of the pipeline is a fixed sequence; agents earn their place at news, conflict and Q&A | multi-agent framework from day one |
| 2026-09-22 (session 01) | Phase 3 probes SSI **before** any schema design | Docs and real payloads often differ; a schema built on assumed field names would have to be rebuilt | designing the schema from the doc's §7.5 field list |

Related: [[architecture]] [[validation]] [[open-questions]]

## Phase 2 — tooling (session 01, run 2)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | Ruff as both linter and formatter | One tool, one config, no disagreement between formatters | black + isort + flake8 |
| 2026-09-22 | Runtime `dependencies = []` in Phase 2 | Add a package in the phase that needs it, so nothing unused reaches the lock file | pre-adding requests / pandas / psycopg |
| 2026-09-22 | `hatchling` build backend, `src/` layout | Default for uv; `src/` stops tests accidentally importing the source folder instead of the installed package | flat layout, setuptools |
| 2026-09-22 | pytest `pythonpath = ["src"]` | Tests run without an editable install step | `uv pip install -e .` |
| 2026-09-22 | `timescale/timescaledb:latest-pg16` | Timescale on a current Postgres; hypertables suit ~5M candles + a nightly one-day append | plain postgres image, Timescale Cloud |
| 2026-09-22 | Named Docker volume for DB data | `docker compose down` then keeps data; only `down -v` deletes it | bind mount into the repo (would land in git and in backups) |
| 2026-09-22 | Local DB credentials as defaults in `.env` / compose | They are local-only dev values, but keeping them in `.env` means changing a port or password needs no edit to `docker-compose.yml` | hard-coding them in the compose file |
| 2026-09-22 | `config/rules/patterns.yaml` seeded with provisional textbook values | Doc §3.5: thresholds are choices and must be visible in one reviewable file, fixed before testing | leaving the folder empty; inlining thresholds in detection functions |
| 2026-09-22 | `.python-version` pinning 3.12 | `requires-python = ">=3.12"` alone let uv pick 3.13; Ben specified 3.12, and the project should not silently change interpreter | relying on requires-python only; capping at `<3.13` in pyproject |

## Data source change (session 02, run 1)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **SSI FastConnect paused; CafeF primary, vnstock reference** | SSI registration costs money and nothing is paid for until the system proves effective. CafeF publishes full-history bulk files for all three exchanges, in both adjusted and unadjusted form, with no account and no rate limit; vnstock's free community tier gives an independent read of the same market for cross-checking | **Paid SSI FastConnect** (revisit once the system is proven — the endpoint notes are kept, not deleted); a single free source with nothing to check it against |
| 2026-09-22 | **Every dataset is reconciled against a second source before use** (now a non-negotiable principle in CLAUDE.md) | Agreement between two sources does not prove either is true — both derive from exchange data — but it catches download, parsing, missing-day and adjustment errors, which are the realistic failure modes | trusting one source; spot-checking by eye |
| 2026-09-22 | **Both CafeF adjusted and unadjusted files are downloaded** | Their ratio per day *is* the corporate-action factor, which is what blocker G1 needs to adjust volume as well as price | downloading only the adjusted file |

## Ben's decisions on the Phase 3 report (session 02, run 2)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **Store everything from 2000; the research window stays 2012 → now** | CafeF gives HSX from 2000-07-28 at no extra cost, and storage is trivial. Keeping the raw years means the window can be widened later without a re-download, while the 2012 start still skips the most distorted post-crisis years | downloading only 2012+ (throws away history that is free today and expensive to recover later); moving the research window back to 2000 |
| 2026-09-22 | **CafeF is canonical for price adjustment** (blocker G15 decided) | Its adjusted/unadjusted pair is the only thing that yields the per-day corporate-action factor, which blocker G1 needs to adjust volume as well as price. A second policy would mean two incompatible price series | vnstock/VCI as canonical; blending the two |
| 2026-09-22 | The VNM ÷ vnstock 1.65% gap is recorded as a **policy difference, not an error** | Both series are internally consistent; they encode different answers to "is this event adjusted for". `reconcile.py` already distinguishes a constant ratio from scattered noise via `median_ratio` | flagging VNM as corrupt and excluding it |
| 2026-09-22 | **Foreign flow is excluded from every signal** until a live source is confirmed (blocker G13 decided) | CafeF's NN_ columns have been all-zero since January 2025. A feature that exists 2015–2024 and not today would backtest well and read zeros in the live scan — the worst possible failure shape | using foreign flow for the historical years only; using it and hoping the feed returns |
| 2026-09-22 | Foreign flow recorded as a **later layer**, consistent with doc §4.4 | It was already "a candidate signal to test once the core is working"; the dead feed just settles the timing | — |
| 2026-09-22 | **Download plan recommendations 1–6 accepted**: CafeF bulk nightly (both variants, raw zips kept); filter to 3-letter tickers; calendar from stock rows not the index; compute our own adjustment factors and apply the inverse to volume; vnstock backfill for exchange transfers; scheduled reconciliation | Each addresses a confirmed defect rather than a hypothetical one | — |
| 2026-09-22 | **Register the free vnstock API key before the G4 backfill** | Unregistered access is 20 req/min and aborts on exceeding it; the free key raises it to 60. Ben adds `VNSTOCK_API_KEY` to `.env` | running the backfill unregistered with long sleeps |
| 2026-09-22 | **G12 is tested before it is decided**: check whether CafeF bulk volume is already matched-only, using stock-days with large negotiated deals | If the bulk volume already excludes block trades, the principle in [[money-flow]] §4.3 is satisfied by the primary source and no scraper is needed. Testing costs an afternoon; building the wrong thing costs weeks | choosing between scrape / accept / pay before knowing what the number already is |
