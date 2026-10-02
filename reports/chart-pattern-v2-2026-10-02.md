# Vietnamese chart-pattern v2 — contained formations, observed break side

This is a **descriptive research census, not a trading signal or a validation result**. Ben approved requiring every adjusted close from the first through last anchor to stay within the eventual frozen pattern walls. The existing repeated-level (1.5%) and triangle (1%) tolerances apply to that interval; the v1 0.5% no-early-break rule still applies from the last anchor through candidate confirmation. A rejected formation cannot suppress a later valid episode. V1 and the production scanner remain unchanged.

The v2 protocol was fixed in `config/rules/chart_research_v2.yaml` (commit `03c5105`) before side-conditioned returns were inspected. The implementation and failing-before regression check were committed as `1772550` before this full census. The registered family is five variants × observed first-break side (up/down) × 3/5/10/20-session horizons: **40 trials**, with 10 sessions primary. A chart's conventional name does not determine its break direction. The outcome is a *long-only*, net-positive return after the existing provisional cost model, compared with all eligible stock-days under the same point-in-time gate. A down break is not a tested short-sale return.

## Reproducible census

Run `uv run python -m vnstock_research.chart_research_v2` to rebuild the v2 episodes and print all 80 period-specific cells (40 registered trials in each of two historical periods). On adjustment build 5, the research artifact is `data/processed/chart_research_v2/5_92c387181435be5a_9ef457b528d8d70f/` (rules hash `92c387181435be5a`, code hash `9ef457b528d8d70f`). Its manifest records 2,511,070 signal rows across 1,705 symbols and 3,172 candidate episodes across 796 symbols: 1,133 confirmed up, 1,167 confirmed down, 577 late/unobservable, 155 expired, 131 interrupted, and 9 still forming. It reuses v1's version-checked forward-return artifact without altering it. The three out-of-wall audited triangles (VAT, NAB, DVP) no longer appear under their v1 episode IDs.

The two slices below, 2012–2019 and 2020–2023, were **already viewed** in v1. Neither is a fresh holdout for v2. The table shows every registered side at the primary 10-session horizon. `n` is the eligible, de-clustered occurrence count (equal to raw count in these cells). Edge is the long-only net-positive hit rate minus the eligible market base rate, in percentage points. Mean net return is provisional and is not the edge. The base rates are 47.14% (2012–2019; 190,572 eligible stock-days) and 49.98% (2020–2023; 182,582 eligible stock-days).

| Formation / observed break | 2012–19 n | 2012–19 edge | 2020–23 n | 2020–23 edge | 2020–23 mean net |
|---|---:|---:|---:|---:|---:|
| Double top / up | 37 | +4.21 pp | 21 | +2.40 pp | +0.19% |
| Double top / down | 9 | +8.42 pp | 15 | +3.35 pp | −1.85% |
| Double bottom / up | 14 | −11.42 pp | 18 | +11.13 pp | +2.74% |
| Double bottom / down | 33 | −1.68 pp | 26 | −11.52 pp | +1.03% |
| Symmetric triangle / up | 74 | −6.60 pp | 43 | −15.10 pp | −0.83% |
| Symmetric triangle / down | 87 | −2.31 pp | 45 | −3.31 pp | −0.77% |
| Ascending triangle / up | 26 | −0.98 pp | 8 | +0.02 pp | −0.76% |
| Ascending triangle / down | 16 | −3.39 pp | 13 | −19.21 pp | −3.56% |
| Descending triangle / up | 50 | +10.86 pp | 14 | +21.45 pp | +2.74% |
| Descending triangle / down | 23 | −21.05 pp | 18 | −5.54 pp | −2.20% |

## Interpretation and next gate

Several cells have fewer than 20 eligible occurrences in the later period. The apparently favourable descending-triangle/up cell has only 14 there; its 40-trial family and already-seen data make selection especially hazardous. Other cells change sign across periods, and hit-rate edge can disagree with mean return. Nothing here establishes that a pattern predicts Vietnamese stocks, or warrants a daily recommendation. UPCoM fillability remains excluded under the existing gate; broker fees remain provisional.

Keep v2 research-only. Next, have a broker/domain reviewer inspect the fixed sample and a *new*, outcome-blind sample of contained v2 formations for recognizable geometry and Vietnamese trading-rule realism. Freeze any corrections as v3 before another outcome review. Then collect genuinely prospective observations and evaluate the entire registered family with multiplicity control, costs, fillability, stock-level fallback, and a no-signal option. Do not relabel 2012–2023 or already-computed 2024–2026 outcomes as an untouched holdout. Rectangles, flags, money-flow combinations, stock-strength reports, and scan promotion remain separate later decisions.
