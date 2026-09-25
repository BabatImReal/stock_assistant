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

## Session 2026-09-23-03 run 5 — sector slice (doc §5.4), branch `features/sector-build`

Locked by Ben (answers to S1–S6):

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **Source: vnstock VCI ICB.** KBS is only a rough cross-check (printed by `scripts/snapshot_industry.py`), never a source | Only free source; covers 99.0% of liquid stock-days since 2012. KBS uses a different taxonomy | blocking on a paid dated source |
| 2026-09-23 | **Sector = ICB level 2, with steel (L4 1757) split out of basic resources (L2 1700). That is the ONLY manual exception**; the rest of basic resources stays 1700; no other group may be hand-adjusted | The doc names steel as a group; at L2 steel is only 8 of 17 basic-resources stocks | L3 or L4 everywhere; any other hand-built groups |
| 2026-09-23 | **Sector figures over ALL TRADEABLE members; equal-weighted MEDIAN daily return on the adjusted close; a member counts only if it also traded the session before** | Same reasoning as breadth; no share counts for cap weights; a median resists one thin stock | liquid members only; mean; cap-weighting |
| 2026-09-23 | **Current labels are applied to history, but the flag is a HARD GATE.** Every sector value that read a pre-snapshot (borrowed) label is flagged (a `flag__<measure>` column per measure). `FeatureSet.flagged` lists each flagged measure. The label basis is in each measure's params, so it is in the fingerprint | ICB is published current-only: a borrowed label is look-ahead (a company classified by what it became) | silently applying current labels; no history at all |
| 2026-09-23 | **Sector-conditioned edge statistics are EXPLORATORY until dated membership accrues. The backtest MUST pass results through `features.base.quarantine_flagged` (it blanks every flagged value) before anything is called validated; flagged sector features are never folded into validated results** | Look-ahead in the label would flatter exactly the "trade with the sector" edge the doc suggests | reporting flagged and dated results together |
| 2026-09-23 | **Dated snapshots start now**: migration 007 `symbol_industry` (symbol, snapshot_date, source, ICB L2 + L4 codes and names); `scripts/snapshot_industry.py` writes one per run date. First snapshot 2026-09-23: 1,722 symbols | The only way to get point-in-time membership is to record it ourselves | not storing snapshots |
| 2026-09-23 | **The sector aggregate is its OWN frame keyed by (trade_date, sector)**, computed once per run, in a third registry `SECTOR_REGISTRY`. Per-symbol values join symbol → its sector on that date → (trade_date, sector) in `compute()` | Its key differs from the one-row-per-date market frame; a separate registry means a measure cannot land on the wrong frame silently | `frame="sector"` in `MARKET_REGISTRY` |
| 2026-09-23 | **The §7.1 small-sample fallback (stock → sector → market) pools by this grouping and MAY use current labels (`data.sectors.current_groups`), but every pooled statistic must say it pooled on current labels** | Pooling needs enough members now; the label caveat must travel with the number | pooling only on dated labels |

Implementation choices this run:

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | Measures: **`sector_change_20d`** (compounded median return over 20 sessions) and **`stock_vs_sector_20d`** (the stock's 20-session change minus its sector's). `compute()` refuses different `window_days` for the two | These are the two Ben named; comparing a stock and its sector over different sessions would be meaningless | also building `sector_advance_share_10d` (YAGNI) |
| 2026-09-23 | **Thin sector-day guard: `min_members` 5 plus the breadth drop rule (0.80 × the trailing 20-session median)**, set from the measured counts before any sector statistic. The guard is shared with breadth (`breadth.count_ok`). Blanks 8.7% of sector-days (banks 1.2%, securities 1.5%, real estate 1.5%, steel 2.5%; Telecom 59%, Oil & Gas 36%) | A median of fewer than five stocks is one company's news | min 3 (6.0% blanked, but a 3-stock median) |
| 2026-09-23 | A value is flagged if **any row in its declared lookback + today** read a borrowed label, OR the symbol's own label on that date is borrowed. A (date, sector) with nothing counted is **fail-safe flagged** | A 20-session change that straddles the first snapshot still rests partly on current labels | flagging on today's label only |
| 2026-09-23 | Membership resolution: a date uses the **latest snapshot on or before it**; before a symbol's first snapshot it borrows the earliest one (flagged). A symbol with no snapshot has no sector (NaN) | Point-in-time from the first snapshot on | the latest snapshot for every date |

## Session 2026-09-23-03 run 6 — nightly hardening / integrity, branch `features/nightly-hardening`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **G17 fixed: seam-rescale factors get provenance** (migration 008: `adjustment_factor.source = 'seam_rescale'` + a `reason` column; `check_backfill_seams.py` tags them from now on). The 27,518 existing rescale rows (33 symbols) were retagged by an unambiguous rule: a `vnstock` factor ≠ 1 exists only where the rescale multiplied it | The rescale shared the tag of the plain backfill factors (exactly 1), so the gate could not tell a rescale from a defect | exempting all 'vnstock' factors; dropping the check |
| 2026-09-23 | **The factor>1 check exempts ONLY `seam_rescale` factors sitting on a backfilled vnstock bar** (`checks.FACTOR_ABOVE_ONE_SQL`); everything else above 1 still fails; a visible `seam_rescale_factors_exempted` line reports the exemption | An exemption must not become a silent hole; a rolled-back test proves an untagged factor, or a tagged one on a CafeF bar, still fails | tag-only exemption |
| 2026-09-23 | **G16 fixed: the nightly writes the session's index rows** (`write_index`, daily file `CafeF.INDEX.<dd.mm.yyyy>.csv`) | Without it, every nightly session lacks VNINDEX and the regime is NaN on the scan day | — |
| 2026-09-23 | **The nightly takes the industry snapshot on EVERY run** (`refresh_labels`), even with no new session; idempotent per day; a failure is reported, never fatal | Dated sector labels accumulate only if every day is snapshotted; sector labels must not stop the price data | monthly; a separate job |
| 2026-09-23 | **Holiday list: `config/rules/holidays.yaml`, 121 dated weekday closures 2012–2026** (statutory days + the compensation day for a weekend holiday + the 2025-05-02 swap), every one verified closed in BOTH CafeF and vnstock (0 conflicts). Two BLOCKING checks: no session and no bar_raw row on a listed date | Tet and Hung Kings are lunar, so dates must be written per year. A MINIMUM list: decree-set extra Tet/bridge days and National Day's second day are not listed. Must be extended each year | computing lunar dates in code; listing unverified decree days |
| 2026-09-23 | **The 2026-07-31 index disagreement is CafeF stale copies**: the 07-31 row repeats 07-30's OHLC for both indices; HNX-INDEX 2023-05-08 carries 05-09's. Repaired from VCI (`backfill_index_gaps.py --stale`) only where VCI and KBS agree, ours differs from VCI on any of OHLC by > 0.5%, and neighbours reconcile. Warn check `index_has_no_repeated_sessions` added | Two independent feeds agree to 0.000%; which row of a repeated pair is wrong needs outside evidence; a close-only test would miss 2023-05-08 (close 0.49% off, open 1.5%) | trusting CafeF; a close-only comparison |
| 2026-09-23 | **The full nightly was NOT run end to end** | CafeF has published 2026-09-22; a real run appends a session to the research DB, which is Ben's call. The steps are proven in isolation (rolled-back tests, a no-commit run of `main()`, a real idempotent snapshot) | running it unasked |

