# Open questions

## For Ben (doc §11.3)
- [ ] Holding period to optimise for: 3 days, 5 days, or "until target or stop"?
      Blocking: [[validation]] §8.2 requires parameters fixed *before* testing.
- [ ] Minimum liquidity — which stocks are too small to consider (VND/day)?
- [ ] Risk tolerance — what losing streak / drawdown is acceptable in paper
      trading?
- [ ] Is "no pick today" acceptable on most days, or is a daily pick expected?
- [ ] SSI FastConnect credentials — registration must be done in person
      (doc §11.4 step 2). Blocks Phase 3.
- [ ] One pick per day: does it interact with what Ben already holds, or is
      each day independent? The doc never mentions portfolio state.

## For the broker friend (doc §11.2, §3.6)
- [ ] Which 5–10 setups does he trust most, with 3 winning and 3 failing
      examples each?
- [ ] What does "wrong behaviour" look like — what makes him react fast?
- [ ] How does he read volume: which days, what multiple of normal, matched
      only?
- [ ] Weight given to foreign flow, proprietary-desk (tự doanh) flow, sector
      moves, the VN-Index?
- [ ] Typical holding period and where he puts his stop?
- [ ] Which kinds of stocks does he avoid entirely?
- [ ] Which news types override a good chart?
- [ ] When bullish and bearish signals appear together, which does he trust?
- [ ] Does he think in combinations ("hammer + volume + support") or does one
      element dominate?
- [ ] Which *cases* of a pattern does he treat as fake?
- [ ] Client pain points (still pending from earlier sessions).

## MUST RESOLVE BEFORE ANY MEASUREMENT

Every item below was found by reading the source document in session 01. Each
one changes what a number *means*, so measuring before they are settled would
produce statistics that look fine and are wrong. Confirmed by Ben 2026-09-22.

### G1 — Volume is never adjusted alongside price
Doc §7.5 adjusts OHLC by the ratio *adjusted close ÷ close* for stock dividends
and rights, but says nothing about volume. Volume must be adjusted by the
inverse ratio or RVOL, sustained volume and every other measure in
[[money-flow]] break across every corporate action — and VN companies pay stock
dividends constantly. **Resolve:** decide and document the volume adjustment
rule; verify against a known 2:1 stock-dividend case in the probe data.

### G2 — Adjusted close probably drifts on every update
If SSI re-states its adjusted close after each new corporate action, then stored
history silently shifts on every nightly update, and yesterday's fingerprints no
longer match today's. **Resolve:** the Phase 3 probe must fetch the same old
date twice, before and after a known recent event, and compare. Then choose:
store raw + our own adjustment factors and recompute, or re-download and
recompute history on each event.

### G3 — Forward returns as defined are not tradeable
Doc §2 measures 3 and 5 days forward **from the signal day *t***. But entry is
day *t+1* at the earliest (no look-ahead, doc §8.1) and T+2 settlement means the
earliest realistic sell is ~*t+3* ([[context-vietnam]] §5.6). These are two
different numbers and only one is achievable. **Resolve:** fix a single
definition — proposed: signal at *t* close → entry at *t+1* open → measure
returns at *t+1+k* for k = 3, 5 — before any statistic is computed.

### G4 — Corporate identity changes break history
Ticker changes, mergers and HNX↔HOSE transfers are not mentioned anywhere in the
document, yet each one splits or merges a stock's history. A pattern measured
across such a break is measuring two different companies. **Resolve:** get a
listing/delisting/transfer event list, and decide whether history is stitched or
cut at the event.

### G5 — Overfitting defences do not cover the analog search
Doc §8 defends single-pattern testing (fix parameters, count variations, split
the data). The fingerprint analog search of §3.6 has its own free parameters —
similarity metric, number of neighbours k, feature weighting, which of the ~100
measures are included — and none of them are covered. This is the largest
unguarded surface in the project. **Resolve:** write the analog search's
parameters and their defences into [[validation]] before the first analog is
computed.

### G6 — Whole-market paging cap shapes the download
DailyStockPrice pages at most 10 × 1,000 rows, so one whole-market range request
returns ~6 trading days at ~1,600 codes. **Resolve:** confirm in the probe, then
choose the download loop (per-day whole-market vs per-symbol full-range) from
the measured limit, not from the doc.

### G7 — Market regime: filter or reported dimension?
Stated both ways: a funnel filter in doc §7.2 step 3 ("if the whole market is
weak, raise the bar"), and a dimension reported alongside every signal in §5.3
("report hit rates separately for good and bad market conditions"). These are
different designs and the second is strictly more informative. **Resolve:** pick
one with Ben; recommend measuring as a dimension and only then deciding whether
it should also filter.

### G8 — 2010 vs 2012 start
Doc §7.5 says "full history is a must — the friend studied every stock from
2010" and then sets the window at 2012. **Resolve:** confirm 2012 is final
(it is currently recorded as a decision in [[decisions]]), or extend and treat
2010–2011 as a separately reported slice.

### G9 — "Rank by evidence strength" is undefined
Doc §7.2 step 7 reduces a handful of candidates to one pick by "evidence
strength", and never defines it. This is the last mile of the entire system.
**Resolve:** specify the scoring function — what it combines (edge over base
rate, occurrence count, expectancy after costs, context agreement) and how it
breaks ties — before the daily scan is built.

### G10 — Parameters cannot be fixed until Ben answers
[[validation]] §8.2 requires parameters fixed *before* testing, but the holding
period is still open (doc §11.3). Circular until answered. **Resolve:** Ben's
four questions above, holding period first.

### G11 — Survivorship bias may be unmeetable
[[validation]] requires delisted stocks in history; [[data-sources]] records
their coverage as unconfirmed. If SSI does not have them, the defence cannot be
met. **Resolve:** probe first; if absent, either find a second source or state
the bias explicitly in every reported statistic rather than ignoring it.

## Technical / factual, to resolve with data (not opinion)
These are not blockers; the blockers are in the section above.
- [ ] Everything under "NOT CONFIRMED" in [[data-sources]] — Phase 3 probe.
- [ ] Re-confirm current price-limit and T+2 rules against the exchanges
      (doc §5.6 says to); and the different rules in force 2012–2014.

Related: [[decisions]] [[data-sources]]

## Environment (session 01, runs 3-4 — verified, closed)
- [x] **uv works.** 0.12.17. `.python-version` pins the project to Python 3.12
      (uv had otherwise chosen 3.13, which is not what Ben specified).
      `uv sync`, `uv run pytest` (4 passed), `uv run ruff check`,
      `uv run ruff format --check` and `uv run pre-commit run --all-files`
      (7 hooks) all pass.
- [x] **Docker works.** Ben launched Docker Desktop and ran
      `docker compose up -d`. `vnstock-db` is up and healthy on port 5432,
      PostgreSQL 16.15 with the **timescaledb 2.30.1 extension already
      created** — no `CREATE EXTENSION` step is needed. The named volume
      `stock_assistant_vnstock-db-data` exists. The README's
      `docker compose exec db psql -U vnstock -d vnstock` command works as
      written.
- Note for future sessions: Docker Desktop puts its CLI in `~/.docker/bin`
      (added to PATH by `~/.zprofile`), not `/usr/local/bin`. A Claude session
      started *before* Docker Desktop's first launch will not see `docker` on
      its PATH; the binaries are at
      `/Applications/Docker.app/Contents/Resources/bin/docker` and
      `.../cli-plugins/docker-compose`.

Phase 2 environment is fully verified. Nothing outstanding here.
