# Open questions

## For Ben (doc §11.3)
- [ ] Holding period to optimise for: 3 days, 5 days, or "until target or stop"?
      Blocking: [[validation]] §8.2 requires parameters fixed *before* testing.
- [ ] Minimum liquidity — which stocks are too small to consider (VND/day)?
- [ ] Risk tolerance — what losing streak / drawdown is acceptable in paper
      trading?
- [ ] Is "no pick today" acceptable on most days, or is a daily pick expected?
- [x] ~~SSI FastConnect credentials~~ — **SUPERSEDED 2026-09-22.** SSI is
      paused (cost); the project runs on CafeF + vnstock. See [[data-sources]].
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

### G1 — IMPLEMENTED 2026-09-22: volume is adjusted by the inverse factor
`bar_adjusted.matched_volume = raw_volume / factor`, and the
**traded-value invariant** check proves it on every row: adjusted close ×
adjusted volume must equal raw close × raw volume. It currently passes on all
2.88M rows. Backfilled spans cannot be adjusted (no factor derivable) and carry
`volume_is_adjustable = false`.

Original finding, kept for context:
Doc §7.5 adjusts OHLC by the ratio *adjusted close ÷ close* for stock dividends
and rights, but says nothing about volume. Volume must be adjusted by the
inverse ratio or RVOL, sustained volume and every other measure in
[[money-flow]] break across every corporate action — and VN companies pay stock
dividends constantly. **Resolve:** decide and document the volume adjustment
rule; verify against a known 2:1 stock-dividend case in the probe data.

### G2 — Restatement detection: NOT IMPLEMENTED (verified in code 2026-09-22)
**Status checked against the source, not assumed.**
`scripts/nightly_update.py:248` contains `restated = False` with the comment
"today's own rows are new, so nothing to compare yet", and line 250 logs
`restatement detected: {restated}`. The job therefore **reports a check it does
not perform**. It computes factors for the new session's rows only; it never
re-derives past factors from the fresh CafeF files, and never diffs them
against the stored series.

Consequence: when CafeF applies a new corporate action, every past factor for
that symbol changes in the source and **nothing notices**. The adjusted series
goes stale and research keeps reading it. The misleading log line should go at
the same time as the fix — a log that claims a check ran is worse than no log.

The surrounding machinery already exists (versioned `adjustment_factor`,
`adjustment_build`, `research_result.build_id`, and a rebuild path proven by
`repair_missed_actions.py`). What is missing is the comparison and the trigger.

Original framing, kept for context:

The original worry was SSI re-stating its adjusted close. It now applies to
CafeF, and the answer is partly built: the factor is derived from CafeF's
adjusted/unadjusted pair, so when CafeF applies a new corporate action every
past factor for that symbol changes, and `bar_adjusted` must be rebuilt under a
new `build_id`.

**Still open, and it is the nightly job's core loop:** compare the newly
computed factor series against the stored one, treat any change on a past day as
a restatement, and rebuild rather than patch. The machinery exists
(`adjustment_build`, versioned `adjustment_factor`, `research_result.build_id`);
the detection does not. **Resolve when step 4 is built.** Note the
suspension-resumption trap below — a resuming symbol's whole series can shift at
once and look like a mass restatement.

### G3 — CLOSED 2026-09-22: definition approved and implemented
The document measures 3 and 5 days forward **from the signal day t**. That is
not a number anyone can trade: entry cannot happen before t+1, and settlement
means the shares are not sellable immediately.

**Approved definition** (implemented in `backtest/forward_returns.py`):

    signal      at the close of day t
    entry       at the OPEN of day t+1        (first price available after the
                                               signal; no look-ahead)
    earliest    t+1 plus the settlement cycle in force on t+1
    exit        (T+3 before 2016-01-01, T+2 after -- see market_rules.yaml,
                 currently marked UNVERIFIED)
    return_k    close(t+1+k) / open(t+1) - 1, for k >= settlement_days

    All days counted as TRADING sessions from the calendar, never calendar days.

Consequences worth stating before approval:
- The doc's 3-day and 5-day horizons both survive: with T+2, k=3 and k=5 are
  both sellable. With T+3 (before 2016) k=3 is the earliest possible exit, so
  pre-2016 results at k=3 sit exactly on the boundary and should be reported
  separately.
