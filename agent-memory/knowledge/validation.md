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

## How the project applies this — the analysis engine (approved 2026-09-24)
Design approved by Ben (A1–A12 + five additions; decisions.md run 16):
- **Outcomes** live in their own table (`backtest/forward_returns.py`), never
  in the fingerprint. Each carries `known_on`, the actual resolution date. A
  past row is evidence for day T only if its known_on < T.
- **Split:** 2012–2019 discover / 2020–2023 validate / 2024→freeze holdout,
  with an embargo at each boundary. The holdout RULE is pre-registered, and
  the holdout is used once, with Ben.
- **Multiple testing:** a pre-registered hypothesis vocabulary with every
  hypothesis logged (N known); BH-FDR q = 0.10 in discover; then on validate
  the same sign + a minimum edge + net > 0. The discover → validate SURVIVAL
  count is reported.
- **Hit** = net > 0. NET numbers are stamped PROVISIONAL (fee 0.15% not
  confirmed). The base rate is taken on the identical population. Fallback:
  stock → PIT liquidity tier → market, ≥ 30 de-clustered.
- **Quarantine:** flagged features AND flagged fillability (undated exchange,
  UPCoM) never enter a validated number. UPCoM is 11.8% of liquid outcomes.
- **Built:** E1 (limits + returns + storage).
- **Next:** E2 (the gate + base rates), E3 (hypotheses + protocol), E4 (kNN).
