# Decisions

Format: Date | Decision | Reason | Rejected alternatives

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 (from doc) | Research tool, not prediction/auto-trading | Claims about measured history are checkable; also keeps clear of VN investment-advisory licensing since Ben is the only user | advisory product, auto-trading bot |
| 2026-09-22 (from doc) | **Rules-based** pattern detection in deterministic code | Exact, repeatable, free, explainable to the broker friend | vision model on chart images (a blurrier copy of data we already have exactly); ML training (memorises noise, cannot explain itself) — ML reconsidered later only to *rank* rule signals |
| 2026-09-22 (from doc) | History window **2012 → now**, daily/weekly/monthly | Broker friend studied from ~2010; 2012 skips the most distorted post-crisis years | 2010 start; shorter 5-year window |
| 2026-09-22 (from doc) | **EOD daily data first**; real-time streaming layer deferred | A 3–5 day horizon does not need intraday; minute data is ~200× larger | building the streaming pipeline first |
| 2026-09-22 (from doc §11.5) | **No message broker**; go direct, Redis pub/sub as a seam later | Avoids infrastructure the current scope does not need | Kafka/RabbitMQ from the v0.1 brief |
| ~~2026-09-22 (from doc)~~ **SUPERSEDED** → see "SSI paused; CafeF primary" below | Stack: SSI FastConnect → PostgreSQL + TimescaleDB, ~$6/month hosting, Telegram + web report | Carried over from the v0.1 platform brief as the data foundation | other data vendors (kept as backup if SSI history is short) |
| 2026-09-22 (from doc §4.3) | Money flow uses **matched volume only** | Negotiated block deals are not market demand and would fake accumulation | using total reported volume |
| 2026-09-22 (from doc §7.1) | Per-stock statistics with **stock → group → market** fallback | Most patterns fire only a few dozen times per stock in 15 years | global statistics only |
| 2026-09-22 (from doc §8.2) | Discover / validate / untouched-holdout split + walk-forward + paper trading before any real money | Tens of thousands of combinations guarantee lucky-looking results | single backtest over all history |
| 2026-09-22 (from doc §3.5) | Pattern thresholds fixed at textbook values first, stored as **config not code** | Choosing thresholds that look best on history is the classic self-deception | tuning parameters during discovery |
| 2026-09-22 (from doc §7.3) | "No recommendation today" is a valid output | A tool forced to pick daily will invent bad picks | always produce a top-ranked stock |
| 2026-09-22 (from doc §9.2) | Build the **deterministic pipeline first**, add agents only where judgement is needed | Most of the pipeline is a fixed sequence; agents earn their place at news, conflict and Q&A | multi-agent framework from day one |
| ~~2026-09-22 (session 01)~~ **SUPERSEDED** → Phase 3 became the free-source probe; see "SSI paused; CafeF primary" below | Phase 3 probes SSI **before** any schema design | Docs and real payloads often differ; a schema built on assumed field names would have to be rebuilt | designing the schema from the doc's §7.5 field list |

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
| 2026-09-22 | **G12 closed: CafeF bulk volume is matched-only; use it directly** | Measured on 20 large-deal stock-days, 20/20 exact, with an 8× separation between the two candidate answers on the clearest day | building a per-stock scraper; accepting total volume with a caveat; paying for SSI |
| 2026-09-22 | **Negotiated volume comes from `NN_<Low>`, treated as "unknown" when the row is missing** | The series is exact where present but covers only 46% of HSX stock-days in 2024. Treating a missing row as zero would silently assert "no block trade" on days we know nothing about | assuming zero; discarding the series |

## Phase 4 data model (session 02, run 4)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **Data model APPROVED** as written in [[data-model]] | — | — |
| 2026-09-22 | `index_bar` table approved | Market regime (doc §5.3) and funnel step 3 need the VN-Index; there is nowhere else to put it | leaving the index to a later phase |
| 2026-09-22 | **Backfill transferred symbols with a flag.** Backfilled spans are usable for **price-based patterns and trend**; **volume-based signals are disabled on them** | vnstock returns adjusted prices only, so no factor can be derived for those spans and volume cannot be adjusted (G1). Losing the price history entirely would be worse — ACB would start in 2020 | not backfilling; backfilling silently and letting volume signals run on unadjustable volume |
| 2026-09-22 | Reconciliation: **liquid universe nightly + full market weekly**, with "liquid" a **config value** (minimum average matched traded value) | 1,600 symbols nightly is ~27 min of requests against a free service; the liquid names are the only ones that can be recommended anyway. Config, not hard-coded, because it is a threshold and thresholds are choices (doc §3.5) | all stocks every night; a hard-coded liquidity number |
| 2026-09-22 | **Every research result records the `build_id` it was measured on** | Adjusted prices change when a new corporate action appears. Without the build id, a number measured last week cannot be reproduced or even interpreted | storing results without provenance |