- Entry at the open, not the close, means the signal day's close is never used
  as an entry price — the look-ahead trap in doc §8.1.
- A window may not span a gap in trading (CLAUDE.md) or an `excluded_window`.
- Price limits still bite: if t+1 opens at the ceiling, the fill is not
  realistic. **Open question for Ben:** reject such entries, or record them
  with a flag and report both? I lean towards rejecting, since the funnel can
  simply pick another day.

### G4 — DONE 2026-09-22: counted, stitched and backfilled
116 Class A symbols (CafeF kept both spans) — transfer gaps now excused from the
missing-session count, derived from `symbol_exchange`. 251 Class B symbols
(pre-transfer history dropped), of which **46 of the 47 liquid ones were
backfilled** from vnstock: 47,334 bars, ACB recovered 14.1 years. The 204
illiquid ones are deliberately skipped (see [[decisions]]).

Original finding, kept for context:
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

### G6 — CLOSED 2026-09-22: no longer applies
The paging cap was an SSI API constraint. CafeF publishes the whole market as
bulk files — one 176 MB download for all history, ~55 KB nightly — so there is
no paging at all. Re-opens only if the project ever returns to an API.

### G7 — Market regime: filter or reported dimension?
Stated both ways: a funnel filter in doc §7.2 step 3 ("if the whole market is
weak, raise the bar"), and a dimension reported alongside every signal in §5.3
("report hit rates separately for good and bad market conditions"). These are
different designs and the second is strictly more informative. **Resolve:** pick
one with Ben; recommend measuring as a dimension and only then deciding whether
it should also filter.

### G8 — SETTLED 2026-09-22: store from 2000, measure from 2012
Ben's decision. CafeF gives HSX from 2000-07-28 at no extra cost, so the raw
years are kept and the research window can widen later without a re-download.

Original finding, kept for context:
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

### G14 — IMPLEMENTED 2026-09-22: calendar comes from stock rows
`trading_day` is built from `bar_raw`, never the index, and weekend index rows
are rejected at parse time. A related defect turned up while implementing it:
CafeF also dates whole STOCK sessions late (214 HNX bars on Saturday
2023-08-26 are Friday's session). Those are moved back when the target date is
free, verified against vnstock, and flagged `date_shifted`.

Original finding, kept for context:
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

### G11 — Survivorship bias: PARTLY MET, rewritten for CafeF (2026-09-22)
Not unmeetable, but not fully met either. Measured, not assumed:

- Delisted symbols **are** present: 82 HSX, 71 HNX, 309 UPCOM 3-letter symbols
  stopped trading before 2026, many with real history (RDP 3,554 rows to
  2024-11, GMC 4,321 rows to 2025-01).
- Coverage is uneven: 37 of the 82 HSX ones have under 50 rows, and 11 have a
  **single stub row** dated 2015-09-01.
- The exchange-transfer backfill improved matters for 46 liquid symbols, but it
  was deliberately limited to liquid names, so 204 illiquid Class B symbols
  still start late.

**Resolve:** state the residual bias in every reported statistic rather than
claiming it is handled, and re-check whether a delisted stock's final months are
present (a collapse that stops being recorded is the exact case this defends
against).

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

- [x] **Suspension–resumption — DECIDED and implemented in the nightly job.**
      A first bar after a long gap starts a new span and its factors are
      re-derived, not diffed. Original note:
- [ ] ~~**Suspension–resumption breaks factor-change detection.**~~ Nightly detection
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

## Next feature slice — breadth and the point-in-time universe

Deferred from §5.3 deliberately (Ben, 2026-09-22): it is foundational enough to
deserve its own slice rather than riding in with index regime, because it
discharges part of **G11** (survivorship) and implements the **point-in-time
liquid universe** decision at the same time.

- Advancers vs decliners must count only the symbols **actually trading on that
  date**, not today's listed set. Counting over today's universe is
  survivorship bias applied backwards.
- **Direction must be computed on the ADJUSTED close.** On an ex-dividend day
  the raw price drops by the dividend, and a raw comparison would record a
  market-wide fake decline on exactly the days most companies pay.
- The same point-in-time machinery is what the liquid-universe decision needs,
  so building it once, properly, serves both.
- **PROPOSED 2026-09-23**, decisions locked by Ben, **BUILT 2026-09-23** on
  branch `features/breadth-pit-build` (session 2026-09-23-03 run 3). Awaiting
  Ben's review before merge. See decisions.md.
- Not built, on purpose: a second breadth measure over the liquid universe
  (optional per Ben). Add it when a study needs it.

## Index and calendar findings — 2026-09-23 (session 03)

The 5 VNINDEX sessions are resolved (see decisions.md, session 2026-09-23-03):
2025-05-02 phantom (calendar fixed), 2024-05-17 and 2026-07-02 index gaps
(backfilled), 2018-01-23/24 real HOSE halt (left, explained). The gate check
`index_covers_every_trading_session` will keep warning **2**; both are explained.

New, found while resolving them. NOT fixed this run:

### Nightly-hardening slice — WORKED 2026-09-23 (run 6, `features/nightly-hardening`)
- **G16**: FIXED. The nightly writes the session's index rows (tested).
- **G17**: FIXED. Seam-rescale provenance (migration 008) plus a narrow
  exemption; the gate re-run passes (build 5 stays 'good').
- **Holiday list**: DONE. `config/rules/holidays.yaml` (121 verified dates) +
  2 blocking checks. **Must be extended each year** from the HOSE/SSC
  announcement.
- **Snapshot scheduling**: DONE. Every nightly run snapshots ICB (idempotent).
  NOTE: the nightly itself is still not scheduled (cron/launchd): Ben's call.
- **2026-07-31**: FIXED. CafeF stale copies, repaired from VCI with KBS
  agreeing (also HNX 2023-05-08).
- **Historical exchange labels**: BUILT on `features/exchange-labels` (runs 7 +
  9), awaiting review. X4 unanswered, so raw is left as filed. See below.

### Exchange labels — residual and findings (2026-09-23, run 9)
- **Residual (flagged, quarantined): 6.43% of liquid stock-days since 2012**
  (57,738 / 897,588); 8.12% of all research-window stock-days
  (203,823 / 2,511,101). By cause, in liquid days:
  - no usable KBS date (delisted / OTC / empty, or contradicted): 29,773
    (294 symbols);
  - vnstock backfill, pre-transfer (G4 Class B): 15,492 (46 symbols);
  - CafeF-filed before the KBS listing date: 12,473 (52 symbols).
- **G4 gap (the DPG kind)**: 174 symbols have a KBS move inside their research
  history. 86 are covered by G4 Class A, 36 are G4 Class B backfills, and
  **52 were never seen by G4**: CafeF re-filed their whole history under
  the new exchange (DPG, ITA, DAG, SJF…). Their pre-move days are now
  flagged.
- **Undetectable case, residual risk**: a transfer CafeF re-filed entirely AND
  for which KBS reports the original listing date looks like "never moved" to
  both sources. At the 16/95 rate seen among Class A, roughly a dozen such
  symbols may exist. **Tripwire**: the gate's price-limit violations on DATED
  days (4,572), a move beyond the dated exchange's limit.
- Three stray one-day HOSE filings on 2015-09-01 (PXL, VLF, VNA) inside UPCoM
  spans are dated UPCoM (the longer span wins).
- **X4 (for Ben)**: re-derive `bar_raw.exchange` / the `trading_day` split from
  the resolved exchange, or keep raw as filed (current)?

### G20 — DETECTED AND EXCLUDED 2026-09-24 (run 17); the factors themselves are NOT repaired
`checks.factor_triage` sorts the 1,818 into: 1,305 resumptions (already gaps),
2 legitimate new-exchange first days, and **511 genuine defects on 313
symbols**. Each defect blanks every feature and return window across it, like
a gap (`factor_break`).
- Liquid k=3 outcomes lost: 82 of 874,390 (0.009%).
- Rows now reasoned `factor_break`: 118 liquid k=3.

Still open: REPAIR (re-derive the factors, or a new build) and a gate check.
Ask Ben.

Original finding:
The first real returns build showed BNA +114% to +136% over 3 sessions on HNX.
The cause is build 5's factor: on 2021-10-07 the raw close fell 67.9 → 38.7
(a corporate action), but the factor jumped 0.1668 → 0.6189. That is a +111%
step in the ADJUSTED series, which should be continuous.

Whole market since 2012 (excluding backfilled rows): **1,818 stock-days on
525 symbols** where the adjusted close moves more than 2x the daily limit on
a day the factor changed. Some are legitimate: a resumption band can reach
20/30/40%. The rest are candidate factor defects.

No gate check looks at this. The price-limit check excuses every
factor-change day.

Effect: a return window crossing such a day is wrong. 292 k=3 returns exceed
±60%: 265 are UPCoM (quarantined), and 27 are not (penny-stock ticks like ACM
are legitimate).

**Resolve:** a gate check on adjusted moves beyond the band in force; then
exclude or repair (excluded_window / a new build). Ask Ben before any build
change.

### G19 — The price-limit check's factor tolerance is below CafeF's rounding jitter (found 2026-09-23)
The check skips a day as "factor changed" when |Δfactor| ≥ 0.000001. CafeF's
factor is adjusted/raw close on 2-decimal prices, so it jitters by more than
that with no corporate action. Of 2.47M day-pairs since 2012 on CafeF bars, only
63.8% are within 1e-6, while 99.5% are within 0.1% (relative) and only 0.5%
move ≥ 1% (real actions). So about 36% of day-pairs are never examined, and the
warning (4,572 + 955) UNDERCOUNTS. A relative tolerance (e.g. 0.1%) would fix
it. Not changed: it moves a gate number outside the exchange slice; Ben's call.

### G18 — The nightly does not update negotiated volume or the symbol master (found 2026-09-23)
Its docstring promised both (step 4), next to the index. Only the index (G16)
and the calendar are written. Negotiated volume is not read by any measure (a
money-flow rule keeps it out), but the data-quality check and the future
foreign/deal analysis read it. The symbol master's `last_trade_date` /
`is_active` go stale. The docstring now says so honestly. Not fixed: out of
this run's scope.

### Pre-2012 repeated index sessions (report only)
14 index rows from 2002–2009 repeat the previous session's OHLC (e.g. VNINDEX
2008-05-27..29). They are outside the research window and not investigated.

### G16 — FIXED 2026-09-23 (was: the nightly job never writes `index_bar`)
`scripts/nightly_update.py`'s docstring says step 4 updates "the index" and it
has a regex for `CafeF.Index.*.zip`, but no code inserts into `index_bar`. It
hasn't done damage yet (`job_run` has 1 row, `no_new_data`). But the first
nightly run that appends a day will leave VNINDEX missing for that day, so the
regime measures will be NaN on exactly the date the daily scan needs. Same shape
as G2: a step the job advertises and does not do. Must be fixed before the
nightly job is scheduled.

### Index value disagreements with vnstock (reconciliation principle)
- **2026-07-31**: CafeF VNINDEX 1744.66 vs vnstock 1735.78 (0.51%, over the
  0.5% tolerance); HNX-INDEX 275.05 vs 271.25 (1.40%). Not explained. Per
  CLAUDE.md it should be flagged and excluded until explained. Needs a third
  source or Ben's view.
- **2026-07-03 → 07-15**: CafeF's index closes are rounded to whole points
  (e.g. 1862.0000 vs 1862.08). Within tolerance, but a sign that CafeF's
  index file for that span is lower-precision.
- Everywhere else checked (2024-04 → 06, 2026-06 → 09), close/high/low agree
  exactly.

### HNX-INDEX has 33 missing sessions since 2012
Including a run 2024-11-26 → 12-06. Not read by any measure today
(`features.yaml` market.index_symbol = VNINDEX). Needs the same diagnosis
before HNX-INDEX is used for anything.

### G17 — FIXED 2026-09-23 (was: the promoted build 5 FAILS a blocking gate check)
Re-running the gate read-only on 2026-09-23:
`factor_never_above_one_in_research_window` → **15,670 factors > 1 since 2012**
(fail). All of them are `source='vnstock'`, on 21 symbols, factor 1.02 → 2.02.
Build 5 passed this check at its last stored gate run (2026-09-22 09:56, 0
rows). The rows come from `scripts/check_backfill_seams.py` (session
2026-09-22-02 run 9), which multiplies a whole backfilled span by the seam ratio
and stores the product as the factor. The gate was not re-run after that.
The rescale is by design, and the check's "factor ≤ 1" assumption does not hold
for it. **Consequence:** the nightly job would now refuse to promote any new
build. **Decision for Ben:** exclude `source='vnstock'` factors from this
check (and give seam factors their own bound check), or reconsider storing the
rescale as a factor. Not changed this run.

### Exchange-day file losses
- **2025-05-05 HNX**: only 1 HNX symbol (CEO) in bar_raw for a real session
  (both indices have the day). About 200 HNX symbols lost that session, so
  their windows are NaN around it. Backfillable from vnstock; not done.
- The gate's `sessions_have_a_plausible_number_of_symbols` (warn) counts days
  like this but does not name them.

### `exchange` is the CURRENT exchange, not the one in force on the date
`bar_raw.exchange` and the backfilled `symbol_exchange` spans use today's
listing. ACB is recorded as HOSE for 2006–2020, but it was on HNX until 2020-12.
CafeF's RAW_HSX file carries DPG trading on 2018-01-23 while HOSE was halted.
So `trading_day`'s per-exchange split is unreliable historically. This matters
for any per-exchange breadth or universe (Task 2 proposal) and for G4.

## Sector (doc §5.4) — S1–S6 decided, BUILT 2026-09-23 on `features/sector-build`
The proposal is in session 2026-09-23-03, run 4; Ben's decisions are in
decisions.md (run 5). The key limitation stands: **ICB membership is
CURRENT-ONLY before the first snapshot (2026-09-23)**. Every historical sector
value is flagged and quarantined (see B3). Dated membership accrues only as
snapshots are taken, which needs scheduling (in the nightly-hardening list).

## Patterns tranche 4 — for the broker friend (2026-09-23)
- Liquid rates: tight_range 8.71%, inside_day_run 2.67%, higher_lows 1.26%,
  breakout (20-day high close) 5.60%; 64.6% of breakouts have rvol >= 1.5.
  tight_range at 8.7% is frequent at the doc's 60% threshold; does he mean
  something tighter? Is two inside days in a row his idea of an inside run?

## Patterns tranche 3 — rare patterns (2026-09-23)
- Liquid rates: morning star 0.14% (878 events), evening star 0.22%, three
  white soldiers 0.21%, three black crows 0.43%, three inside up 0.61%,
  three inside down 0.45%. **A morning star fires about 3 times per stock in
  14 years**, far below `reliability.min_occurrences_per_stock` (30). So
  three-candle statistics will almost always fall back to the sector (current
  labels, noted) or the whole market. The backtest must SAY which level each
  number came from.
- For the broker friend: star_body_max 0.3 and max_wick_to_range 0.25 are
  our choices (doc §3.3 gives no numbers).

## E4 (2026-09-24, run 19) — notes for Ben
- The look-alike pool stops before 2024 until the holdout is run
  (`pool_before`). After the holdout, should `pool_before` move to the query
  day? That would be a change to the neighbours block, so it would need a new
  version.
- The avoid candidates on validate: 5 of 8 kept a negative sign (dark cloud
  cover + support + rvol, inside-day run + support, breakout + rvol k5,
  hammer + support k5, breakout k5). The 3 evening-star variants flipped
  positive. Exploratory only.

## E3 results — questions for Ben (2026-09-24, run 18)
- **Negative-edge survivors:** 8 discover survivors did WORSE than the base
  ("avoid" signals). The validate rule as written (edge ≥ +3 pts, net > 0)
  can never pass them. Should avoid-signals get their own validate rule
  (same sign, |edge| ≥ 3 pts)? It would be registered as an ADDITION and could
  only be tested on unused data.
- **Nested survivors:** the 16 held hypotheses overlap heavily (e.g. five
  marubozu_red + rvol_high variants). They are about 5 families, not 16
  independent edges.
- **The p-value floor:** 2,000 resamples give a minimum p of 0.001, so BH can
  reject only once ≥ 16 hypotheses reach it. This is conservative; it was
  pre-registered and was not changed.
- **Validate has no significance test:** the rule is sign + size + expectancy
  only (the top held one has validate p 0.11). As registered.
- **"Bearish" labels behave bullishly:** three_black_crows / marubozu_red +
  high rvol lead the held list (doc §6.3 lesson 5). A broker-friend question.

## Analysis engine — A1–A12 ANSWERED 2026-09-24 (approved as proposed + five additions; decisions.md run 16). E1 built.
- **Environment (FIXED run 17):** `shm_size: 1gb` in docker-compose.yml; the container was recreated. Originally: the recreated DB container had Docker's default 64 MB /dev/shm. A
  whole-market parallel hash join failed with "could not resize shared
  memory segment". Workaround: `SET max_parallel_workers_per_gather = 0` in the
  heavy queries. A fix would be `shm_size` in docker-compose.yml (an
  environment change; ask Ben first).

Horizons (G10), the hit definition, the middle fallback level (liquidity tier vs
sector), min occurrences de-clustered, the split years, FDR + validate
thresholds, the hypothesis vocabulary, the kNN spec, the reference price (the
ex-date adjusted prev close; UPCoM average-price reference UNVERIFIED), the
storage helper, MFE/MAE now vs target/stop later, and accepting the
ceiling-rejection bias. Full text: logs/sessions/2026-09-23-session-03.md run 15.
- **B1 correction (found run 15):** `checks.py` has NO ceiling-price function
  to reuse. Its limit logic is violation-counting SQL, so B1 needs a new shared
  `limit_prices()` in checks.py plus a Python/SQL agreement test.

## Patterns tranche 5 (fingerprint) — for Ben (2026-09-24)
- **Code hash in the manifest** (my addition): any edit under `data/`,
  `features/` or `patterns/`, even a comment, makes the stored fingerprint
  refuse to load until it is rebuilt (~20 min). Safe but strict. Keep it, or
  narrow it to the measure functions?
- **Every stock, not only liquid**: the table holds all 1,705 symbols since
  2012; the point-in-time liquid filter is applied at research time. OK?
- **Traditional direction labels** (report only): marubozu green/red,
  higher_lows and breakout are labelled bullish/bearish; the hammer shapes,
  doji, tight_range and inside_day_run have none. A broker-friend question too.
- **Rebuild speed**: ~20 min single-threaded; market/sector values are still
  recomputed per symbol (0.12 s of 0.68 s). Only worth changing if the
  fingerprint becomes a nightly step.

## Patterns tranche 2 — for the broker friend (2026-09-23)
- Liquid rates: engulfing 2.40% / 2.36%, harami 4.48% / 3.89%, piercing
  0.63%, dark cloud 0.84%. Does he treat an engulfing of a tiny prior body
  as real? (The floor removes half of them.)
- Harami: the doc requires a LONG first day, but not today's colour; does he?

## Patterns tranche 1 — for the broker friend (2026-09-23)
- **`doji` fires on 10.95% of liquid stock-days** (19.07% without the tick
  floor), with the doc's loose-end threshold body <= 10% of range. That is
  high for a signal. Not tuned (fixed before measuring); ask whether he
  means 5%.
- hammer_shape 5.03%, inverted_hammer_shape 3.59%, marubozu green 5.15% and
  red 5.59% of liquid stock-days. Ask which of these he actually watches.

## For the backtest step — recorded 2026-09-22, DO NOT act on these yet

These are review findings about work already done. They belong to the backtest
step, not to features, and are written down so they are not rediscovered late or
assumed handled.

### B1 — Two different price-limit definitions exist in the codebase
`data/checks.py` computes the limit properly: the **limit in force on that date
plus one tick**, with the wider **first-day / resumption bands** applied. But
`scripts/measure_fillability.py` and
`backtest/forward_returns.is_at_ceiling` / `is_at_floor` use a plain
`prev_close × (1 ± limit)` with a flat 1.5 VND tolerance — **no tick rounding
and no first-day band**.

The exchange rounds the ceiling *down* to the tick, and 1.5 VND is smaller than
one tick on every exchange, so genuine ceiling and floor bars on higher-priced
stocks are **under-detected**. ~~The measured fillability rates (0.133% of
liquid bars rejected at entry, 0.342% deferred at exit) are approximate and
slight undercounts.~~ **CORRECTED 2026-09-24 (run 16): not slight. With the
tick-rounded limit, liquid entries at the ceiling are 0.929% and exits at the
floor 2.272%, about 7x the old figures.**

**RESOLVED 2026-09-24 (run 16):** `checks.limit_prices` is the one definition
(Python + `limits_sql`), used by the gate, fillability and
measure_fillability; the flat-epsilon helpers are deleted; a live test asserts
Python == gate SQL. STILL TO CONFIRM against the exchange rulebooks: the
ceiling rounds DOWN and the floor UP, to the tick of the limit price itself;
one tick from the reference when rounding lands on it; UPCoM's reference is
the previous AVERAGE price (so UPCoM fillability is flagged).

**When the backtest applies fillability per trade it must reuse `checks.py`'s
tick- and first-day-aware logic, not the simplified helper.** Consider
consolidating both onto one shared limit function so the two cannot drift again.

### B3 — Sector features are EXPLORATORY: quarantine them (decided 2026-09-23)
Every sector value resting on a borrowed (pre-snapshot) label carries a
`flag__<measure>` column, and `FeatureSet.flagged` lists the measures. The
backtest MUST run results through `features.base.quarantine_flagged` before
reporting anything as validated; flagged sector features are exploratory only.
The §7.1 fallback may pool on current labels (`data.sectors.current_groups`),
but it must SAY it pooled on current labels.

### B2 — BUILT 2026-09-24 (run 16, E1): `forward_returns.outcomes` + storage
Kept for context (the original finding):

### B2 — The return generator is not written
`backtest/forward_returns.py` is **primitives only**: `earliest_sell_offset`,
`valid_horizons`, `net_return`, `is_at_ceiling`, `is_at_floor`, `load_costs`.

Not yet written, and not to be assumed done:
- computing `return_k` over the adjusted series for real bars,
- deferring an exit onto the next session that does not close at the floor,
  with the 5-session cap and the flag,
- enforcing the CLAUDE.md rule that **no pattern window or forward-return
  window may span a gap in trading**, including the `excluded_window` spans.

All three belong to the backtest step.

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

## The holdout (2026-09-24, run 20) — for Ben
- **The broker fee is now decisive.** 5 of the 9 rejects become ACCEPT at an
  all-in round trip of 0.10% and 4 at 0.25%; none of the 6 accepts flips down
  to 0.10%. The break-even of the accepts is 0.57–1.21% all-in. The verdict
  stays on the registered 0.40%. Please confirm your real fee.
  - **Update 2026-09-24 (session 2026-09-24-01):** Ben does not know his fee.
    Research (context-vietnam.md) shows the realistic range is 0.16% all-in
    (a zero-commission broker still passes on 0.03% a side) to 0.60% (0.25%
    a side). 0.10% is below any real broker, so "zero-fee" means 0.16%. At
    0.16%: 10 accept (4 rejects flip). At 0.60%: 5 accept
    (higher_lows+breadth+ma50, break-even 0.57%, drops out). These are read
    off the break-even column, which is exact because NET is linear in the
    gross. **Open: which broker Ben will use.**
  - **Open: run `describe-holdout` on Ben's machine.** The code is built
    (run 5 of session 2026-09-24-01), but the cloud session has no DB, so
    the avg win/loss, drawdown and losing-streak numbers are NOT computed
    yet.
- **The weak accepts.** 3 of the 6 pass the rule on 34–49 occurrences with p
  0.09–0.64 (the rule does not require significance). How should G9 (ranking
  to one pick) weigh them against the 2 that are both accepted and
  significant?
- **2026.** Several survivors are weaker or negative in 2026 (by_year in the
  report). Watch this, don't tune.
- `pool_before` for the look-alikes can now move past 2024, since the holdout
  is spent. That is Ben's call, and it needs a new neighbours version.

## After the holdout description (session 2026-09-24-01, run 7) — for Ben
- **The unit of the test (architectural, Ben decides).** The registered rule
  measures per trade; the daily scan bets per day. The two marubozu accepts
  lose or break even per day (validation.md). Should G9 and any future
  registered test measure the one-pick-a-day result (per signal day)? It
  cannot be re-tested on the spent holdout, only on new data or paper
  trading.
- ~~Check the extreme trades.~~ RESOLVED 2026-09-24 (run 21): the report now
  names them, and GKM / HVN / NTP / MCO were checked against raw prices and
  factors. They are real floor-lock and limit-up runs, not data errors.
- **Drawdown vs profit.** Even the best per-day idea (k3
  breakout+volume_dry: +30.5% of a stake over 2.7 years) fell 34% (basket)
  to 45% (bad one-pick path) on the way. Higher_lows: +19.8% vs −41% to −71%.
  At 100M VND a trade with overlapping positions, that is a small reward for
  the pain and capital. The fee swings it hard (higher_lows +63% at 0.16%,
  −16% at 0.60%).
- **Branch cleanup (run 21):** `claude/great-bell-6wr1jq` was merged into
  `features/analog-backtest` (fast-forward). Deleting it locally and on
  origin was blocked by the permission guard. Ben can delete it:
  `git branch -d claude/great-bell-6wr1jq && git push origin --delete claude/great-bell-6wr1jq`.

## After the daily scan (session 2026-09-23-03, run 22) — for Ben
- **G9 ANSWERED** by Ben's registered tie-breaker (`daily_scan` in
  protocol.yaml). **The unit question is ANSWERED too**: paper trading is per
  signal day (`paper_trading`).
