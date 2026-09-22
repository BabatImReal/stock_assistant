# Data sources (doc §7.5)

**Status: CafeF and vnstock are CONFIRMED by a probe that ran on 2026-09-22
against the real sources.** SSI is paused. Everything marked CONFIRMED below was
observed in downloaded data, not read from documentation.

Probe: `scripts/probe_free_sources.py`. Raw files in `data/raw/cafef/<date>/`,
reports in `data/reports/` (both git-ignored).

---

## PRIMARY — CafeF bulk files
`https://cafef.vn/du-lieu/du-lieu-download.chn`. No account, no key, no rate
limit observed. Plain HTML page with direct links; the date is in each filename,
so the probe parses the newest date that has **all** wanted files rather than
hard-coding one.

### The five "Upto" (full-history) files
| Role | Zip | Contents | Size |
| --- | --- | --- | --- |
| stocks, adjusted | `CafeF.SolieuGD.Upto<DDMMYYYY>.zip` | `CafeF.{HSX,HNX,UPCOM}.Upto<d>.csv` | 50 MB |
| stocks, unadjusted | `CafeF.SolieuGD.Raw.Upto<DDMMYYYY>.zip` | `CafeF.RAW_{HSX,HNX,UPCOM}.Upto<d>.csv` | 38 MB |
| index | `CafeF.Index.Upto<DDMMYYYY>.zip` | `CafeF.INDEX.Upto<d>.csv` | 0.2 MB |
| supply/demand + foreign, stocks | `CafeF.CCNN.Upto<DDMMYYYY>.zip` | `CafeF.{CC,NN}_{HSX,HNX,UPCOM}.Upto<d>.csv` | 88 MB |
| supply/demand + foreign, index | `CafeF.CCNN.Index.Upto<DDMMYYYY>.zip` | `CafeF.{CC,NN}_INDEX.Upto<d>.csv` | 0.4 MB |

Page rows are labelled **Đã điều chỉnh** (adjusted) and **Chưa điều chỉnh**
(unadjusted = the `.Raw.` files).

### Format — CONFIRMED
AmiBroker/MetaStock import CSV: a UTF-8 **BOM**, then
`<Ticker>,<DTYYYYMMDD>,<Open>,<High>,<Low>,<Close>,<Volume>` (plus `<OI>` in the
CC/NN files). Read with `encoding="utf-8-sig"` or the first column name silently
becomes `﻿<Ticker>`. Prices are in **thousands of VND**.

### Coverage — CONFIRMED (file dated 2026-09-21)
| File | Rows | Symbols | Earliest |
| --- | --- | --- | --- |
| HSX | 1,543,953 | 2,535 | 2000-07-28 |
| HNX | 921,422 | 379 | 2001-07-16 |
| UPCOM | 872,379 | 1,126 | 2002-01-21 |
| INDEX | 11,460 | 3 (VNINDEX, HNX-INDEX, +1) | 2000-07-28 |

History goes back **far past the 2012 window** the project needs. Of HSX's 2,535
symbols only **474 are 3-letter stock tickers**; the other 2,061 are covered
warrants (`CACB2101`…) and must be filtered out.

### CONFIRMED findings
- **Adjusted ÷ unadjusted close gives the exact corporate-action factor**, as
  the doc hoped. It is a step function, flat between events.
- **CafeF does NOT adjust volume.** Adjusted-file volume equals unadjusted-file
  volume on 100% of days. Blocker **G1 is real and this source will not solve
  it**: volume must be divided by the price factor ourselves.
- **Delisted stocks ARE included, partially.** 82 HSX / 71 HNX / 309 UPCOM
  3-letter symbols stopped trading before 2026, and many carry real history
  (RDP 3,554 rows to 2024-11, GMC 4,321 rows to 2025-01). But coverage is
  uneven: 37 of the 82 HSX ones have under 50 rows, and 11 symbols
  (ATA, CYC, GTT, KSS, KTB, PTK, PXL, TTP, VLF, VNA, VNH) have a **single row**
  dated 2015-09-01 — stubs, not history. **Partial defence against
  survivorship bias (blocker G11), not a complete one.**