## Phase 4 build (session 02, run 4)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | Migrations are **numbered .sql files applied by a 60-line runner**, not an ORM or a migration framework | The SQL is the schema documentation and carries the "why" next to each constraint; a one-developer project gains nothing from models kept in sync with tables | Alembic, SQLAlchemy models |
| 2026-09-22 | `bar_adjusted.matched_volume` is **numeric(24,6)**, not (20,2) | Adjusted volume is raw ÷ factor; two decimals is fine for a million shares and off by 0.5% on a ten-share day, which broke the traded-value invariant on 479,511 rows | keeping 2dp and loosening the check instead — that would have hidden the one test that proves G1 is right |
| 2026-09-22 | The `factor > 1` check **blocks inside the research window only**, with a whole-history warning | Pre-2012 data is stored but never measured on. One symbol (GGG, 2010) has 120 such factors; blocking a build over data research never reads would train us to ignore the gate | blocking on the whole history; dropping the check |
| 2026-09-22 | **Weekend-dated bars are moved to the previous business day when that day is free for the symbol**, dropped on collision, and flagged in `bar_raw.date_shifted` | CafeF dated a whole HNX session one day late (Saturday 2023-08-26 = Friday's session, verified against vnstock). Dropping would lose real data for 214 symbols; repairing invisibly would be worse | dropping all weekend rows; repairing without a flag |
| 2026-09-22 | Reconciliation compares **adjusted close vs adjusted close, and raw volume vs raw volume** | vnstock adjusts price but not volume. Comparing our adjusted volume with theirs measures the factor, not agreement — it scored 1.92% before the fix and 98.74% after | comparing adjusted volume to vnstock volume |

## Session 02 run 5

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | CLAUDE.md honesty rule extended: **never claim a file was written, a test passed or a task was done unless it happened in this run**; say "not done yet". And **never modify `.env` without asking** — propose the change | Run 3 reported `data-model.md` as written when it was not, and run 4 edited `.env` without asking | — |
| 2026-09-22 | **Every date-shifted bar is verified against vnstock; unverifiable ones are deleted** | One worked example justified the repair; it did not justify 85 rows. 84 verified on exact volume match, 1 (BDT 2025-05-02) deleted because the reference has no session at the target date | trusting the repair on the strength of one example |
| 2026-09-22 | **Research excludes `date_shifted` bars by default** (`config/rules/universe.yaml`) | They are repaired data. Verified, but research should not silently depend on a bar whose date we corrected | including them once verified |
| 2026-09-22 | VNM/MBB/PNJ vs vnstock recorded as a **known policy difference, no further action** | CafeF is canonical; both series are internally consistent | investigating further; excluding the symbols |
| 2026-09-22 | **"Liquid universe" is defined in `config/rules/universe.yaml`** — avg matched traded value ≥ 1bn VND/day over 60 sessions (PROVISIONAL, pending G10) | Ben asked for a config value, not a hard-coded number. It is also the yardstick for how much a data-quality warning matters | a hard-coded threshold |

## Session 02 run 6

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **The liquid universe for research is POINT-IN-TIME**: computed as of each historical date from data available then, never today's list | Using today's liquid names to filter history is look-ahead bias of the worst kind ([[validation]] §8.1) — it silently selects the stocks that turned out to be successful. VIX was thinly traded in 2012 and liquid now; including its 2012 days because it is liquid *today* would flatter every statistic | a single current liquidity list applied to all history |
| 2026-09-22 | The 1bn VND/day threshold **stays provisional** pending G10 | Ben has not set his minimum liquidity yet, and [[validation]] requires parameters fixed before testing | fixing the number now |
| 2026-09-22 | CLAUDE.md gains: **every fix must be proven by a check that fails without it**, and **verify the edit applied — formatters can change the text you matched on** | Four patches silently failed to apply this session because `ruff format` had reflowed the text being matched, twice producing a wrong result I nearly reported | relying on careful editing |
| 2026-09-22 | CLAUDE.md principle: **no pattern window or forward-return window may span a gap in trading** | 108 liquid symbols have >20 missing sessions inside their listed range, mostly days they genuinely did not trade. A 5-day window spanning a 3-month hole measures a move over the wrong period | handling gaps ad hoc per pattern |
| 2026-09-22 | Price-limit check uses the **limit in force on that date plus one tick**, from `config/rules/market_rules.yaml` | HOSE widened 5%→7% and HNX 7%→10% on 2013-01-15, inside the research window; and at a 100 VND tick a 600 VND share moves 16.7% in one tick. Both produced phantom violations | today's limits with a flat 2% tolerance |
| 2026-09-22 | **Class A transfer gaps are excused from the missing-session count**, derived from `symbol_exchange` rather than stored | The days between leaving one venue and joining the next are a real non-trading period. Deriving it needs no table: the spans already say it | a `symbol_gap` table |

## Session 02 run 7

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **Never run `ruff format` during a session.** Lint with `ruff check` only; formatting happens once, in the pre-commit hook | Four patches silently failed to apply in one session because `ruff format` reflowed the exact text being matched, twice producing a wrong result that was nearly reported. The formatter is useful at the boundary and actively harmful mid-edit | formatting after every edit |
| 2026-09-22 | **Try to INFER a missed corporate action's factor before excluding the window** | A round stock-dividend ratio confirmed by a matching volume jump is strong evidence; repairing the factor recovers the whole history, while excluding throws away ~67 sessions per event | excluding every missed action outright |
| 2026-09-22 | Inferred factors are stored in `adjustment_factor` with `source='inferred'`; **`bar_raw` is never touched** | Raw stays the permanent record. An inferred factor is a derivation, and derivations are rebuildable and labelled | writing corrected prices into bar_raw |
| 2026-09-22 | The exclusion window is **longest feature lookback + longest forward window**, and the lookback floor is **60 sessions** | `config/rules/patterns.yaml` currently tops out at 20, but the doc's context measures (50-day average §5.1, 60-day support/resistance §5.2) are not in config yet. 60 is the honest floor until they are | ±6 days, which covers only the pattern itself |
| 2026-09-22 | **Backfill the 47 liquid Class B symbols only**; skip the 204 illiquid ones | The illiquid ones cannot be recommended, so their missing pre-transfer years cost nothing and would cost ~3 hours of a free service's rate limit | backfilling all 251 |

## Session 02 run 8

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | Tick sizes carry **effective dates**; HOSE cut 100/500/1,000 VND to 10/50/100 on **2016-09-12** (verified) | Before that a share under 50,000 VND moved in 100 VND steps, so at 600 VND one tick was 16.7 percent. A percentage limit check that ignores the regime in force reports phantom violations across the early years | one tick table for all history |
| 2026-09-22 | **First-day and resumption bands** (HOSE 20 / HNX 30 / UPCoM 40 percent, resumption after 25 sessions) are applied inside the price-limit check | A newly listed or resuming security is not violating a limit, it is under a different one. This removed 1,188 of the remaining violations | classifying them after the fact only |
| 2026-09-22 | Settlement history recorded as T+3 → T+2 from 2016-01-01 but **marked unverified** | Ben's belief matches the common account and Circular 203/2015/TT-BTC, but I could not confirm the effective date from a primary source this session. It must be checked before any backtest depends on it | writing the date as fact |
| 2026-09-22 | `CURRENT_STATE.md` is **rewritten from scratch every run**, with every number re-checked against the database or git | It had been patched incrementally and had begun to drift from the data | appending and patching |

## Session 02 run 9 — G3 approved, seams, nightly job

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **Settlement has three eras, all verified** (Ben's sources): T+3 to 2016-01-03; T+2 settling 16:30 from 2016-01-04, so earliest sell is still **T+3**; T+2 settling before 13:00 from 2022-08-25, earliest sell **T+2 afternoon** | The middle era is the trap: "T+2 settlement" from 2016 did not make shares sellable on T+2, because the money landed after the close. A backtest using T+2 for 2016-2022 would book exits it could not have made | treating 2016 as the T+2 switch |
| 2026-09-22 | **G3 APPROVED.** signal at close of t; entry at open of t+1; `return_k = close(t+1+k) / open(t+1) - 1`, with k ≥ the earliest-sell offset for the era of the ENTRY date | Entry at the open means the signal day's close is never an entry price, closing the look-ahead trap (doc §8.1). k=3 and k=5 are valid in every era | measuring from the signal day's close |
| 2026-09-22 | **Reject entries where t+1 opens at the ceiling** | Nobody fills a buy at the ceiling — there are no sellers. Measured cost: 0.13% of liquid bars | flagging and keeping them |
| 2026-09-22 | **Defer an exit that closes at the floor** to the next session that does not, capped at 5 sessions, flagged | A stretched holding period is a real cost and must be visible. Measured: 0.34% of liquid bars, and only 3 runs market-wide exceed the cap | forcing the exit at an unfillable price |
| 2026-09-22 | **Store gross AND net returns**; fees and the 0.1% sale tax in `config/rules/costs.yaml`; broker fee **provisional at 0.15%/side** until Ben confirms | Round trip is 0.40%, which is a meaningful slice of a realistic edge (doc §6.3). The sale tax is charged on the sale whether or not the trade profited, so it cannot be netted off a gain | a single net figure; hard-coded costs |
| 2026-09-22 | **Suspension–resumption:** a first bar after a long gap starts a new span and its factors are **re-derived, not diffed** | Otherwise a resuming symbol's whole series shifts at once and reads as a mass restatement | diffing factors for every symbol uniformly |
| 2026-09-22 | **Backfill seams are rescaled only when the two spans meet across ≤ 20 days**; longer gaps are reported and left alone | Across a long gap the ratio is mostly real price movement. VHM's spans meet across 308 days with a raw ratio of 3.82 — that is the stock tripling, not a level mismatch. Rescaling by it would have erased a real move | rescaling every seam by its raw ratio |
| 2026-09-22 | TDP and VHM spans written to `excluded_window` as **unreconciled backfill seams** | Their vnstock level is not comparable to CafeF's and cannot be fixed without an overlap | leaving them usable |
| 2026-09-22 | **The nightly job writes a heartbeat row every run**, with `no_new_data` and `stale_source` as distinct statuses | The failure that matters is silence: a dead job looks exactly like a job with nothing to do, and the scan then reports on stale data | logging only failures |

## Session 03 — features slice 1 (doc §4.1)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **All seven doc §4.1 measures built in this slice**, none deferred | The table in doc §4.1 lists exactly seven; price–volume agreement and divergence turned out to need only an N-day change in close and in average volume, not the trend module, so there was no reason to defer them | deferring agreement/divergence to the trend slice |
| 2026-09-22 | **Measures compute on demand; nothing materialised yet** | The measure set is not stable, and a materialised table costs either a migration per measure or a JSONB blob. Materialise when the backtest starts making repeated passes | a `feature_daily` table now |
| 2026-09-22 | **A measure declares its `lookback` and its `needs`** | Declaring the lookback is what lets the no-gap rule be enforced centrally without reading each measure's body; declaring `needs` is what makes the volume guard automatic rather than remembered | inferring the window from the code; per-measure guards |
| 2026-09-22 | **NaN, 0 and "no column" are three distinct states** | NaN = no signal / excluded / unknowable; 0 = a real measured zero; a disabled measure produces no column at all. Collapsing any pair would let a consumer read "we cannot tell" as "nothing happened" | filling NaN with 0 or False |
| 2026-09-22 | **Boolean measures are stored as float64** | So an unevaluable boolean stays NaN instead of collapsing to False, which would read as "no signal here" when the truth is "we cannot tell" | a bool dtype |
| 2026-09-22 | **RVOL divides by the previous N sessions, excluding today** | Including today lets a huge day inflate its own denominator and understates exactly the spikes the measure exists to find | a window including today |
| 2026-09-22 | `bars.py` reads the **current promoted good build only** | `bar_adjusted` is build-scoped and a build is one consistent adjustment policy; reading across builds would splice two policies into one series | reading whatever rows exist |

## Session 03 — features slice 2 (doc §5.1-5.2, per-symbol)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **Booleans stay NaN when an INPUT is undefined**, via `base.boolean_from` | `(a >= x) & (b >= y)` yields False when b is NaN, because a comparison against NaN is False. That reads as "evaluated and did not hold" when the truth is "could not evaluate" — the same collapse the float64 storage prevents, one level lower | letting the comparison decide |
| 2026-09-22 | **Lookbacks tightened to what each measure truly reaches** | They were over-declared by 1–2 rows, which only inflated the NaN rate near gaps, but an over-declared window is a quiet inaccuracy in the one number the gap guard depends on. NaN share fell ~0.5pt across the volume measures | leaving them safe-but-wrong |
| 2026-09-22 | **A pivot within `pivot_k` rows of today is not counted** | Confirming a pivot needs rows on both sides; one whose confirmation window is still open would be look-ahead. Proven by removal — the test fails without the filter | using every pivot in the window |
| 2026-09-22 | Trend measures declare `needs=("close",)` and so remain available on **backfilled spans** | This is the price-yes / volume-no decision working in both directions, driven by the declared `needs` rather than by anyone remembering it. Tested explicitly | applying the volume guard to everything |
| 2026-09-22 | `tests/` is now a package with a shared `_helpers.frame` | Both feature suites must test against the SAME synthetic frame; if they drifted, a guard could pass in one suite and be silently untested in the other | duplicating the helper |

## Session 03 — features slice 3 (doc §5.3 market regime)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 | **`near_support`/`near_resistance` lookback is `lookback_days - 1 + pivot_k`** | The pivot at the window's left edge is itself confirmed by reading `pivot_k` rows further back, which sat OUTSIDE the guarded window. A gap in that margin escaped `_window_ok`, so shipped code could fire on a level confirmed across a suspension — a no-gap-rule violation. Found by Ben; proven by a test that fails with the old declaration | the under-declared `lookback_days - 1` |
| 2026-09-22 | **Separate `MARKET_REGISTRY` and `@market_measure`** | Market measures read one calendar-aligned frame, not one symbol's bars, and are computed once per run rather than per symbol. One registry would need a discriminated union at every call site | a `scope` field on a single registry |
| 2026-09-22 | **A gap in `index_bar` is a DATA DEFECT**: fatal to the window AND reported by the data-quality gate | The index trades every session the market is open, so a missing row means our data is wrong, not that the market paused. Routing around a defect without reporting it is how it becomes permanent. Currently 5 such sessions since 2012 | treating it like a symbol suspension |
| 2026-09-22 | **Market measures are NaN on a symbol date the index lacks — never forward-filled** | Carrying yesterday's regime forward asserts a market state we have no index for | forward-fill |
| 2026-09-22 | **Enabling a market measure with no market frame raises** | Silently dropping it would leave a hole exactly where the regime context should be, and nothing downstream could tell | quietly skipping |
| 2026-09-22 | The FeatureSet fingerprint covers **both registries** | Otherwise two feature sets differing only in a regime parameter would be indistinguishable in any stored output | per-symbol measures only |
| 2026-09-22 | **Breadth deferred to its own slice** | It needs the point-in-time universe, which also discharges part of G11 and implements the PIT liquid-universe decision — too foundational to ride along | building breadth here |

## Session 2026-09-23-03 — the 5 missing VNINDEX sessions (Task 1)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **2025-05-02 is a PHANTOM calendar date; fixed by re-deriving `trading_day` from `bar_raw`** | `trading_day` listed it (UPCOM, 1 symbol) but `bar_raw` had ZERO rows that day: `verify_date_shifts.py` deleted the one shifted bar and never re-derived the calendar. 2025-05-02 was a public holiday (the 30/4–1/5 break was extended). The phantom inflated `gap_before` by 1 for 1,358 symbols; 611 went 1→0 | deleting the one row by hand (leaves the root cause); leaving it |
| 2026-09-23 | **`db.rebuild_trading_day()` is the one definition of the calendar; every script that writes `bar_raw` calls it; gate check `calendar_matches_bar_raw` is `fail`** | The calendar is DERIVED data. Two scripts edited `bar_raw` without re-deriving it and 7,352 exchange-days had drifted (mostly counts). A blocking check makes any future forgetful script visible before promotion | patching each script without a gate; a `warn` severity |
| 2026-09-23 | **2018-01-23/24 are a real HOSE halt, NOT a defect; left as is** | vnstock shows VNINDEX and VNM at volume 0 with a flat close both days; CafeF has no HOSE stock rows. HNX and UPCoM traded. The 50 index dates after them stay NaN for regime windows, which is correct under the no-gap rule. The gate keeps reporting 2 missing sessions, both explained | inserting placeholder index rows; dropping the dates from the calendar (HNX/UPCoM did trade) |
| 2026-09-23 | **2024-05-17 and 2026-07-02 were INDEX-GAPs; VNINDEX backfilled from vnstock with `index_bar.source='vnstock'` (migration 006)** | Normal sessions (108% / 99% of neighbour symbol counts), vnstock has them with real volume, and vnstock matches CafeF's close on all 10 neighbouring sessions (max diff 0.000% / 0.027%, tolerance 0.5%). Regime windows touching an index gap fell from 150 dates to 50 | leaving them NaN (costs ~100 sessions of regime data for every symbol); inserting without a provenance column (index VOLUME differs by 6–9% between sources) |
| 2026-09-23 | Backfill guards: **vnstock volume > 0** and **neighbours reconcile** | Volume 0 is how vnstock shows a halt; the guard is what kept 2018-01-23/24 from being filled. A source that disagrees next door is not trusted for the day between | a hard-coded date list |

## Session 2026-09-23-03 run 3 — PIT universe + breadth slice (doc §5.3), branch `features/breadth-pit-build`

Locked by Ben before the build:

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **The universe is recomputed on demand from `bar_raw`**, never stored; build-independent | A stored copy is derived data that drifts (the `trading_day` phantom) | a cached `universe_day` table |
| 2026-09-23 | **Tradeable on D** = bar_raw row, matched_volume > 0, not date_shifted, not in an excluded window. Delisted stocks count on the days they traded (G11 membership). Whole market only | Rows are the only first-hand evidence of trading; exchange labels are not historical | listed/suspended status from `symbol_exchange`; per-exchange universes |
| 2026-09-23 | **Liquid on D** = tradeable on D + traded ≥ 40 of the last 60 SESSIONS (D included) + average traded value on traded days ≥ the universe.yaml floor. Reads bar_raw only | Sessions, so a Tet week is not "missing". bar_raw, because `bar_adjusted` on seam-rescaled spans can sit above the real price (G17) | calendar-day windows; `bar_adjusted` values |
| 2026-09-23 | **"Liquid" has ONE canonical definition: `data/universe.py`.** `liquid_symbols()` = the liquid set on the latest session (reporting). Research filters by the liquid set on EACH historical date (`universe.liquid`). The five one-off scripts (`measure_fillability`, `analyse_missed_actions`, `investigate_warnings`, `backfill_transfers`, `repair_missed_actions`) PREDATE it and are left as run | One definition for research and reporting; the old scripts' recorded results stay reproducible | rewriting the one-off scripts |
| 2026-09-23 | **Breadth is over ALL TRADEABLE stocks, not the liquid universe** | It must capture the broad participation the cap-weighted index misses | liquid-only breadth |
| 2026-09-23 | Breadth direction on the **ADJUSTED close**; a stock counts only if it traded the **immediately preceding session** | Ex-dividend days are not declines (4,830 stock-days since 2012 would have been fake declines); a stock back from suspension would compare against a stale close | raw close; comparing against the last available close |
| 2026-09-23 | Two market measures, `breadth_advance_share` and `breadth_advance_share_10d`, in `MARKET_REGISTRY`; breadth in its **own date-aligned frame**, blanked on thin days | An index gap must not blank breadth, and vice versa | breadth columns in the index frame |

Implementation choices this run:

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | Market measures declare `frame` ('index' default, 'breadth'); `compute_market` takes one frame or a dict and outer-joins the per-frame results on trade_date. A missing declared frame raises | Smallest change that keeps each frame under its own window guard | a second compute function per frame |
| 2026-09-23 | **Thin-day guard: counted < 0.80 × median of the previous 20 sessions' counts → NaN.** Set from the measured distribution BEFORE any breadth statistic: median 1.00, 5th pct 0.93, 2nd pct 0.85; every whole-exchange loss ≤ 0.73; most lost HNX files 0.76–0.83. Blanks 54 of 3,689 sessions | It is a data-defect guard, not a research parameter. Known ceiling: partial losses at 0.80–0.90 pass | 0.90 (122 blanks, catches normal variation); 0.70 (misses most HNX losses) |
| 2026-09-23 | The guard's parameters are **measure parameters** (in the FeatureSet fingerprint), and the declared lookback covers them: `count_median_sessions + 1` (+ `window_days − 1` for 10d) | CLAUDE.md: a declared lookback must cover every row a measure reads, helpers included | frame-level guard settings outside the fingerprint |
| 2026-09-23 | Unchanged = |Δ adjusted close| ≤ 1e-9; advance share = adv / (adv + dec), unchanged left out | Adjusted closes are stored to 6 dp, so the same raw close gives an identical adjusted close; thin names print unchanged constantly and would pull every day toward 0.5 | a tick-based tolerance; unchanged in the denominator |
| 2026-09-23 | The optional liquid-universe breadth measure is **NOT built** | Ben made all-tradeable primary; YAGNI until a study needs it | building it now |