## Working practice (Ben, 2026-09-23)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **One working branch only: `features/exchange-labels`.** All further work is committed and pushed there; no new or stacked per-slice branches. `main` is merged only when Ben asks | Five stacked branches made the repo "really unorganized"; they were merged into main and deleted | a new branch per slice |

## Session 2026-09-23-03 runs 7 + 9 — dated exchange labels (branch `features/exchange-labels`)

Locked by Ben (X1–X3):

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **Date only what evidence dates**: CafeF-documented transfer spans (G4 Class A, 116 symbols) FIRST, then KBS `listing_date` (current exchange from that date). Stored in `exchange_membership` (migration 009), re-derived by `exchanges.rebuild()` | Observed trading filed per exchange outranks a listing date | assuming today's exchange for history |
| 2026-09-23 | **Everything else is UNKNOWN: flag as a hard gate.** Per-exchange results on such days carry `flag__*`: G3 `fillability()` (limit, entry_at_ceiling, exit_at_floor) goes through `quarantine_flagged` (the SAME gate as sector; now takes plain names). The gate's price-limit check counts dated and flagged violations apart | The limit itself may be wrong (±7% applied to a stock that was really on HNX's ±10%) | guessing HNX; inferring from move sizes |
| 2026-09-23 | **X4 unanswered, so raw is left as filed**: `bar_raw.exchange` and `trading_day`'s per-exchange split are NOT re-derived; the resolver is the only historical truth | Conservative default; changes nothing Ben has not approved | rewriting raw |

Found and decided while building (run 9):

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **KBS `listing_date` is not always the date of joining the current exchange; sometimes it is the ORIGINAL listing date.** 16 of the 95 CafeF-documented transfers with a KBS date carry a date years BEFORE the move (HBC: "UPCoM since 2006", moved from HOSE 2024) | Measured against CafeF's two-file evidence | trusting KBS alone |
| 2026-09-23 | **Rule A**: a KBS span contradicted by CafeF's own filing (a row on/after listing_date under another exchange, not explained by a documented transfer) is DROPPED at rebuild. Catches 1 (MHL) | Two sources disagreeing → the date cannot be trusted → unknown | keeping it |
| 2026-09-23 | **Rule B**: a vnstock backfill row is NEVER dated by KBS | G4 Class B rows are pre-transfer by construction; 3,136 rows on 17 symbols had been dated with the current exchange through an original-listing KBS date | per-symbol exceptions |
| 2026-09-23 | Overlapping CafeF spans: the LONGER wins | Three stray one-day HOSE filings on 2015-09-01 (PXL, VLF, VNA) inside long UPCoM spans | the filed exchange |
| 2026-09-23 | **Residual accepted and flagged: 6.43% of liquid stock-days since 2012** (57,738 of 897,588) have no dated exchange | Small enough not to dent the backtestable sample; quarantined, never silently mis-limited | dropping those stocks |

## Session 2026-09-23-03 run 10 — PATTERNS TRANCHE 1 (doc §3.1), branch `features/patterns`

Locked by Ben (P1–P9):

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **P1**: ONE shape flag each (`hammer_shape`, `inverted_hammer_shape`); the trend before the candle comes from the trend measures, never baked into the flag | Hammer = hanging man and inverted hammer = shooting star as SHAPES (doc §3.1); one source for "trend" | separate named flags with a trend condition |
| 2026-09-23 | **P2**: pattern thresholds live in `features.yaml` `measures:`, fixed before any measuring; the `single_candle` block moved out of `patterns.yaml` | Same enable switch and FeatureSet fingerprint as every measure | a second config home |
| 2026-09-23 | **P3**: "long body" = at least the stock's 20-day average body (applies from T2) | Relative to the stock | an absolute body/range cut |
| 2026-09-23 | **P4** (applies at T3): gaps relaxed to "opens below/above the prior close", documented as a VN deviation | Price limits make textbook gaps rare | strict textbook gaps |
| 2026-09-23 | **P5**: `range_rel_20d` kept AND a minimum-range floor inside the shape flags, so a flag is meaningful on its own | Tick noise | relying on consumers to check range_rel_20d |
| 2026-09-23 | P6/P7/P9: breakout later and price-only; flag/pause deferred; no pattern-specific strength numbers yet | — | — |

Implementation choices (run 10):

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **The floor is in TICKS on the RAW range: `min_range_ticks: 3`**, applied to ALL FOUR shapes (not only doji and marubozu) | A 1-tick candle with open = close = high passes every hammer ratio (body 0), so the hammer shapes have the same noise problem; tested | a percent-of-price floor (wrong unit: a tick is 0.2–10% of price depending on price and exchange) |
| 2026-09-23 | **The tick is the DATED exchange's own tick; the LARGEST tick of any exchange only where the exchange is undated** (`checks.floor_tick`) | "Largest everywhere" was built first and MEASURED: it overshot HOSE's real tick 2–10x on 64% of dated liquid HOSE days and dropped about 1 real candle in 10 (72.0% vs 82.6% passing), on HOSE only, an exchange bias. On undated days the largest tick is never looser, so no flag is needed | largest tick everywhere; flagging undated days |
| 2026-09-23 | The bars frame carries raw high/low/close and the resolved `exchange` / `exchange_unknown` | Ticks apply to raw prices on the exchange in force | — |
| 2026-09-23 | With textbook values, "body in the top third" already IMPLIES "lower wick >= 2x body" (and the mirror for inverted). The explicit clause is kept (it binds if a threshold changes) and is tested at 3x | Found while designing the one-test-per-rule cases | dropping the clause |
| 2026-09-23 | Measure metadata for the fingerprint schema (`group`, `direction`) NOT added yet | It is only needed at T5 (assembly) | adding it now |