- **Exchange transfers destroy history (blocker G4, now proven).** ACB appears
  only in the HSX file, starting **2020-12-14**, its HOSE transfer date. Its
  ~9 years of HNX history is in **no** CafeF bulk file. vnstock has it.
- **The index file contains phantom weekend sessions.** VNINDEX has rows on
  Saturday 2026-02-07 and Sunday 2026-03-08 with plausible values, and no stock
  traded on either. 7 stock rows fall on weekends too (2016–2017). The trading
  calendar must be derived from stock rows, or weekend-filtered, not taken from
  the index file as-is.
- **CORRECTION (2026-09-22, G12 test): the bulk files DO carry the matched vs
  negotiated split.** The Phase 3 probe said they did not. That was wrong — it
  read the AmiBroker headers at face value. See "The split" below.

### The split — CONFIRMED, and the bulk files have it
**CafeF's bulk OHLCV volume is MATCHED-ONLY.** Tested on the 20 stock-days in the
last quarter with the largest negotiated deals (64%–88% of total volume):
bulk volume equalled matched-only on **20/20** and matched+deal on **0/20**. On
HDB 2026-08-19 the two candidate answers differ by 8× (7.07M vs 59.6M), so the
test is not marginal.

So [[money-flow]] §4.3 — money flow uses matched volume only — **is already
satisfied by the primary source**, with no scraper and no workaround.

The negotiated series is available too, from `NN_<Low>`, but its **coverage is
patchy in recent years**: rows exist for 97–100% of HSX stock-days in 2012–2020,
then 92% (2021), 80% (2022), 89% (2023), **46% (2024)**, 73% (2025), 100% (2026).
Where a row exists it is exact; where it is missing, deal volume is unknown
rather than zero — a distinction that matters if it is ever used as a filter.

