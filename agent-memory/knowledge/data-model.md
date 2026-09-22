# Data model (Phase 4) — **APPROVED by Ben 2026-09-22**

Two ideas everything rests on:

1. **Raw is permanent; adjusted is disposable.** We store exactly what CafeF
   published and never edit it. Everything adjusted is derived and can be
   rebuilt in minutes. A new corporate action can therefore never corrupt the
   record — it only changes a derivation we redo.
2. **Absent is not zero.** A missing negotiated-volume row means *unknown*, not
   *no block trade*. Designed in: no row, rather than a `0`.

## Tables

| Table | Key | Why |
| --- | --- | --- |
| `symbol` | `symbol` | 3-letter tickers only. CafeF's HOSE file has 2,535 symbols but only 474 are stocks; the rest are covered warrants. Without this filter every base rate is 4× too big. Listing/delisting dates come from observed data. |
| `symbol_exchange` | `symbol, valid_from` | Exchange is a *period*, not a field (blocker G4). Also identifies which symbols need the backfill. |
| `bar_raw` | `symbol, trade_date` | **The permanent record.** Unadjusted OHLC + matched volume, append-only, with `source`/`source_file` provenance. Rebuilds everything else. |
| `adjustment_factor` | `symbol, trade_date, build_id` | adjusted close ÷ unadjusted close — CafeF publishes both files, and their ratio *is* the corporate-action factor. |
| `bar_adjusted` | `symbol, trade_date, build_id` | Rebuildable. Price × factor, **volume ÷ factor** (blocker G1 — CafeF adjusts price but not volume, verified identical on 100% of days). |
| `negotiated_volume` | `symbol, trade_date` | From `NN_<Low>`. A row with 0 = CafeF said no block trade; **no row = unknown**. Coverage 97–100% (2012–2020) but 46% (2024). |
| `trading_day` | `trade_date, exchange` | Built from stock rows, never the index (blocker G14 — the index file has rows on Saturday 2026-02-07 and Sunday 2026-03-08). `symbols_traded` makes a half-dead session visible. |
| `index_bar` | `symbol, trade_date` | VN-Index / HNX-Index, weekend rows rejected. Needed for market regime (doc §5.3) and funnel step 3. **Approved by Ben.** |
| `reconciliation_run` | `run_id` | when, sources, range, tolerances, match rate, pass/fail. |
| `reconciliation_mismatch` | `run_id, symbol, trade_date, column` | both values, relative difference, **and the ratio** — a constant ratio is a policy difference, scattered is corruption. |
| `research_result` | `result_id` | **Every research result records the `build_id` it was measured on** (Ben, 2026-09-22), so any number can be reproduced later. |

Built-in correctness check: **traded value is invariant under adjustment** —
`adj_close × adj_volume` must equal `raw_close × raw_volume`, because the factor
cancels. The best single test that G1 was done right.

At ~2.5M rows plain PostgreSQL would suffice; TimescaleDB costs nothing and is
already running, so we keep it. Chunk by year.

## Pipeline

**(a) One-time historical load, back to 2000**
download the five Upto zips (kept permanently) → `bar_raw` from the `RAW_`
files → `adjustment_factor` from adjusted ÷ raw → `negotiated_volume` from
`NN_` → `index_bar` (weekends rejected) → `trading_day` from stock rows →
`symbol` + `symbol_exchange` → `bar_adjusted` → **checks + reconciliation
sampled across every year** → promote the build only if all pass.

**(b) G4 backfill for transferred symbols**
Find them → register the vnstock key **first** (60/min vs 20/min) → fetch in
**4-year chunks**, never one long request (the 8-year cap is stateful and
truncates silently) → store with `source='vnstock'`.

*Consequence Ben accepted:* vnstock returns **adjusted prices only**, so for
backfilled spans we cannot recover the unadjusted price, cannot compute a
factor, and therefore **cannot adjust volume**. Those spans are usable for
**price-based patterns and trend**; **volume-based signals are disabled on
them** and the flag must travel with the data.

**(c) Nightly**
download the **daily** files (~55 KB, not 176 MB) → append to `bar_raw` →
compute today's factor **and check whether any past factor changed** (that is
how a new corporate action announces itself) → if so, new `build_id` and rebuild
`bar_adjusted` → update the rest → **checks + reconciliation** → promote only if
all pass.

**Reconciliation scope:** the **liquid universe nightly**, where "liquid" is a
**config value** (minimum average matched traded value) not a hard-coded number,
**plus the full market weekly**.

**On failure:** nothing is deleted and nothing is silently accepted. Raw is
always kept. The failing build is **not promoted** — research and the daily scan
keep reading the last good build, and the report says plainly that the data is
stale and why.

## Re-adjustment policy
1. `bar_raw` never changes — a corporate action does not alter what traded.
2. Factors are **versioned and append-only**; a new event creates a new
   `build_id`.
3. `bar_adjusted` is a **rebuild, not an edit**.
4. **Every research result records its `build_id`**, so a number measured under
   build 7 stays interpretable once build 8 exists.
5. Re-adjustments are logged: which symbols changed and by how much. A factor
   that changes on a day with no corporate action is a bug, not a dividend.

We keep old *factors* (tiny), not old *bars* (large), because bars regenerate
from raw + factors.

## Checks that must pass before research uses any data
Structural: expected files present; row counts in a sane band; no duplicate
`(symbol, trade_date)`.
Per bar: `low ≤ open, close ≤ high`; prices positive; volume ≥ 0; day-on-day
*unadjusted* move within the price limit + tolerance (violations are the
signature of an unadjusted corporate action).
Adjustment: **traded value invariant**; factor = 1.0 on the latest day and never
above 1; factor changes only on plausible event dates.
Coverage: plausible symbol count per trading day; missing sessions per symbol
*inside its listed range*; `NN_<High>` equals matched volume wherever an NN row
exists (100% expected — a drop means the format changed).
Cross-source: reconciliation passes its thresholds **sampled across every year**;
a constant-ratio divergence is recorded as policy, scattered divergence fails.
Universe: 3-letter tickers only.

Related: [[data-sources]] [[money-flow]] [[validation]] [[decisions]]
[[open-questions]]
