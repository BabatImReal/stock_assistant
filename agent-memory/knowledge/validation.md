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
- **Built:** E1 (limits + returns + storage), E2 (the gate + base rates +
  fallback, G20 factor defects blanked like gaps), E3 (the protocol).
- **E3 results:** N = 1,554 → 1,454 testable → **82 passed
  discovery** (BH q = 0.10, date-block bootstrap) → **16 held on validate**.
  The held list is led by "bearish" patterns behaving bullishly
  (three_black_crows / marubozu_red + high rvol), and it forms ~5 nested
  families.
- **E4 built:** a look-alike search, ILLUSTRATIVE only. Its own registered,
  frozen block; the pool goes through the gate, is resolved before the query
  day, and until the holdout is run stops before 2024. The 16 held survivors
  are displayed as 6 families; the 8 negative-edge survivors are shown as
  exploratory avoid candidates.
- **THE HOLDOUT (run once, 2026-09-24):** 2024-01-01 → F = 2026-09-10.
  - **F:** the session before the first entry with a pending outcome, so
    every outcome is final; the rows still pending are floor-locked exits,
    which dropping would have flattered.
  - **16 → 6 ACCEPTED, 9 REJECTED, 1 not testable.**
  - Honest reading:
    - only 2 accepts are also significant (p 0.022, 0.007: two marubozu_red
      + rvol variants);
    - 3 accepts rest on 34–49 occurrences with p 0.09–0.64;
    - 8 rejects kept a positive edge but net ≤ 0 at the registered 0.40%,
      and 5 of them flip at a zero-fee broker (0.10%).
  - The edge in hit rate mostly persists; whether it pays depends on the
    fee.
  - Nothing tuned after.

## Finding: per-trade expectancy is not what a daily pick earns (session 2026-09-24-01, run 7)
The holdout judged the MEAN NET PER TRADE, so every trade counts once. The
daily scan puts ONE stake on each signal day. Those are different averages:
the per-trade mean beats the per-day mean exactly when days with MORE
signals have BETTER outcomes. That is arithmetic, not a guess:
trade mean = Σ n_d m_d / Σ n_d; day mean = Σ m_d / D.

In the holdout description (`research/reports/holdout-2026-09-10-describe.txt`):

(Corrected 2026-09-24, run 21: an earlier table put the SUM over all trades,
one stake per trade, beside one stake per day. That compares different
amounts of money. The fair comparison is the average per stake:)

| accepted | avg per trade | avg per signal day | signal days |
| --- | --- | --- | --- |
| k3 breakout+volume_dry | +0.67% | +0.74% | 41 |
| k3 breakout+above_ma50+volume_dry | +0.44% | +0.38% | 33 |
| k3 three_black_crows+breadth+rvol | +0.81% | +0.12% | 38 |
| k3 higher_lows+breadth+ma50 | +0.17% | +0.11% | 180 |
| k3 marubozu_red+breadth+rvol | +0.77% | −0.02% | 160 |
| k5 marubozu_red+ma50rising+rvol | +0.27% | −0.43% | 275 |

The two "significant" marubozu accepts earn their edge on CROWDED days (many
stocks firing together, and whether those are sell-off-then-rebound days is a GUESS, not checked).
Followed as one stake a day, one is flat and the other loses more than a
stake. The breakout ideas (about 1 signal a day when they fire, and rare: 41
days in 2.7 years) are the ones whose per-trade and per-day results agree.
- **Lesson:** a result must be measured in the unit the strategy trades in.
  For a one-pick-a-day scan, that unit is per signal day, not per trade.
- **Do NOT** turn "trade marubozu only on crowded days" into a rule and
  trust it: it was seen on the holdout, so it is a NEW hypothesis for data
  not yet used (paper trading).
- **The extreme trades are real (checked 2026-09-24, run 21, raw prices +
  factors):** GKM 2024-09-19 (−57.7%: ten −10% floor days on HNX, factor
  1.0), HVN 2024-07-16 (−30.7%: −7% floors on HOSE, flat factor), NTP
  2024-05-17 (+36.8%: a real limit-up run), MCO 2024-02-29 (a real
  rebound). They are not missed corporate actions.
