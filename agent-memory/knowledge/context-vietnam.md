# Context and Vietnamese market rules (doc §5)

The same hammer means little in a quiet drift and a lot at support after a
sharp fall on heavy volume. **Context turns weak patterns into useful ones.**
Each context item is itself a rule that can be switched on/off and measured.

## Context measures
- **Trend before the pattern (§5.1):** price vs 20- and 50-day moving averages,
  slope of those averages, % change over 10–20 days. Reversal patterns need
  something to reverse — a "bottom" with no prior decline is not a bottom.
- **Support / resistance (§5.2):** zones where price repeatedly stopped falling
  or rising. Sketch rule: is today's low within ~2% of a low that held at least
  twice in the last 60 days? Bullish patterns *at* support and breakouts
  *through* resistance carry more meaning.
- **Market regime (§5.3):** VN-Index above/below its 50-day average; breadth
  (how many stocks rose). In Vietnam most stocks move together, so a perfect
  setup during a market-wide sell-off usually fails. Record the regime with
  every signal and report hit rates separately per regime.
- **Sector (§5.4):** banks, real estate, securities firms, steel move as
  groups. A signal with its sector is more credible than one against it.

## News (§5.5) — veto, not signal
VN investors react fast and hard; one bad headline can dump a strong stock.
News **overrides** patterns but is hard to predict with. Therefore:
- News never *generates* signals (at least initially).
- News acts as a **veto / warning**: a recommended stock with fresh negative
  news must be flagged in the report.
- A news-reading LLM agent comes later ([[architecture]]).

## VN rules that change the arithmetic (§5.6)
Any honest backtest must model all of these:

| Rule | Consequence |
| --- | --- |
| Daily price limits (±7% HOSE, ±10% HNX, ±15% UPCoM) | Cannot buy at the ceiling (trần) or sell at the floor (sàn). A backtest filling at the limit price is lying. |
| T+2 settlement | Shares arrive ~2 trading days later, so the earliest realistic sell is ~day 3. A 1-day edge is untradeable; the 3–5 day horizon fits. |
| Long-only for retail | Bearish signals are "avoid" / "sell what you hold", not trades. |
| Fees + 0.1% sale tax | Small average gains vanish after costs. |
| Liquidity | Thin stocks can show beautiful untradeable statistics. Enforce a minimum average matched traded value. |
| Retail-dominated, herd behaviour | Probably why patterns may work better here than in the US — and why news shocks are violent. |

Doc flags that **price-limit and settlement details must be re-confirmed
against current exchange rules before building**, and that 2012–2014 rules
differed from today's, so backtests apply the rules in force at each date and
report those years separately (doc §7.5).

Related: [[patterns]] [[validation]] [[funnel-and-scale]]

## Trading days (Ben, 2026-09-23)
The market is **closed on Saturday, Sunday and public holidays**, so a date
without data on one of those days is NOT missing data. Holidays include 1/1,
Tet (lunar, about a week, and the dates move every year), Hung Kings (10/3
lunar), 30/4, 1/5 and National Day 2/9. The government sometimes extends a
break by swapping in a working Saturday; for example, 2025-05-02 was closed.
- Missing data only means a **weekday session the market was open** and our data
  lacks. Never count weekends or holidays as gaps or as `gap_before`.
- The calendar (`trading_day`) is derived from stock rows, so closed days are
  absent by construction. The danger runs the other way: a stray row ON a
  closed day creates a phantom session (2025-05-02; see decisions.md
  2026-09-23). Weekends are rejected by a gate check. **Holidays have no check
  yet**, because there is no holiday list in config.
- Checked 2026-09-23: 0 weekend dates in the calendar, and none on 1/1, 30/4,
  1/5 or 2/9.
