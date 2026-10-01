# Vietnamese chart-pattern pilot — first census, not a trading signal

Run on 2026-10-01 from the preregistered price-only rules in `config/rules/chart_research.yaml` (commit `0bfdf5a`), detector commit `5a931f6`, and calendar-fix commit `d7b980f`. Promoted adjustment build 5; rules hash `714965cdc639e7ac`; final chart-code hash `f019f46d9336aa38`. The versioned artifact is `data/processed/chart_research/5_714965cdc639e7ac_f019f46d9336aa38/`. This is an isolated research path; it does not change the production scanner.

## What the census actually measured

The detector uses adjusted closes and causal, two-session-confirmed pivots. It records double tops/bottoms and symmetric/ascending/descending triangles as candidate episodes. A signal occurs only on the first observed close crossing a frozen boundary by 0.5%; the observed break can be **up or down regardless of the chart's name**. Formation gaps, factor breaks, excluded bars, and date-shifted bars terminate an episode. Outcomes use the existing tradeable-return engine at 3, 5, 10 (primary), and 20 sessions, with cost assumptions and `known_on` gating. The comparator is all stock-days on which the signal could be judged and the same return was eligible, not all raw rows.

Across the available 2012–2026-09-21 history: 2,511,070 symbol-day rows from 1,705 symbols were processed; 3,965 candidate episodes occurred on 844 symbols, and 2,770 episodes had a confirmed first break. These are **not** 2,770 independent or tradeable observations. Point-in-time liquidity, fillability, resolved outcome, and the 125-clean-session formation history narrow the evaluated samples. UPCoM fillability remains unverified and its outcomes are excluded by the existing gate. Broker fee is provisional. The event table retains direction, anchors, confirmation dates, expiry, and later failure dates for audit.

## Primary 10-session descriptive comparison

The two periods below are already seen by the project. They are useful for debugging and temporal comparison, **not fresh holdout evidence**. `n` is eligible, de-clustered pattern occurrences; edge is the pattern's net-positive hit share minus the same eligible market base. Both break directions are pooled because the registered trial was the named chart variant, not a side-specific strategy.

| Variant | 2012–19 n | 2012–19 edge | 2020–23 n | 2020–23 edge | 2020–23 provisional mean net return |
|---|---:|---:|---:|---:|---:|
| Double top | 50 | +4.86 pp | 37 | +1.37 pp | −0.98% |
| Double bottom | 50 | −1.14 pp | 48 | −6.23 pp | +0.99% |
| Symmetric triangle | 199 | −3.42 pp | 102 | −9.79 pp | −0.90% |
| Ascending triangle | 52 | −10.60 pp | 25 | −17.98 pp | −2.81% |
| Descending triangle | 82 | −0.80 pp | 41 | +3.68 pp | +0.02% |

The relevant market base rate was 47.14% in 2012–19 and 49.98% in 2020–23 at k=10. A positive edge is **not** proof of a useful pattern: the double-top hit edge is positive in both periods but its mean net return turns negative in the later period. The ascending-triangle result is an apparent negative association, not a validated short or avoidance rule. The 20 preregistered variant×horizon comparisons invite false discoveries; no new p-value or winning rule is claimed here.

## Audit finding and next decision

Direction cannot be inferred from a drawing's conventional label. In the full candidate table, 269 double-top episodes first broke **up** versus 113 **down**; 233 double-bottom episodes first broke **down** versus 86 **up**. The detector preserves these as observed outcomes rather than silently discarding inconvenient breaks. Because side-specific effects were not registered as a separate trial, mining them now would be exploratory and would require a new, fixed protocol before any future test.

Do **not** promote these five names to daily recommendations. First inspect a blinded sample of event charts against the recorded anchors and break dates, then register any revised geometry/direction rules as a new version. Reserve a genuinely untouched forward period for evaluation; previously viewed 2012–2023 results cannot be made fresh again by renaming a split. The 2024–2026 artifact was computed but its returns were deliberately not summarized here. Add money-flow/context only as separately registered hypotheses, after verifying matched-volume provenance. A stock report remains a later phase.