### CC_ and NN_ files — what they actually hold
Every file reuses the same AmiBroker header, so the column *names* mean nothing;
only the values identify them. Findings:
- `NN_*`: **`<High>` = matched volume (khớp lệnh), `<Low>` = negotiated volume
  (thỏa thuận)** — identified by matching values against CafeF's per-stock page
  on 20 large-deal days, 20/20 exact for both. `<High>` equals the OHLCV volume
  on 100% of rows every year 2012–2026 (99.8% in 2023).
  **`<Open>`, `<Close>`, `<Volume>` and `<OI>` have been all-zero since January
  2025** — populated through 2024 and then stopped. Those were the foreign-flow
  columns, so **foreign flow (doc §4.4) exists historically but is dead in the
  current files** (blocker G13, excluded by Ben's decision).
- `CC_*` (cung cầu / supply-demand): order-book aggregates — order counts and
  values on the buy and sell side — not a matched/negotiated split.
- Old rows (2006–2007) carry identical placeholder values across different
  symbols, so early CC/NN data is not trustworthy.

---

## REFERENCE — vnstock (free community tier)
`pip/uv add vnstock` (4.0.2 tested). Docs: <https://vnstocks.com/docs>.

```python
from vnstock import Quote

Quote(source="vci", symbol="VNM").history(
    start="2012-01-01", end="2015-12-31", interval="1D"
)
```

### CONFIRMED
- **No API key needed.** `VNSTOCK_API_KEY` is optional; registering raises the
  rate limit.
- Sources: `vci`, `kbs`, `msn`, `fmarket`. Default is **KBS**; **VCI works
  best** and is what the probe uses. Columns: `time, open, high, low, close,
  volume` — no foreign flow, no block trades, as the doc said.
- **vnstock returns ADJUSTED prices.** Determined by comparison, not assumed:
  it matches CafeF's adjusted file on 87.8% of days and its unadjusted file on
  1.5%.
- **It has ACB's pre-2020 history** that CafeF lost, and reaches 2011-10-21.

### Two traps, both found the hard way
1. **The 8-year cap is STATEFUL.** One request longer than 8 years truncates
   *every later call in the same process* to the last 8 years — silently, with a
   warning but no error. It reads exactly like "there is no history before
   2018". Fetch in **4-year chunks** and never make a long request first.
2. **Unregistered access is 20 requests/minute, not 60.** Exceeding it aborts
   the run rather than backing off. The probe waits 4s between calls. A free
   `VNSTOCK_API_KEY` raises this to 60/min.

---

## Reconciliation result — CONFIRMED (2012-01-01 → 2026-09-22, 5 symbols)
Tolerances: 0.5% on price, 1% on volume (reasoning in `reconcile.py`).

| | CafeF adjusted vs vnstock |
| --- | --- |
| close | **87.80%** of 16,098 days within 0.5% |
| volume | **99.79%** within 1% |
| days only in CafeF | 0 |
| days only in vnstock | 2,507 (almost all ACB pre-2020) |

Per symbol: FPT 99.97%, SSI 99.86%, HPG 98.91%, ACB 100% (only 1,435 days
exist), **VNM 47.68%**.

### KNOWN POLICY DIFFERENCE — no further action (Ben, 2026-09-22)
Three symbols disagree with vnstock by a near-constant ratio over a long span,
then agree exactly afterwards. That is two different answers to "is this event
adjusted for", not corruption, and **CafeF is canonical** (decision 2026-09-22):

| Symbol | Span of the divergence | Ratio |
| --- | --- | --- |
| VNM | 2012-01-03 → 2022-01-19 | ~0.9835 |
| MBB | 2012-01-03 → 2022-01-20 | ~1.08 |
| PNJ | 2012-01-03 → 2022-01-19 | ~1.031 |

All three resolve in January 2022. Every other symbol tested is 98.9–100%.
**Consequence to remember:** those three symbols' pre-2022 history will not match
a chart drawn from any other source. Nothing is broken; it is a different
definition. `reconcile.py` already separates this case from corruption by
reporting the median ratio of the mismatches.

**VNM is one explained divergence, not corruption.** Every day from 2012-01-03
to 2019-09-13 differs by a constant ratio of **0.9835** (1.65%), and after that
they agree exactly. One corporate action around 2019-09-16 that CafeF adjusts
for and VCI does not. HPG has 39 scattered small differences, all in 2012.

Volume disagreements (34 of 16,098) cluster on shared dates — 2022-01-19/20,
2024-03-06, 2015-10-02 — the same days across all five symbols, so they are
session-level anomalies, not a definitional difference about block trades.

---

## PAUSED — SSI FastConnect (revisit when the system is proven)
Kept, not deleted: registration costs money and nothing is paid for until the
system proves effective (doc §7.5, decision 2026-09-22). Nothing below was ever
verified — no credentials were ever obtained.

| Endpoint | Useful fields (from published docs) | Notes |
| --- | --- | --- |
| **DailyStockPrice** | OHLC, average price, **adjusted close**, ref/ceiling/floor, **matched volume & value**, **negotiated (deal) volume & value**, **foreign buy/sell volume & value**, foreign room | symbol optional → whole market per request; 10 pages × 1,000 rows |
| DailyOhlc | OHLC + matched volume/value | 30-day range limit |
| DailyIndex | index value, advances/declines, matched vs deal volume | market regime and breadth |
| SecuritiesDetails | listed shares, first/last trading date | listing dates |

**Why it still matters:** SSI is the only known source that carries the
**matched vs negotiated split** — a non-negotiable principle ([[money-flow]]
§4.3) that the free sources cannot satisfy. If that layer turns out to be
essential, this is what it costs.

Related: [[money-flow]] [[funnel-and-scale]] [[open-questions]] [[decisions]]
