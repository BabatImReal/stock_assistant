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

### G12 — CLOSED 2026-09-22: CafeF bulk volume is matched-only
**Tested, not assumed.** On the 20 stock-days with the largest negotiated deals
in the last quarter (deal = 64–88% of total), CafeF's bulk OHLCV volume equalled
matched-only 20/20 and matched+deal 0/20. On HDB 2026-08-19 the two answers
differ by 8×, so the result is unambiguous.

**Consequence: no scraper, no backfill, no SSI purchase is needed for volume.**
[[money-flow]] §4.3 is satisfied by the primary source.

**Second finding, and a correction.** The Phase 3 report claimed no bulk file
carried the split. That was wrong — it trusted the AmiBroker headers. The `NN_`
files do carry it: `<High>` = matched, `<Low>` = negotiated, 20/20 exact, and
`<High>` equals the OHLCV volume on 100% of rows every year 2012–2026. Caveat:
NN row coverage drops in recent years (46% of HSX stock-days in 2024, 73% in
2025), and a missing row means "unknown", not "no deal".

Superseded text below, kept for the record:

### (superseded) No free source has matched vs negotiated volume
**Found by the Phase 3 probe, 2026-09-22.** CafeF's CC_ files are order-book
supply/demand aggregates and its NN_ files are foreign flow; neither separates
matched (khớp lệnh) from negotiated (thỏa thuận) volume. vnstock's free tier has
neither. But "money flow uses MATCHED volume only" is a **non-negotiable
principle** in CLAUDE.md and [[money-flow]] §4.3, and it exists because a single
block deal can fake a day of accumulation.
**Ben's instruction 2026-09-22: TEST FIRST, then choose.** Before picking an
option, check whether CafeF's bulk volume is *already* matched-only — take 10–20
stock-days with large negotiated deals (identified from CafeF's per-stock history
page) and compare the bulk volume against matched-only and matched+deal.
- If it is matched-only, **G12 closes** and the principle is already satisfied.
- If not, plan a **polite one-time backfill of the split for all real tickers**
  (not only shortlisted ones) plus a nightly update, and show Ben the plan
  before building it.
The remaining fallbacks if the backfill proves impractical: accept total volume
with the limitation stated everywhere, or pay for SSI — the only confirmed
source of the split.

### G13 — Foreign flow stopped being published in the bulk files — DECIDED 2026-09-22
**Ben's decision: exclude foreign flow from all signals until a live source is
confirmed; recorded as a later layer.** The finding stands as below.

**Found by the probe.** In `CafeF.NN_*`, the columns carrying foreign data were
populated on ~95% of days through 2024 and have been **all-zero since January
2025**. So foreign flow (doc §4.4) exists for 2015–2024 and not for the present.
**Resolve:** confirm whether CafeF moved it elsewhere, before any signal is built
on a series that stops dead mid-history — a backtest would look fine and the live
scan would silently see zeros.

### G14 — The index file contains phantom weekend sessions
**Found by the probe.** VNINDEX has rows dated Saturday 2026-02-07 and Sunday
2026-03-08, with plausible values, on which no stock traded; 7 stock rows fall on
weekends too (2016–2017). Using the index as the trading calendar therefore
invents sessions, which shows up downstream as every stock "missing" days.
**Resolve:** derive the calendar from stock rows (or weekday-filter it) and
reject index rows with no matching stock activity.

### G15 — CafeF and vnstock disagree on adjustment policy — DECIDED 2026-09-22
**Ben's decision: CafeF is canonical. The VNM divergence is recorded as a policy
difference, not an error.** The finding stands as below.

**Found by the probe.** VNM differs by a constant 1.65% for every day from
2012-01-03 to 2019-09-13 and agrees exactly afterwards: one corporate action
around 2019-09-16 that CafeF adjusts for and VCI does not. Both series are
internally consistent; they encode **different definitions**. A pattern measured
on one is not measured on the other.
**Resolve:** decide which policy the project uses (proposal: CafeF, since the
adjusted ÷ unadjusted pair also yields the volume factor G1 needs), and treat a
constant-ratio divergence as an adjustment-policy difference rather than an
error — reconcile.py already surfaces it as a median ratio.

