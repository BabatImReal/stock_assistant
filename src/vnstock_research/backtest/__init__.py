"""Measurement: what actually happened after each pattern, and whether it matters.

Doc §2 (pattern → detection → measurement) and §8 (validation discipline).

This is the module that turns a shape into a signal. For every flag, look
forward: did the close rise after 3 and 5 days, how far did it run at best and
at worst, did it reach a target before a stop.

**The number alone is meaningless.** A 58% hit rate is worth nothing if the
stock rises on 55% of all comparable windows anyway. Every statistic is reported
against the stock's own **base rate** over the same period; the edge is the
difference (doc §2).

**Sample sizes are small** (doc §6.3, §7.1). A pattern may fire only a few dozen
times on one stock in fifteen years. Statistics fall back in three levels:
this stock → its group (sector or liquidity tier) → the whole market.

**The defences matter more than the results** (doc §8), because with ~1,500
stocks × dozens of patterns × several filters, hundreds of combinations will
look excellent by pure chance:

- No look-ahead: signal at day *t* close, earliest entry at *t+1*.
- Parameters fixed before testing, and every variation tried is recorded.
- Split history: discover → validate → one untouched holdout.
- Walk forward year by year; report stability by year and by market regime.
- Model the Vietnamese rules and costs every time: ±7/10/15% price limits
  (you cannot buy at the ceiling), T+2 settlement, fees, 0.1% sale tax.
- Report expectancy after costs and maximum drawdown, not just win rate.
- Anything above ~75% is a bug or a leak until proven otherwise (doc §6.1).

Blocker before the first statistic is computed — see open-questions.md G3: the
document's "3 and 5 days from the signal day" is not the return that can
actually be traded once entry is *t+1* and T+2 applies. The definition has to be
settled first.
"""