## Session 2026-09-23-03 run 11 — PATTERNS TRANCHE 2 (doc §3.2), branch `features/patterns`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | Six two-candle patterns per doc §3.2, dated on TODAY, reading yesterday: lookback 1 (harami 21 = the 20-session LONG baseline before yesterday + 1), so a pair across a trading gap or an excluded row is BLANK | The yesterday-adjacent rule, as in breadth and sector | computing across the gap |
| 2026-09-23 | **Prior-body floor: yesterday's RAW body >= `min_prior_body_ticks: 3` ticks** (the same `floor_tick` as T1: the dated exchange's tick, the largest where undated), on all six | A 1-2 tick body makes "covers", "inside" and "past the midpoint" true on noise. MEASURED: it removes 53-55% of engulfings, 23-26% of haramis, ~2% of piercing/dark cloud | no floor; a floor on today's body too (an engulfing body covers yesterday's anyway; a harami's small body is the point) |
| 2026-09-23 | Piercing line / dark cloud cover also require today's close SHORT of yesterday's open (textbook); the doc's wording gives only the midpoint | Keeps them distinct from engulfing: measured 0 days with both | the midpoint-only rule |
| 2026-09-23 | "Opens lower/higher" = beyond yesterday's CLOSE (the doc's wording; P4 is for stars) | Match doc §3.2 | below the prior low |
| 2026-09-23 | **Cross-day comparisons use REL_TOL = 1e-4** on the adjusted prices | 43.5% of raw ties (open2 == close1) come out unequal after adjustment rounding (median 0, p99 2.6e-5); 1e-4 is 4x that and >= 5x smaller than any real tick | exact comparison; comparing raw prices across a possible ex-date |
| 2026-09-23 | IMPLIED colour clauses removed and documented (engulfing: today's colour; harami: yesterday's; piercing/dark cloud: both) | A clause that cannot change the answer cannot be tested | keeping untestable clauses |
| 2026-09-23 | **Mutation proofs purge `__pycache__` and disable bytecode writing on every run** | Found this run: Python's .pyc check is size + whole-second mtime, so a same-size mutation written in the same second reused the PREVIOUS mutation's bytecode. That gave 3 false survivors here. Every earlier proof (T1, exchange labels, sector, universe/breadth) was re-run with the purge: all genuine | trusting the cache |

