# What the research actually says (doc §6)

## Ignore the marketing numbers (§6.1)
Websites quote 95% for cup-and-handle, 89% for head-and-shoulders. Those come
from cherry-picked examples and loose definitions. **Anyone quoting 90%+ is
selling something.** Serious backtesting guides say be sceptical above ~75%.
If our own numbers ever look that good, assume a bug or overfitting first.

## Academic findings (§6.2) — mixed, with one useful shape
| Study | Market | Finding |
| --- | --- | --- |
| Marshall, Young & Rose (2006) | US, Dow 30 | 28 candlestick patterns: no real edge over a decade |
| Caginalp & Laurent (1998) | US, S&P 500 | some three-day patterns had short-term predictive power |
| Lu & Shiu (2012) | Taiwan | several bullish reversal patterns profitable |
| Chen, Bao & Zhou (2016) | China | harami and homing pigeon most accurate; engulfing only useful <2 days |
| Tharavanij et al. (2017) | Thailand | even filtered, most patterns could not predict direction |
| Ahlawat (chart patterns) | cross-section | no chart pattern gave significant profits |

**Reading:** patterns fail in large, efficient, professional markets and
sometimes work in smaller, retail-heavy, less efficient ones. Vietnam is much
closer to Taiwan/China than to the US. That is a reason to **test**, not to
believe — Thailand is also an emerging market and showed mostly nothing.

## Practical lessons to build in (§6.3)
1. Realistic hit rates are **55–65%**, not 90%. Still profitable if average win
   > average loss after costs.
2. **Multi-candle beats single candle.**
3. **Volume confirmation raises hit rates** in nearly every test → [[money-flow]].
4. **Context beats pattern**: a mediocre pattern well filtered beats a perfect
   pattern in isolation → [[context-vietnam]].
5. **Direction labels can be wrong** — one practitioner backtest found "bearish"
   engulfing behaving bullishly, repeatedly. Measure the label.
6. **Most patterns fire rarely** — a few dozen times in 15 years on one stock,
   too few to trust. This is exactly why per-stock stats need group and market
   fallbacks ([[funnel-and-scale]]).

## What it means for us (§6.4)
The value is not knowing the patterns (public) but measuring them honestly on
Vietnamese data, per stock, with Vietnamese rules and costs, plus the broker
friend's context judgement. Nobody offers that to a VN retail investor.

Related: [[validation]] [[patterns]]
