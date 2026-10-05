# Chart formations, forward-only shadow track (v3)

Registered 2026-10-05, before any forward event was recorded. Frozen values:
`config/rules/chart_forward_v3.yaml`. This track runs beside the registered daily scan
and never changes it, the paper ledger or the E3 log.

## What is tested
The frozen v2 chart detector (double top/bottom as "repeated highs/lows", symmetric,
ascending and descending triangles; first close 0.5% beyond a contained wall) is run
every day on all stocks. Every confirmed first break is logged with its side (up or
down), including days with no events. Outcomes use the project's tradeable-return
engine: buy at the next open (no trade at the ceiling), sell at the close 10 sessions
after entry, 0.15% fee per side plus 0.1% sale tax (Ben confirmed the fee on
2026-10-05). Long-only: a down break is an observed event, never a short.

## Two hypotheses (the only decision-relevant ones)
- **H1:** a confirmed up-break has a higher net 10-session return than the same signal
  day's liquid comparator (excess_net_10 > 0).
- **H2 (avoid signal):** a confirmed down-break has a lower net 10-session return than
  the comparator (excess_net_10 < 0). It would say "do not buy a stock that just broke
  down", not "sell short".
Comparator = the same signal day's liquid stocks with a resolved, unflagged 10-session
outcome, so market moves cancel. Inference clusters by signal day, one-sided,
alpha 0.025 per hypothesis, looked at when 60, 120 and 240 events have resolved with
alpha 0.008 per look. No futility stopping. Final look: 240 resolved events or
2029-10-05. Hit rate vs the comparator's share, other horizons and variant x side cells
are reported but never decisive.

## How the hypotheses were chosen (disclosure)
H2 was chosen after I looked at pooled outcomes of all confirmed v2 breaks through
2026-09, which includes returns for 2024-2026 that the earlier Codex reports had
deliberately not summarised. That pooled look showed up-breaks about equal to the
market (hit 46.3% vs a 46.8% base) and down-breaks clearly worse (40.8% hit, -1.18%
mean net). **Those numbers are not evidence for anything and must not be cited as a
result**; they were the reason H2 was written down. Only forward events (signal day
after 2026-10-05) count. 2012-2023 and 2024-2026 remain spent.

## What "meaningful" means, defined before the data (minimum detectable effect)
Sd of one event's net 10-session return is about 8.2%. With ~40 usable events a year
per side (2014-2025 average, after liquidity and resolution gates):

| resolved events | at ~40/yr | detectable mean excess (80% power, alpha 0.008) | detectable hit-rate gap |
|---:|---:|---:|---:|
| 60  | 1.5 years | about 3.4% | about 21 points |
| 120 | 3 years   | about 2.4% | about 15 points |
| 240 | 6 years   | about 1.7% | about 10 points |

So this track settles only LARGE effects within 1-2 years and modest ones in many
years. It reports running estimates with intervals every week from the first
resolved event, labelled as accumulating evidence, not a result. The registered daily
scan's own paper ledger (about 30 scored signal days, earliest verdict around
January 2027) matures first.

## Rules of operation
Log rows carry the registration hash and are refused if it changed. A day is recorded
once; a later different answer for the same day is refused. Days recorded late show a
late `recorded_at`. Detection loads each symbol's bars from 2012, as the census did,
and is gated against the census (exact match on episode, variant, side and signal
day for 2026-01-01..2026-09-21) before the first forward day is recorded.