## Session 2026-09-23-03 run 12 — PATTERNS TRANCHE 3 (doc §3.3), branch `features/patterns`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | Six three-candle patterns per doc §3.3, dated on DAY 3 (the confirming candle is today: nothing is back-dated). Lookback 2, or long_body_window + 2 for the stars and three-inside, so a gap or excluded row ANYWHERE in the window blanks the pattern | The confirmation is part of the pattern, as with the pivots | back-dating a confirmed pattern |
| 2026-09-23 | **P4 applied to the stars**: the star only has to OPEN beyond d1's close (below for morning, above for evening), not truly gap; d3 has no gap requirement (doc §3.3 gives none). Documented as the VN deviation | Daily price limits make true gaps rare | textbook gaps |
| 2026-09-23 | Stars: d1 and d3 must both be LONG against the SAME pre-pattern baseline (the long_body_window sessions before d1) | The pattern cannot raise its own bar | d3 against a baseline that includes d1-d2 |
| 2026-09-23 | **Large-body floor (`min_large_body_ticks: 3`)** on d1 and d3 of a star, all three soldiers/crows, and d1 of three-inside (via the reused harami's own floor). A star's middle candle is NOT floored (tested: a doji star fires) | Its small body is the point, like a harami's second day | flooring every candle |
| 2026-09-23 | three_inside_up/down = the tranche-2 harami function shifted one day, plus d3 closing beyond d1's open | Reuse, not a second implementation | a copy of the harami rule |
| 2026-09-23 | Soldiers/crows: each of d2 and d3 opens WITHIN the previous body (directional: open .. close) and closes beyond the previous close; each of the three closes near its extreme (wick <= max_wick_to_range 0.25 of range, a NEW value). The directional bounds imply every colour, so colours are not checked separately | Matches doc §3.3 and "closing near its high/low" | an explicit colour clause that cannot be tested |
| 2026-09-23 | NEW values (doc §3.3 gives words only): star_body_max 0.3, min_close_into_first_body 0.5, max_wick_to_range 0.25. Fixed before measuring | Textbook-typical | tuning |
| 2026-09-23 | Test bearish cases by MIRRORING the bullish ones (p -> 41 - p, high and low swap): the same price level and ticks, so each bearish rule is tested by exactly its bullish twin's case | Removes hand-mirrored test data as a source of error | hand-written mirror cases |

## Session 2026-09-23-03 run 13 — PATTERNS TRANCHE 4 (doc §3.4) + mutation-proof integrity, branch `features/patterns`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | Four consolidations per doc §3.4, dated on the last day: `tight_range` (mean range of the last 5 < 0.6 x the mean of the 20 sessions BEFORE them; lookback 24), `inside_day_run` (each of the last 2 days inside the day before, with a strictly smaller range; lookback 2), `higher_lows` (4 rising lows, highs within 2% of the close; lookback 3), `breakout` (close above the highest high of the previous 20; lookback 20) | Doc §3.4 wording; the window is kept out of its own baseline | a baseline that includes the window |
| 2026-09-23 | **`breakout` is PRICE-ONLY (P6)**: the old `min_rvol: 1.5` was dropped from config; "breakout on volume" = breakout AND rvol >= 1.5 as a fingerprint combination (measured: 64.6% of liquid breakouts meet it) | Keep one source per concept | baking volume into the flag |
| 2026-09-23 | Tick floors (the same self-meaningful rule): `tight_range` needs a baseline mean RAW range >= 3 ticks; `inside_day_run` needs the MOTHER bar >= 3 ticks (only the mother: small inside days are the point). None on higher_lows/breakout (every step is a whole tick) | "Tight vs a 1-tick normal" and "inside a 1-tick bar" are noise | no floor; flooring the inside days |
| 2026-09-23 | Flag/pause stays DEFERRED (P7). NEW values: inside_day_run min_days 2, higher_lows highs_flat_tolerance 0.02; fixed before measuring | — | — |
| 2026-09-23 | **Mutation proofs count ONLY a genuine test failure** (the test's own assert / DID NOT RAISE / a raises-match, or for the two "fails loudly" tests a different exception escaping `pytest.raises(ValueError)`); a crashed mutant (syntax/import/NameError...), a not-run test, or a mutant that does not compile is NEVER a catch; each mutant is compile-checked; `__pycache__` is purged; test ids are audited against the collected list | Found this run: earlier scripts counted ANY non-zero exit as caught. A strict re-run showed 10 rules "certified" on crashes: 4 since their original runs (exchange listing-date + backfill rule, T3 star midpoint, breadth separate-frame) and 6 introduced by my run-11 whitespace helper (indentation doubled). All 10 were re-proved with valid mutants: all genuine. Final strict totals: every rule in every tranche genuinely caught | trusting the exit code |

## Session 2026-09-23-03 run 14 — the guard-test fix + PATTERNS TRANCHE 5 (fingerprint, doc §3.6), branch `features/patterns`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-23 | **No exemptions in the mutation harness**: the "fails loudly" special case (a different exception escaping `pytest.raises` counted as a catch) was REMOVED. Guard tests now use `tests/_helpers.fails_with(exc, match, fn, ...)`, which judges every outcome by an assert (no error / wrong type / wrong message) | Ben: a crash is not a catch. Proven: the OLD sector test against the guard removal is reported CRASHED (AttributeError); the new one is genuine. All five guard tests (sector input, sector window, market frame, breadth frame, unregistered measure) 5/5 genuine | keeping the judged exemption; `pytest.raises` with a broader type |
| 2026-09-23 | **`base.featureset(config, basis)`** is the ONE definition of a FeatureSet; `compute()` returns it, and the stored fingerprint's staleness check uses it without computing | Two definitions could drift; `compute()`'s own accumulation was deleted | a second copy in fingerprint.py; running compute() to learn the FeatureSet |
| 2026-09-23 | The fingerprint = `compute()` per symbol, stacked (`assemble`): no fill, no normalisation across rows, one row per stock-day for EVERY stock in the build since 2012 (not only liquid; the PIT liquid filter is applied at research time) | Every guard comes along; the universe is a research-time choice | a second code path; a liquid-only table |
| 2026-09-23 | **Schema generated from the registries**: group = the registering module, registry, kind, doc_ref, lookback evaluated with THIS feature set's params, reads_volume, flagged, direction, description = the docstring's first paragraph (8 measures gained a docstring; a test requires one for every measure) | Never hand-typed | a hand-maintained column list |
| 2026-09-23 | **`direction` (bullish/bearish) is an optional `Measure` field, set on 16 patterns**; hammer/inverted hammer, doji, tight_range and inside_day_run have none (trend-dependent, P1, or neutral). Schema only: never a value column, so `query` cannot match on it | Report-only (doc §3 labels are hypotheses) | a direction column |
| 2026-09-23 | **Storage**: `data/processed/fingerprint/<build>_<featureset>/<year>.parquet` + `manifest.json` (build_id, featureset, **code hash**, params, flagged, columns, schema, per-file rows + sha256). The manifest is deleted FIRST on a rewrite and written LAST. `load(build, fs)` refuses: no stored pair, a manifest disagreeing with it, a different code hash, a file whose sha changed | The trading_day lesson. The CODE hash (over `data/`, `features/`, `patterns/`) is my addition: a fixed rule with unchanged params keeps the same FeatureSet fingerprint, so without it a stale table would load silently | params-only staleness; a Postgres table (P8) |
| 2026-09-23 | **`validated()` is the only path to validated values**: it applies `quarantine_flagged` with the MANIFEST's flagged list; returns a `Validated` that only `validated()` can construct; `load(columns=...)` always brings each flagged measure's flag column | Ben: the ONLY path | trusting callers |
| 2026-09-23 | **`query`**: exact combinations, conditions = a number (equality) or a comparison with a FIXED number; `hit` is 1/0/NaN (boolean_from), NaN outside `judged`; per-symbol occurrence counts | A data-derived threshold is look-ahead; unknown never counts as false | percentile thresholds; NaN as 0 |
| 2026-09-23 | pyarrow added as a runtime dependency | Parquet (P8) needs an engine | fastparquet |
| 2026-09-23 | Market/sector values are still recomputed per symbol inside compute() (a `ponytail:` note in `build`) | Measured: 0.12 s of 0.68 s per symbol; a full build is ~20 min | a precomputed path that bypasses compute() |
| 2026-09-24 | **Bug fixed (found by the first real build): `compute()` crashed on any stock with NO sector label in any snapshot.** `sectors.assign` returned an all-NaN FLOAT sector, which pandas refuses to merge with the string sector keys. Now the empty sector keeps the labels' dtype, so the stock gets NaN sector values, flagged. 125 of 1,705 symbols (40,667 stock-days since 2012, delisted stocks absent from today's ICB snapshot) | Test `test_a_symbol_with_no_label_at_all_is_blank_and_flagged` failed with the same error before the fix and passes after; the strict proof is genuine (the test turns a crash into an assert, because not crashing IS the rule). Earlier runs used liquid, labelled stocks only, so it never showed | dropping unlabelled stocks from the fingerprint |
| 2026-09-24 | `test_each_sector_measure_is_individually_flagged` now asserts that every flagged measure has its flag column | After the `featureset()` refactor, removing a per-symbol flag made the test crash on a KeyError instead of judging it | — |
| 2026-09-24 | Exchange-label proof script: the filed-exchange mutant is now mapped to the test that catches it (`test_the_gate_judges_a_move_by_the_dated_exchange_not_the_filed_one`); strict 15/15 | Run 13 had confirmed it by hand; the script still named the old test | — |

## Session 2026-09-23-03 run 15 — merge + analysis-engine PROPOSAL, branch `features/analog-backtest`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | main fast-forwarded to `f53b72a` (T1–T5) by me at Ben's choice; `features/patterns` deleted locally and on GitHub; `features/analog-backtest` cut from the new main | Ben said "merged", but origin/main was still 168c2e9 with no PR; verified first, then asked | cutting from the unmerged main |
| 2026-09-24 | PROPOSED (not decided): outcomes in their own table, joined to features only through one gate; exact combinations = evidence, kNN = one pre-registered look-alike method; purge by `known_on`; BH-FDR over a logged hypothesis count; a base rate on the identical population; a level-labelled fallback. Awaiting A1–A12 | Doc §8, G5 | — |

## Session 2026-09-23-03 run 16 — ANALYSIS ENGINE E1 (limit function + forward returns + storage), branch `features/analog-backtest`

Ben APPROVED the engine design with rulings on A1–A12 (as proposed: k = 3 and 5 both; hit = net > 0; liquidity tier validated + sector exploratory; 30 de-clustered; split 2012–2019 / 2020–2023 / 2024→freeze; BH-FDR q = 0.10 then same sign + min edge + net > 0; 21 triggers × up to 2 of ~8 conditions; hybrid kNN k = 50 after exact combos; adjusted ex-date reference + UPCoM flagged approximate; shared storage; MFE/MAE now; accept the ceiling rejection and report it) plus FIVE ADDITIONS:
1. the holdout rule is PRE-REGISTERED (written down before any discover run);
2. `known_on` = the ACTUAL resolution date, including any deferral;
3. every NET result is stamped PROVISIONAL on the 0.15% fee;
4. measure and report the liquid UPCoM share;
5. report the discover → validate SURVIVAL count.

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | **`checks.limit_prices(ref, exchange, dates, first_day)` is THE ceiling/floor** (rate, ceiling, floor, ticks). The dated limit (`limit_rate`) or the first-day band; ceiling rounded DOWN and floor UP to the tick of the limit price ITSELF; one tick from the reference when rounding lands on it; `at_ceiling`/`at_floor` = within HALF a tick. `limits_sql` is its SQL twin. The gate's price-limit SQL and `scripts/measure_fillability.py` now use it; the flat-epsilon helpers are deleted | B1 (Ben's ruling). A live test asserts Python == gate SQL row for row on real stocks covering resumption, sub-tick cheap stocks, UPCoM and pre-2013 | a second definition per caller |
| 2026-09-24 | **The gate's resumption is counted in SESSIONS** (skipped ≥ 25, from `trading_day`), no longer 35 calendar days; the `n <= 2` leniency was dropped; a violation = a raw close more than ONE TICK beyond the exact ceiling/floor. Gate count (warn only) 4,572 → 4,521 dated, 955 → 913 flagged | One definition with the backtest; the tick of slack absorbs UPCoM's average-price reference and cash-dividend ex-dates | the old move-vs-rate+tick test |
| 2026-09-24 | **B1 was a ~7x undercount, not "slight"**: the flat 0.0015 tolerance only caught ceilings that needed no rounding. Liquid entries at the ceiling 0.133% → **0.929%**, exits at the floor 0.342% → **2.272%** (whole market 0.741 → 3.427%, 0.799 → 3.802%). Checked on a sample: detected opens sit 0–2.4% below the unrounded limit, exactly the rounding gap | Measured | — |
| 2026-09-24 | Rounding rules (ceiling down / floor up, the tick of the limit price, one tick from the reference) are in code, marked TO CONFIRM against the exchange rulebooks | Not in market_rules.yaml's verified facts | — |
| 2026-09-24 | **Forward returns** (`forward_returns.outcomes`): per row t and k ∈ {3, 5}: ret (adjusted), net, mfe, mae, exit_offset, deferred, known_on (actual resolution), reason, upcom, flag__fill. Reasons in walking order: pending, data_ends (G11), no_next_session, window_gap (incl. deferral sessions), window_excluded (t .. exit), not_tradeable (zero matched volume or date-shifted, entry or exit), not_sellable, entry_at_ceiling, exit_floor_unresolved | G3 + the approved proposal | — |
| 2026-09-24 | "pending" (the MARKET calendar ends first) is kept apart from "data_ends" (the stock's rows end while the market goes on: delisted or still suspended) | G11: never mix "not known yet" with a stock that disappeared | one "no data" reason |
| 2026-09-24 | The reference price = adj(t-1) / factor(t) (= the raw previous close on an ordinary day); fillability is FLAGGED on UPCoM and on undated exchanges, and where no limits exist; an outcome is flagged if ANY judged row (entry + every exit attempt) is | A9 | flagging the entry only |
| 2026-09-24 | **`store.py`**: the shared Parquet-by-year + manifest code (write / load / code_hash / files_hash). The fingerprint and the returns both use it; a column's flag always comes with it via the manifest's `flag_for` | Ben: reuse the fingerprint's storage | two copies |
| 2026-09-24 | Returns stored at `data/processed/returns/<build>_<rules-hash>/`; the manifest records build_id, a rules hash (market_rules, costs, patterns.yaml), a code hash (backtest, data, features, store.py), the file hashes, and `net_provisional`. `join(fp, returns)` refuses two builds | Ben's E1 spec | — |
| 2026-09-24 | `features.bars.load` now carries `date_shifted` | A shifted bar is never an entry or exit day (universe.yaml) | a second query |
| 2026-09-24 | The fingerprint's code hash now also covers `store.py` | Its writing and reading code | — |

## Session 2026-09-23-03 run 17 — shm_size, G20 detector (PART 0), E2 gate + base rates (PART 1), branch `features/analog-backtest`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | `docker-compose.yml`: `shm_size: 1gb`; container recreated on the same volume; the parallel-off workarounds removed | Ben. Proven: the whole-market join that failed with "could not resize shared memory segment" completes in 8 s with parallel workers on | keeping the per-query workaround |
| 2026-09-24 | **G20 detector = `checks.factor_triage`**: an ADJUSTED move beyond `JUMP_LIMITS` (2) x the daily limit on a factor-change day (`FACTOR_TOL` 1e-6, the gate's own tolerance), backfilled rows not judged; labels 'resumption' (>= 25 sessions skipped: already a gap), 'new_exchange' (first day on another exchange, raw close inside that exchange's first-day band + 1 tick), else 'defect'. Reads only the row and the one before (no look-ahead) | Ben's definition; the resumption rows need no exclusion because the gap rule already blanks every window across them | a list written to excluded_window (a DB write the stored tables' manifests could not see: the trading_day lesson) |
| 2026-09-24 | **Defects blank windows LIKE A GAP**: `bars.load` sets `factor_break`; `features.base._window_ok` treats it as a gap; `forward_returns.outcomes` blanks entry/window crossings with reason `factor_break`. Computed from the build's own data, so the build_id + code hashes cover it | Ben: "blanked, like a gap". A gap (between two rows) not an exclusion (of the day): the defect day's own candle is intact | marking the day excluded |
| 2026-09-24 | **Triage of the 1,818** (production code path, `scripts/triage_factor_defects.py`): 1,305 resumptions (373 symbols), 2 new-exchange first days, **511 genuine defects on 313 symbols** (peak 2023: 115). The scratch breakdown of the defects: ~372 raw jumps with only jitter-level factor change (missed action / bad print), ~105 factor changes with no raw gap, ~31 wrong factor ratio (BNA), ~2 misdated. Liquid resolved outcomes crossing a defect: ~0.01% (far under the 5% stop) | Measured | — |
| 2026-09-24 | `checks.reference` (moved from forward_returns) is the one reference-price definition, shared by fillability and the detector | One definition | a copy |
| 2026-09-24 | **The gate moved to `backtest/evidence.py`**: `validated(fp, returns, universe, before)` is the ONE join of features and outcomes; `fingerprint.validated`/`Validated` were removed (their tests moved to test_evidence.py). It refuses two builds, blanks flagged features (quarantine_flagged), blanks outcomes that are fill-flagged / not liquid on t / not known strictly before `before` (reasons `fill_flagged`, `not_liquid`, `not_yet_known`; the returns' own reason wins), and drops rows from `before` on. `Validated` only from `validated()`; `evidence()` refuses anything else | Ben's E2 spec; the gate needs the outcomes, which live in backtest/ | two gates |
| 2026-09-24 | **`evidence(v, conditions, k, symbol)`**: hit = net > 0; the base rate over every eligible stock-day at the same level/period/horizon where the condition was JUDGED (an unjudged day is in neither, counted `condition_unknown`); edge = hit − base; gross, expectancy, avg win/loss, MFE/MAE mean + worst MAE; the fallback stock → liquidity tier (the stock's tier on its latest liquid day in the period) → market, the first level with >= 30 DE-CLUSTERED occurrences (a repeat within k sessions of a counted one is not new); `sufficient=False` if even the market falls short; sector beside, EXPLORATORY; every level carries n raw/de-clustered, the base rate + n, the drop reasons; the Evidence carries period, before, and the PROVISIONAL stamp | Ben's E2 spec | a base rate over all days regardless of judgeability |
| 2026-09-24 | **Liquidity tiers** (`universe.tiers` / `tier_panel`): terciles (`universe.yaml liquidity.tiers: 3`) of the day's liquid set by the trailing 60-session average traded value | A3; knowable on the day | sector as the validated middle level |
| 2026-09-24 | The returns' code hash now covers `backtest/forward_returns.py` only (plus data, features, store.py), not the whole of backtest/ | evidence.py reads outcomes; changing it must not make stored outcomes stale | — |
| 2026-09-24 | Real-data E2 sanity is run on the DISCOVER years only (before 2020-01-01) | Validate and holdout stay unseen until E3's pre-registered protocol | full history |
| 2026-09-24 | **Bug found by the real-data run, fixed:** `universe.tiers` crashed on real data. pandas 3's `stack()` keeps NaN cells, so the non-liquid stock-days survived and the int cast failed. Now `tier_rows` (pure, tested) drops them explicitly; tier is nullable Int64 | The new test fails without the filter (strict genuine); the unit test on `tier_panel` alone had not covered the stacking | — |

## Session 2026-09-23-03 run 18 — E3: the discover/validate protocol, branch `features/analog-backtest`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | **Pre-registration committed ALONE, before any protocol code or run** (`b3ca180`, config/rules/protocol.yaml): 21 triggers × (1 + 8 + 28) × k {3,5} = 1,554; slices 2012–2019 / 2020–2023 / 2024→freeze; min 30 de-clustered; BH q = 0.10 on date-block bootstrap p (10-session blocks × 2,000, seed 20260924); validate rule same sign + edge ≥ +3 pts + net expectancy > 0; the HOLDOUT rule (keep sign + net expectancy > 0 with ≥ 30 de-clustered, on 2024→freeze, run once with Ben) | Git history proves the order: registration → code (`c132439`) → runs | registering alongside the code |
| 2026-09-24 | The `registered` block is FROZEN by a hash written into every log row; later ideas go to `additions` | Ben: freeze it | editable config |
| 2026-09-24 | **Hypothesis log in git** (`research/hypothesis_log.csv`), one row per hypothesis per run with the protocol hash, code hash, build, slice and result; N = distinct hypotheses ever logged, printed on every result line | Auditable, and survives outside the machine's data folder | a log under data/ (git-ignored) |
| 2026-09-24 | **Spent data**: a hypothesis may be tested on a slice only if the slice is unused or it was part of the slice's FIRST run; validate takes only the survivors of the LATEST discover run; the holdout is refused in code | Ben: a later hypothesis is tested only on data not already used | date-based registration (loophole on the same day) |
| 2026-09-24 | Test statistic: edge = de-clustered hit rate − base rate (market level, liquid on t, through the gate); p two-sided = share of resampled date-blocks on the far side of zero, (tail + 1) / (B + 1); untestable → p = 1, still in m; BH with m = N; survivors need testability | Many stocks move together on one day and an outcome spans several days | row resampling (overstates significance: test shows p 0.06 vs ~0.001) |
| 2026-09-24 | The validate rule is applied EXACTLY as written, so a discover survivor with a NEGATIVE edge (a pattern that does worse than the base) can never hold (it would need +3 pts) | Ben's rule; flagged for him as a question | re-reading the rule |
| 2026-09-24 | Walk-forward = each hypothesis's edge year by year over 2012–2023, each year purged at its own end; reported for every validate hypothesis | The parameters are fixed, so walk-forward is persistence, not refitting | — |
| 2026-09-24 | **RESULTS (discover 2012–2019, validate 2020–2023; holdout NOT run):** N = 1,554; testable 1,454; **passed discovery 82** (46 k=3, 36 k=5; 8 with a negative edge); **held on validate 16** (12 k=3, 4 k=5). Failed 66: 7 flipped sign, 8 negative-edge (cannot pass the rule), 59 kept sign but fell short of +3 pts or net > 0. Discover flagged 1 suspicious (an untestable 9-occurrence evening star) | Measured | — |

## Session 2026-09-23-03 run 19 — E4: the look-alike search + E3 display, branch `features/analog-backtest`

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | **The neighbour method was registered ALONE before any code** (`a828418`): its own frozen `neighbours` block in protocol.yaml. The exact fired set of the 21 triggers (every trigger known); 13 numerics as the same-day percentile among liquid stocks; 4 booleans as 1/0; mean absolute distance over columns known on both; >= 80% known; equal weights; k = 50; k 3/5 outcomes. The E3 `registered` hash is unchanged (0106fab4dc2f35a2) | Ben: registered and hash-frozen before it runs | registering alongside the code |
| 2026-09-24 | **`pool_before: 2024-01-01`**: until the holdout is run, look-alike outcomes come only from before the holdout | Showing 2024+ outcomes before the holdout would let us see the holdout period first | a pool up to the query day |
| 2026-09-24 | Market-level measures are not used as percentile context (every stock has the same value on a day, so they would rank as ties); the regime enters as the boolean `index_above_ma_50` | A same-day percentile of a market value carries no information | index_change_20d etc. as numerics |
| 2026-09-24 | The pool is exactly the gate's rows with an outcome at every registered horizon (the gate already blanks non-liquid, fill-flagged and late rows); a redundant liquid clause was removed after the strict proof showed it could not be caught | One rule, one place | a second liquid filter |
| 2026-09-24 | `research/neighbours_log.csv` records every look-alike run with the method hash (the freeze check) | Auditable, like the hypothesis log | — |
| 2026-09-24 | **Display only:** `protocol.families` groups the held survivors by the same trigger + nested conditions (any horizon, transitive): 16 → **6 families** (3 + 1 + 1 + 7 + 3 + 1). `protocol.summary` shows them plus the 8 negative-edge discover survivors as EXPLORATORY avoid candidates (5 kept a negative sign on validate; the 3 evening-star variants flipped positive). No rule registered, no verdict changed | Ben: collapse the 16 into families; avoid candidates exploratory only (no unused data to test an avoid rule without spending the holdout) | registering an avoid rule |
| 2026-09-24 | Bug found while testing, fixed: under pandas 3, `where(..., None)` on a string column stores NaN, so a query with an unjudged trigger fell through to the wrong reason. The fired key is now an object array; the query uses `pd.isna` | The test failed before the fix | — |
| 2026-09-24 | **The holdout freeze F = 2026-09-10**, computed by `protocol.freeze_date`: the last session before the first entry (since 2024-01-01) with a k=3 or k=5 outcome still `pending` (2026-09-11: floor-deferred exits); the last settled session is 2026-09-21 | Every outcome of an entry up to F is final; cutting at the first pending day keeps out the floor-locked losers that dropping pending rows would lose | hardcoding today; dropping the pending rows |
| 2026-09-24 | The protocol hash leaves out `slices.holdout.end` | It was the one value registered as open ("set when run"); the E3 hash `0106fab4dc2f35a2` stays valid, and the holdout cannot be moved and re-run (it runs once) | a new hash (which would have refused the E3 log) |
| 2026-09-24 | The holdout gate's cutoff is the day after the last settled session; entries after F are cut by the slice; any entry up to F whose outcome is not final is refused | No price after the cutoff exists; nothing is silently dropped | a cutoff at F + 1 (it would blank the last week's outcomes, which contradicts F) |
| 2026-09-24 | The holdout's used-data rule: any holdout row in the log refuses a run | The holdout is spent by its one run | reusing check_unused (it allows a re-run of the first-use hypotheses) |
| 2026-09-24 | The holdout verdict is `holdout_rule` as written: same sign as discover, net exp > 0, ≥ 30 de-clustered, else NOT TESTABLE; there is no min_edge | Ben: not `holds()` | reusing `holds()` |
| 2026-09-24 | The fee lines are information only: net + verdict at an ALL-IN round trip (both broker fees + the 0.10% tax, which stays fixed) of 0.10/0.25/0.40%, plus the break-even all-in cost | "All-in round trip" taken literally: the registered cost is 0.40% (it reproduces the verdict exactly), so the range looks at cheaper brokers, and the break-even shows the costlier side | a per-side fee reading |
| 2026-09-24 | **THE HOLDOUT RESULT** (run once, 2026-09-24T08:46:45Z): 16 → **6 ACCEPTED, 9 REJECTED, 1 NOT TESTABLE**. Only 2 of the 6 have p < 0.05 (k3 marubozu_red+breadth+rvol, k5 marubozu_red+ma50rising+rvol). 5 rejects are fee-hinged (ACCEPT at 0.10%) | The finding; nothing tuned after | — |

## Session 2026-09-24-01 — the holdout described (branch `claude/great-bell-6wr1jq`, on top of `features/analog-backtest`)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | **Describe the holdout, never re-judge it:** `protocol.describe_holdout` takes the verdicts from the log and re-derives the SAME de-clustered trades (`occurrences`, the logic `evaluate` uses). It REFUSES unless their count and mean NET equal the logged ones exactly, and the build matches. It writes no log row, so it is safe to repeat | Ben asked for the missing doc §8.3 numbers; the holdout is spent and is only read | re-running `holdout` (refused, and would spend it again) |
| 2026-09-24 | The metrics (`backtest/risk.py`, information only): avg win / avg loss / payoff / best / worst per trade; max drawdown and worst losing streak on a FIXED stake per signal day (not compounding, in units of one stake), two ways: **basket** (the stake split over every stock that fired that day) and **one pick** (one of that day's stocks at random, 1,000 seeded paths, median + worst-5% path); the share of 60-pick stretches ≤ 0. A loss is net ≤ 0 (a hit is net > 0). Order = signal date; overlapping positions allowed; no slippage beyond the costs | "One pick" mirrors the daily scan's single proposal; "basket" is the smooth upper bound; a fixed stake keeps every number readable in VND (1% = 1M at 100M a trade) | compounding equity (hides the stake size); one pick with no overlap (would need a position-sizing rule nobody has decided) |
| 2026-09-24 | Describe costs 0.16 / 0.40 / 0.60% all-in (`DESCRIBE_ROUND_TRIPS`) | The researched real range (context-vietnam.md); 0.10% is unreachable because of the exchange's 0.03% a side | 0.10 / 0.25 / 0.40 (the holdout report's grid, which is left unchanged) |
| 2026-09-24 | `_holdout_gated` split out of `run_holdout` (one loader for the run and its description) | The description must see the same rows; behaviour unchanged, the holdout tests pass as before | copying the loader |
| 2026-09-24 | `claude/great-bell-6wr1jq` fast-forwarded into `features/analog-backtest` (now `674a2ce` + run 21), keeping ONE working branch. Deleting the session branch was blocked; Ben deletes it | Ben: "do like your recommendation" | working on the session branch |
| 2026-09-24 | The describe report gives totals and drawdowns in STAKES (not %), shows avg per trade beside avg per signal day, names the best/worst trades, and measures the cash needed (`risk.max_open`) from the real exit dates | Ben found the report confusing: "−48%" read as half an account; the old chat table compared a sum over trades with one stake a day | keeping % of one stake |

## Session 2026-09-23-03 run 22 — the DAILY SCAN + PAPER TRADING, branch `features/daily-scan` (cut from `features/analog-backtest`)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | **The scan trades EXACTLY the 6 ACCEPTs of the latest holdout run, as-is** (`report/scan.accepted`). "Strong" = one fired; no performance threshold | Ben: the forward record must be of what the frozen rule accepted; no filter fitted on the holdout or its description | per-day filters chosen after seeing the describe |
| 2026-09-24 | **G9 answered by Ben's tie-breaker, frozen as `daily_scan` in protocol.yaml** (own hash in every ledger row): validate net expectancy (per trade, frozen; ranks only) → 20-session mean traded value known at T → the more liquid tier → symbol | Declared before any forward day is scored, using only frozen or known-at-T numbers | a fitted evidence score |
| 2026-09-24 | **Tier direction**: data.universe numbers tiers 1 = LEAST liquid … 3 = most. Ben's prompt said "tier 1 = most liquid"; the block prefers the MORE liquid tier (his meaning), with a comment. Flagged to Ben | The code's numbering predates the prompt | renumbering tiers (would change E2/E3 outputs) |
| 2026-09-24 | **Eligibility mirrors the holdout's gate at T**: liquid on T, and fillability judgeable (a DATED exchange, not UPCoM). Frozen in the block | The gate blanked every undated/UPCoM outcome, so no accepted signal was ever measured on one | proposing UPCoM stocks |
| 2026-09-24 | **Paper-trading pass rule frozen as `paper_trading`** (Ben's numbers): ≥ 30 scored signal days spanning ≥ 3 months; PASS = cum > 0 AND max DD ≥ −1.0 stake AND strictly > half the months positive; FAIL = cum ≤ 0 OR DD < −1.5; else PROVISIONAL; no PASS/FAIL while the fee is PROVISIONAL | Ben, 2026-09-24 | — |
| 2026-09-24 | "Spanning 3 months" = the last scored signal day is on or after the first + 3 calendar months. Months for the majority rule = calendar months of the signal days | My reading of Ben's wording; frozen | distinct months touched |
| 2026-09-24 | **VOID vs STUCK**: an outcome decided at entry with no trade (e.g. opens at the ceiling) is VOID (no stake; counted, not scored); a placed stake with no return (gap in the hold, data ends, floor-locked past the cap) is STUCK and WITHHOLDS any verdict until Ben rules | Dropping a stuck stake would hide a loss (the freeze_date lesson) | dropping both; scoring stuck as 0 |
| 2026-09-24 | **Forward record = days strictly after `frozen_on` 2026-09-24** (the freeze commit's date). 2026-09-11..09-21 are recorded in the ledger labelled BEFORE THE FREEZE and never enter the forward record | Ben | counting them as forward |
| 2026-09-24 | The ledger (`research/paper_ledger.csv`, in git) is append-only, one row per day; re-running the same day returns the recorded row; a DIFFERENT proposal for a recorded day is refused | Idempotent and never rewritten | overwriting on re-run |
| 2026-09-24 | The report states no stop and no target (none was registered or tested; the rule is a time exit) instead of inventing one for doc §7.4 | Honesty over completeness | a stop fitted now |
| 2026-09-24 | **`daily_scan` v2 — HOSE FIRST** (Ben: focus HOSE ~85% / HNX ~12% / UPCoM ~3%; HOSE = the big, reliable companies, HNX/UPCoM mostly small caps). The tie-breaker's FIRST key is now the exchange, [HOSE, HNX, UPCOM]: HNX is proposed only when no HOSE stock is eligible; UPCoM stays excluded. Hash `a5be2561c39c60af` (v1 `914a3afc4d05fea0` ran only on the 7 pre-freeze days) | Ben chose "HOSE first in tie-break". My option text contradicted itself ("right after signal quality" vs "HNX only when no HOSE fires"); I implemented exchange FIRST, his stated reason, and flagged it; swapping to second is a one-line change, possible only before the first forward day | an exact 85/12/3 quota; HOSE only; effort-only |
| 2026-09-24 | **The freeze guards the FORWARD record only**: `check_frozen` compares forward rows' hashes, so a change Ben makes before the first forward day does not split the record; pre-freeze rows keep the hash they ran under | The freeze exists for the forward record | refusing any change after any row |
| 2026-09-24 | **Ben CONFIRMED the exchange key FIRST** (daily_scan v2 as committed) and asked to merge: main fast-forwarded to `features/daily-scan` (which contains `features/analog-backtest`); the three merged branches (daily-scan, analog-backtest, claude/great-bell-6wr1jq) deleted locally and on GitHub | Ben, run 24 | — |

## Session 2026-09-23-03 run 25 — NEW-HYPOTHESIS BATCH `complements_1`, branch `features/new-hypotheses` (cut from main = the deleted daily-scan head)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-24 | **A batch is candidate generation, not confirmation.** The 2012-2023 slices were already seen by the registered run; survivors can only become forward paper-trading candidates. No holdout path exists for a batch | Ben | re-using the spent holdout |
| 2026-09-24 | **The rule that defines `complements_1`**: the registered context vocabulary made two-sided. Each of the 8 registered conditions gains its EXACT complement (same measure, other side of the same comparison: >= -> <, > -> <=, == -> !=; no new measure or threshold). Batch = 21 triggers x every 1-2 of the 16 conditions with >= 1 complement and never a condition with its own complement (92 sets) x k 3,5 = **N 3,864** | The registered conditions were one-sided (above / rising / up / positive), so every "in a downtrend / weak market / breadth negative" context (doc §5.1: a reversal needs a prior decline) was never tested. Mechanical, not curated | 3-condition combos over the 8 (deeper into small samples); a hand-picked list |
| 2026-09-24 | Batch rows go to their OWN log, `research/hypothesis_log_batches.csv` (batch name + batch hash in `protocol`) | Appending to the original log would feed `_latest(log, "validate")` (the scan's tie-breaker), describe and `check_registration` with batch rows; the original log stays byte-identical | appending to hypothesis_log.csv |
| 2026-09-24 | The original "used data is refused" check stands UNCHANGED for the registered set; a batch has its own: each slice runs ONCE per batch | Read literally, the original check refuses every new hypothesis on the used slices, which would forbid the task Ben set | changing check_unused |
| 2026-09-24 | Fee out of scope (Ben): hit = GROSS return > 0 via `batch.gross` (ret in place of net, so evaluate / bootstrap / walk-forward are reused unchanged); net at the provisional cost computed beside as information only | Reuse, no second statistics path | a gross flag threaded through evaluate |
| 2026-09-24 | Discover = BH q 0.10 over the batch N AND testable AND abs(edge) >= 3 pts (the registered min_edge reused), both signs. Validate = same sign AND gross expectancy > 0. Candidate = held AND edge > 0 (no short selling). "Materially stronger" = on validate, gross basis: higher edge AND higher gross than the best of the six AND >= their best walk-forward years positive; all registered in the block before the run | Ben's gates, made exact before the run | net gates |

## Session 2026-09-25-01 run 1 — PATTERN HISTORY (descriptive, info only), branch `claude/design-system-pattern-history-aqbkd8` (cut from main `dfabd5b`)

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-25 | **A DESCRIPTIVE study, not a test**: no hypothesis-log row, no p-value, nothing in N, no holdout path; the report says so at the top and above the summary | Ben: information only; it must not be read as an edge | running it through the batch/protocol machinery |
| 2026-09-25 | **2026 excluded entirely**: study end 2025-12-31; `load_config` refuses an end in 2026+, and `study` refuses any 2026 row that reaches it | Ben: incomplete, single-regime downtrend | a partial 2026 column |
| 2026-09-25 | **Point in time = the gate per period**: discover / validate / holdout_spent each through `evidence.validated` with `before` = the next period's start (the last: 2026-01-01), so an outcome counts only if known before its period ended | The same purge the protocol applies to its slices; it costs only the last few sessions of 2019, 2023 and 2025 | one gate at the study end only (lets a 2019 fire use a 2020-known outcome) |
| 2026-09-25 | Statistics on DE-CLUSTERED fires (de-clustered over the whole history, then split by month/regime); the raw count beside; base = every liquid stock-day where the signal could be JUDGED (not de-clustered); hit = gross > 0 strictly; the market itself shown as `ALL_LIQUID` | The engine's own rules (evaluate / evidence), so the numbers agree with the rest of the project | stats on raw fires; one market-wide base for every signal |
| 2026-09-25 | Regime = `index_above_ma_50` on the signal day; an unknown regime counts in "all" only | Ben's definition; unknown is never a guess | forward-filling the regime |
| 2026-09-25 | The structural signals = the 8 fixed comparisons of batch structural_1, copied unchanged (rs_20/60/120 > 0, down-day RS > 0, stage 1–4) | No threshold chosen for this study | new thresholds |
| 2026-09-25 | **Cherry-picked 1b04481 (structural features) onto this branch** | Ben asked for main as the base AND the structural signals; they exist only on `features/structural-features`. Code + tests only: no batch, no log rows. Same content as that branch, so merging both should not conflict | cutting from features/structural-features (would carry its batch + log rows); dropping the structural signals |
| 2026-09-25 | Summary rules fixed in `history.yaml` before any real run: a year is judged at ≥ 10 de-cl fires; ranked at ≥ 30 in total; ordered by the share of judged years beating the base, then the pooled edge; LEANS = without its best 2 years (fires × edge) the pooled edge falls to ≤ 50%; up vs down differ at ≥ 3 points; plus a coin-flip yardstick (chance of ≥ b of j years, times the number of signals) | "Consistent" needs a scale: with 29 signals, some beat the base 10 of 14 years by luck | ranking by pooled edge alone (rewards one great year) |
| 2026-09-25 | Pushed to the session branch `claude/design-system-pattern-history-aqbkd8`, not `features/pattern-history` | The cloud harness pins this session to that branch; one branch only. Ben can rename it | pushing a second branch |
