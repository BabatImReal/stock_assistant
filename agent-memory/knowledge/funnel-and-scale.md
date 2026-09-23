# Funnel, per-stock statistics and scale (doc §7)

Two phases: a **research phase** run once and refreshed periodically, and a
**daily scan**.

## Research phase — the pattern library (§7.1)
1. Measure every pattern on every stock across history, with and without volume
   and context filters.
2. Measure **per stock**, not only globally — a big bank and a thin small-cap
   do not behave alike; some stocks obey patterns, some are noise.
3. Handle small samples honestly with a three-level fallback:
   **this stock → its group (sector / liquidity tier) → whole market.**
4. Keep only what clearly beats the base rate, with enough occurrences, and
   survives [[validation]].
5. Output: a table of strong pattern+context combinations, plus a behaviour
   profile per stock ("responds to volume breakouts, ignores hammers").

## Daily scan funnel (§7.2)
| Step | Filter | Remaining |
| --- | --- | --- |
| 1 | all listed codes | ~1,500+ |
| 2 | liquidity (min avg matched traded value), not suspended/warned | a few hundred |
| 3 | market regime — if the market is weak, raise the bar or pick nothing | same |
| 4 | did a strong pattern or money-flow signal fire today? | dozens |
| 5 | good track record **on this stock** (or its group)? | ~5–15 |
| 6 | context conditions met (trend, support, volume, sector) | a handful |
| 7 | rank by evidence strength, check news vetoes | **1 pick** + runners-up |

Step 2 is implemented (2026-09-23) as the point-in-time liquid set,
`data/universe.py`. On the latest session (2026-09-21) that is 280 symbols. In the
backtest, step 2 must use the liquid set ON EACH historical date
(`universe.liquid`), never today's list. Step 3's regime now includes breadth.
The §7.1 fallback group "this stock → its sector → whole market" uses the ICB
level-2 grouping (steel split out). Pooling may use CURRENT labels
(`data.sectors.current_groups`), but every pooled statistic must say so; sector
features themselves are quarantined (decisions.md 2026-09-23, B3).

## "Nothing today" is a valid answer (§7.3)
A tool that must produce a pick every day will eventually invent bad ones.
Waiting is part of the discipline.

## What a recommendation contains (§7.4)
- The stock and the signal that fired (pattern + volume + context).
- Its measured history: occurrences, hit rate **vs base rate**, average gain vs
  average loss, over which years.
- A risk-defined setup: reference entry, **stop level** (the price that says
  this was wrong), target zone.
- What would invalidate it (regime turn, negative news, volume dry-up).
- The runners-up and why they ranked lower.

## Scale — it is a small computing problem (§7.5)
~3,650 trading days from 2012, ~1,600 codes → **~4.5–5.5M daily candles**;
fingerprints (~100 measures/stock-day) ≈ 2 GB uncompressed. Weekly and monthly
candles are derived from daily, no extra download. This fits on a laptop;
detection takes seconds to minutes. **The months of work are in designing and
validating the rules, not in the computing.** Minute data would be ~200× larger
and is not needed for a 3–5 day horizon.

Automation: rules as a library (add a rule → it runs on all history) → one
batch computing all fingerprints → one batch computing all statistics → an
automatic behaviour profile per stock → **nightly update** of just the new day
→ periodic re-research every few months to see whether edges are fading.

## Data problems to solve before any of this is trustworthy (§7.5)
- How far back SSI daily data actually goes; whether **delisted** stocks are
  covered (survivorship bias — [[validation]]). A second source may be needed.
- **Price adjustment**: VN companies pay stock dividends and issue rights
  constantly, creating fake price gaps. History must be adjusted or patterns
  fire on events that never happened.
- Matched vs negotiated split available for the full history ([[money-flow]]).
- Stocks listed after 2012 lean on group-level statistics.
- Trading rules changed over the years → check results year by year.

Related: [[data-sources]] [[validation]] [[architecture]]