### G11 — Survivorship bias may be unmeetable
[[validation]] requires delisted stocks in history; [[data-sources]] records
their coverage as unconfirmed. If SSI does not have them, the defence cannot be
met. **Resolve:** probe first; if absent, either find a second source or state
the bias explicitly in every reported statistic rather than ignoring it.

## Technical / factual, to resolve with data (not opinion)
These are not blockers; the blockers are in the section above.
- [x] **Does any CafeF file separate matched vs negotiated (thỏa thuận)
      volume?** **NO** — probed 2026-09-22. The CC_ files are order-book
      supply/demand aggregates and the NN_ files are foreign flow; neither
      splits matched from negotiated. [[money-flow]] §4.3 is a non-negotiable
      principle with **no data behind it from any free source**. Escalated to
      blocker G12 below.
- [x] **Are delisted stocks included in the CafeF files?** **PARTIALLY** —
      82 HSX / 71 HNX / 309 UPCOM delisted 3-letter symbols are present, many
      with real history, but 37 of the 82 HSX ones have under 50 rows and 11
      have a single stub row dated 2015-09-01. A partial defence for blocker
      G11, not a complete one.
- [ ] Everything under "NOT CONFIRMED" in [[data-sources]] — Phase 3 probe.
- [ ] Re-confirm current price-limit and T+2 rules against the exchanges
      (doc §5.6 says to); and the different rules in force 2012–2014.


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

## For the nightly job design (session 02, run 5-6)

- [ ] **Suspension–resumption breaks factor-change detection.** Nightly detection
      treats a changed factor on a past day as a restatement. A symbol that stops
      trading keeps a frozen factor (68 symbols have a latest factor ≠ 1 for
      exactly this reason, none of them liquid). If such a symbol **resumes**,
      its whole factor series can shift at once and look like a mass
      restatement. Decide the handling before the nightly job is built: most
      likely, treat a symbol's first bar after a long gap as a new span and
      re-derive its factors rather than diffing them.
- [x] **Missed corporate actions — handled 2026-09-22.** Of 123 suspect events,
      **10 were repaired** by inferring the factor from a round stock-dividend
      ratio confirmed by a volume jump (build 5), and **113 were excluded** as
      unexplained, covering ~16,025 calendar days. The volume half of the test is
      weak evidence below ~20% dividend rates — it discriminates well for a 1:1
      bonus and barely at all for a 5% one, which is why only 10 of 123 passed.
      Worth revisiting with a real corporate-action calendar if one becomes
      available.
- [ ] Price limits and tick sizes in `config/rules/market_rules.yaml` are
      **unconfirmed** — the doc says to re-confirm against the exchanges
      (doc §5.6). They currently affect data-quality counts only, not backtests.

## Tools to evaluate later

### TypeSafe — Jev model (<https://docs.typesafe.ai>)
A fast, cheap model that answers **typed** questions — Choice, Score, yes/no —
and returns a confidence with each answer. The typed output is the interesting
part: it comes back as something code can branch on, rather than prose that has
to be parsed.

**Candidate uses**
- The **news-veto worker** (doc §5.5, §9.1). Classify Vietnamese news per stock:
  is it negative, what type of event, how severe — with low-confidence answers
  routed to review rather than acted on. News is a veto in this system, not a
  signal, so a wrong "negative" costs a missed opportunity and a wrong "fine"
  costs a bad pick; confidence gating fits that shape.
- Other backend or frontend **judgement** tasks where an answer has to be a
  value rather than a paragraph.

**Not for** numbers, dates, counting or pattern detection. Its own docs say to
keep those in code — which matches this project's non-negotiable principle that
deterministic code computes every number and the LLM only reads news and
explains ([[architecture]] doc §9, §10.3).

**Unknowns to test before trusting it**
- Vietnamese language quality. Unproven, and this is the whole use case.
- Resistance to manipulative rumour articles — a real hazard in a
  retail-dominated market where news moves prices hard (doc §5.5). A model that
  can be talked into "not negative" by a promotional piece is worse than no
  news layer.
- Access is **waitlist-only**.

**Status: parked.** Revisit after the core pipeline works. The news layer is
explicitly a later layer, and evaluating a model for it now would be building
the roof before the walls.

Related: [[decisions]] [[data-sources]] [[architecture]]