- **Tier numbering.** data.universe: tier 1 = LEAST liquid, 3 = most. Your
  instruction said "tier 1 = most liquid"; the block prefers the more liquid
  tier. Confirm that is what you meant.
- **Eligibility at T:** UPCoM and undated-exchange stocks are not proposed,
  because the holdout's gate never measured an accepted signal on one.
  Confirm.
- **Running it daily.** The forward record needs, after every session:
  1. `nightly_update`;
  2. `fingerprint.build` (~20 min);
  3. `forward_returns.build`;
  4. `report.scan`.

  Then `report.paper score`. Nothing is scheduled.
- **STUCK proposals** (a placed stake with no return) withhold the verdict
  until you rule on them.
- The fee: while it is PROVISIONAL, no PASS/FAIL is declared.
- RESOLVED 2026-09-24 (run 24): the exchange key stays FIRST (Ben
  confirmed). Still open: the tier direction wording, the UPCoM/undated
  exclusion, the fee, and running the daily pipeline.

## After batch complements_1 (session 2026-09-23-03, run 25) — for Ben
- **151 paper-trading candidates, 49 display families; NONE materially
  stronger than the best of the six.** Adding any to the forward test needs a
  new `daily_scan` version (Ben's call). It should happen before forward rows
  exist, or the forward record is split by rule version.
- **Many candidates are near-duplicates of registered hypotheses.** Some
  complements are near-universal: `not_at_support` in 54 candidates,
  `not_volume_dry` in 40, `not_rvol_high` in 32. For example,
  marubozu_red+ma_50_rising+not_at_support ≈ marubozu_red+ma_50_rising.
  The genuinely new region is the WEAK MARKET (`not_market_up`, 13
  candidates).
- Validate needs no significance: 28 of 151 have validate p < 0.05.
- Discover's one SUSPICIOUS result (k3 three_black_crows+not_ma_50_rising
  +rvol_high, hit 76.5% on 68) held on validate at a normal 58.4%.

## After batch structural_1 (session 2026-09-23-03, run 26) — for Ben
- **236 more paper-trading candidates, none materially stronger** than the
  six or the complements_1 candidates.
  - Relative strength and stage 2 (an uptrend) carry the structural signal.
  - Stage 1 (basing) and stage 4 (declining) produced NO candidates:
    reversal-in-a-downtrend setups do not hold.
- The structural fingerprint must be rebuilt (`python -m
  vnstock_research.structural`, ~24 min) whenever build 5 changes, like the
  registered one. It is not in the daily pipeline.
- Hypotheses ever tested: 8,442 (1,554 + 3,864 + 3,024). Each batch's FDR
  is within its own N; across batches there is no correction. That is why
  every survivor is only a candidate.
