# Validation discipline (doc §8)

**This is the section that decides whether the project is real.** With ~1,500
stocks × dozens of patterns × several filters × several holding periods there
are tens of thousands of combinations. By pure chance hundreds will look
excellent on history. Most are luck.

## The traps and their defences (§8.1)
| Trap | Looks like | Defence |
| --- | --- | --- |
| Overfitting | tuning thresholds until history looks great | fix parameters **before** testing; limit variations; record every variation tried |
| Multiple testing | testing 10,000 combos, celebrating the top 50 | demand stronger evidence the more combos were tried; confirm on unseen data |
| Look-ahead bias | using info not available on the signal day | signal at day *t* close → earliest entry day *t+1* |
| Survivorship bias | testing only today's listed stocks | include delisted stocks where data exists |
| Ignoring costs/rules | gains that vanish after fees, 0.1% tax, T+2, price limits | model all of them ([[context-vietnam]]) |
| Small samples | 80% hit rate from 10 occurrences | minimum occurrence count; fall back to group level |
| Regime change | worked 2012–2017, then stopped | report results year by year, never only in total |

## Testing sequence (§8.2)
1. **Split history** — e.g. 2012–2019 discover, 2020–2023 validate, 2024–now
   held back untouched.
2. **Discover** on slice one only.
3. **Validate** on slice two. Anything that collapses is discarded no matter
   how good it looked.
4. **Walk forward** — roll the window year by year; does the edge persist?
5. **Final check** on the untouched slice, **once**. Using it to tune anything
   destroys it.
6. **Paper-trade forward** for weeks to months: daily picks logged, nothing
   bought.
7. Only then consider small real positions.

## Metrics to report (§8.3) — win rate alone is not a metric
- Hit rate **vs base rate** (the edge).
- Average win vs average loss — 45% can be profitable, 65% can lose money.
- Expectancy per signal **after costs**.
- Maximum drawdown — can Ben tolerate it?
- Number of occurrences — how much evidence is behind the number.
- Stability by year and by market regime.

Rule of thumb from [[research-findings]]: if a result looks better than ~75%,
suspect a bug or a leak before celebrating.

Related: [[funnel-and-scale]] [[patterns]]
