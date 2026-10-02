# Independent broker-style review of chart-pattern v2

This is a skeptical research review, **not a licensed broker opinion, a stock recommendation, or evidence that a chart pattern predicts Vietnamese shares**. I reviewed the fixed v1 chart sheets only through their event dates as illustrations; they are not a visual sample of v2. I did not inspect or summarize 2024–2026 returns.

## 1. Are the formation labels recognizable?

### Takeaway
The triangle names describe plausible *close-based converging geometry*, but the double-top/bottom names are too strong as unqualified reversal labels. Call these “repeated-high/low formations” until prior trend and clean reversal context are independently established.

### Cited Findings
- The detector uses five alternating, two-right-session-confirmed **adjusted-close** pivots for triangles, connects high and low pivots with log-price lines, and classifies slope combinations. It does not use intraday highs/lows or volume. — [v1 geometry, lines 97–112 and 164–211](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/chart_research.py#L97); [v1 registration, lines 16–37](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/config/rules/chart_research.yaml#L16)
- A “double top/bottom” requires only high-low-high or low-high-low, peaks/troughs within 1.5%, a 5% middle swing, and 22–120 sessions separation. The 60-session prior trend is **labelled** `reversal_context`, `other`, or `unknown`, but never required for admission. — [v1 geometry, lines 120–161](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/chart_research.py#L120); [v1 registration, lines 21–28](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/config/rules/chart_research.yaml#L21)
- In common chartist usage, a double top is a reversal after a meaningful prior uptrend and is completed by a break below the intervening trough; a double bottom reverses a prior downtrend and completes above the intervening peak. A triangle is judged after a valid break, with volume and prior trend often used as context. These are practitioner conventions, not a guarantee of efficacy. — [StockCharts double top](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/double-top-reversal); [StockCharts double bottom](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/double-bottom-reversal); [StockCharts symmetrical triangle](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/symmetrical-triangle)
- The fixed v1 outcome-blind audit identified DCT/DPS as range-like and VAT/NAB/DVP as out-of-wall triangles; it explicitly said the sample was not a market-wide defect estimate. I viewed those fixed sheets and agree that DCT/DPS read more like repeated trading levels than textbook two-turn reversals. — [geometry audit, lines 3–17](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/reports/chart-pattern-geometry-audit-2026-10-01.md#L3); [DCT sheet](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/data/reports/chart_audit_v1/double_top.png); [DPS sheet](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/data/reports/chart_audit_v1/double_bottom.png)

### Inferences
- V2's full-formation containment fixes the particular wall breach but cannot by itself distinguish a double reversal from a range, or establish accumulation/distribution from price alone. The five names should be understood as algorithmic geometry-family labels, not broker-certified chart calls.

### Gaps
- No fixed, outcome-blind **v2** chart sample has been inspected here, so I cannot estimate the fraction of v2 episodes a human would recognize or certify any individual v2 episode.

## 2. Are containment, confirmation, and break sides actionable?

### Takeaway
The event clock is sensible for research: a signal occurs only after a causally known close outside a frozen wall. That is not yet an executable or strong signal; it lacks a volume filter, magnitude/time persistence test, and a declared risk/exit action.

### Cited Findings
- V2 tests each close from first through last anchor against the **eventually frozen** upper/lower walls with 1.5% repeated-level or 1% triangle tolerance. A candidate that fails is skipped before it could block a later episode. — [v2 registration, lines 16–26](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/config/rules/chart_research_v2.yaml#L16); [v2 detector, lines 55–69 and 168–179](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/chart_research_v2.py#L55)
- The existing 0.5% rule rejects closes already outside after the last anchor and before candidate confirmation. An active formation is confirmed by the **first** close more than 0.5% beyond a wall; `late_or_unobservable`, expired, interrupted and still-forming episodes do not become side flags. Failure is recorded on a later day, not retroactively removed from the initial signal. — [v2 detector, lines 95–149 and 206–252](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/chart_research_v2.py#L95); [v1 registration, lines 17–20](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/config/rules/chart_research.yaml#L17)
- The report correctly describes the observed up/down sides as separate **long-only** hypotheses, not implied by the traditional name; a down break has not been tested as an executable short. The v2 census has 1,133 confirmed up and 1,167 confirmed down breaks, plus 577 late/unobservable and other non-signal states. — [v2 report, lines 3–11](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/reports/chart-pattern-v2-2026-10-02.md#L3)
- Chartist references regard a closing break as a starting point and often look for volume expansion, break size, persistence, and position relative to the apex; those contextual checks are not in this price-only v2 detector. — [StockCharts symmetrical triangle](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/symmetrical-triangle); [StockCharts descending triangle](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/descending-triangle)

### Inferences
- `confirmed_up` means “one observed close crossed a computed upper boundary,” not “buy”; `confirmed_down` means the corresponding lower cross, not “short.” A 0.5% cross can be small relative to normal volatility or tick size and may occur near a triangle apex. A later `failure_on` is useful for **prospective** risk tracking, but filtering past signals by eventual failure would introduce look-ahead bias.

### Gaps
- The report does not show first-day follow-through, failed-break frequency, break distance relative to volatility/tick, or whether matched-volume expansion would change recognizability. Those are untested hypotheses, not reasons to tweak v2 after viewing its returns.

## 3. Does the simulated trade match Vietnamese execution?

### Takeaway
The return engine handles several essential Vietnamese constraints, but “next open if not ceiling” remains a price assumption rather than a proven fill for Ben's order size. Unresolved floor exits and provisional fees can materially distort an apparent edge.

### Cited Findings
- HOSE's own trading guide states an ordinary stock fluctuation band of ±7%, with different first-day/resumption cases. HNX's official FAQ states ±10% for HNX-listed shares and ±15% for UPCoM, whose reference price is a previous-session weighted average rather than simply the previous close. — [HOSE trading guide](https://staticfile.hsx.vn/Uploads/UploadDocuments/2453338/HTGD_Quy%20dinh%20can%20biet%20khi%20GDCK%20tren%20HOSE_T2.2026.pdf); [HNX FAQ](https://upcom.hnx.vn/vi-vn/hoi-dap.html)
- VSDC says the August 29, 2022 change made T+2 stock/cash available before 13:00 for afternoon trading; previously completion was after the market close. The return engine dates settlement eras and requires sellability at the chosen horizon. — [VSDC notice](https://vsdc.vn/vi/ad/152750); [return engine, lines 1–19 and 102–117](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/backtest/forward_returns.py#L1)
- The model enters at next session's **open**, excludes an open at the ceiling, requires matched volume, defers a close-at-floor exit for up to five sessions, then blanks unresolved exits; it quarantines UPCoM/undated-exchange fill judgments. Net return includes both-side broker fees and sale tax, but the broker fee is provisional. — [return engine, lines 21–54 and 226–370](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/backtest/forward_returns.py#L21); [evidence gate, lines 83–126](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/backtest/evidence.py#L83)

### Inferences
- Matched volume somewhere during the day does not prove a particular order could fill at the opening auction price, especially with thin books. Excluding every ceiling open is conservative about entry; dropping positions still trapped at the floor after five sessions is **not** conservative for estimated returns if the worst losses vanish. Treat the table as conditional on resolvable, model-fillable trades, not portfolio P&L.

### Gaps
- Actual broker fee, intended order size, participation cap, auction/book depth, slippage and treatment of unresolved floor-held positions are not calibrated. Current rule pages do not establish the correctness of every historical regime in a 2012–2023 backtest; the project's dated market-rule dataset still needs a targeted audit.

## 4. Does the table support any stock-strength or pattern-strength claim?

### Takeaway
No. It is a pooled, spent-history, multiple-comparison description. Even its most attractive primary cell is too small and selected from too many possibilities to justify an edge, let alone strength in a particular stock.

### Cited Findings
- The protocol fixes five variants × two sides × four horizons = **40** trials, primary k=10. The report shows all ten primary side cells in each already-viewed period, correctly says neither slice is a fresh holdout, and explicitly withholds prediction/scan promotion. — [v2 registration, lines 3–15 and 27–30](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/config/rules/chart_research_v2.yaml#L3); [v2 report, lines 5–30](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/reports/chart-pattern-v2-2026-10-02.md#L5)
- Its later descending-triangle/up cell has n=14 and +21.45 percentage-point hit edge against a 49.98% stock-day base, implying **10 net-positive outcomes out of 14**; one outcome changes that hit rate by 7.14 points. The earlier cell has n=50 and +10.86 points. Several other cells change sign between periods or have fewer than 20 occurrences. — [v2 report, lines 11–28](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/reports/chart-pattern-v2-2026-10-02.md#L11)
- `evidence._level` calculates hit rate/mean on raw eligible event rows and `n_declustered` separately, against all eligible same-period stock-days where a signal could be judged. `descriptive_market` explicitly takes the **market** level, not the stock→tier→market chosen fallback. — [evidence, lines 170–215 and 220–273](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/backtest/evidence.py#L170); [v2 descriptive_market, lines 374–409](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/chart_research_v2.py#L374)
- The gate removes missing/non-liquid/fill-flagged/not-yet-known outcomes. The report's primary base denominators are 190,572 (2012–19) and 182,582 (2020–23), whereas the whole census contains 2,511,070 stock-days; these numbers describe different populations. — [evidence gate, lines 83–126](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/src/vnstock_research/backtest/evidence.py#L83); [v2 report, lines 9–11](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/reports/chart-pattern-v2-2026-10-02.md#L9)

### Inferences
- The denominator is correctly gated for a descriptive comparison, but it is **not** a same-stock, same-regime or one-pick-per-day counterfactual. Horizons overlap, related variants can co-occur, and many stocks can fire on one market-shock day; the reported n alone should not be treated as independent trials. A pooled edge cannot answer whether any single stock is “strong.”

### Gaps
- No multiplicity-controlled p-value/interval, date-block uncertainty, year/regime/tier stability, stock-level fallback, or one-pick-per-signal-day analysis is reported for v2. The already computed 2024–2026 outcomes cannot become an untouched holdout by renaming them.

## 5. What should happen next without tuning on spent outcomes?

### Takeaway
Keep v2 research-only. The shortest credible path is to verify meaning and fillability **without reading forward returns**, freeze any correction, then log and evaluate new observations prospectively.

### Cited Findings
- The prior audit was deterministically sampled by episode-ID hash and viewed only through event date; causal replay matched all 25. This provides a ready procedure for a new v2 geometry audit, not efficacy validation. — [geometry audit, lines 3–7](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/reports/chart-pattern-geometry-audit-2026-10-01.md#L3)
- Project discipline already requires base-rate comparison, per-stock fallback, no look-ahead, multiplicity accounting, fillability and costs, and a valid “no recommendation today” result. — [validation notes, lines 1–32](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/agent-memory/knowledge/validation.md#L1); [project instructions](/Users/Ben%20Nguyen/stock_assistant/stock_assistant/AGENTS.md)

### Inferences
1. **First: blind v2 geometry rubric.** Fix a hash-selected sample *before opening its charts*, stratified by variant, observed side, and confirmed/late state; show only formation through event date. Have this agent score “recognizable,” “range-like,” “ambiguous,” prior trend, wall containment, and whether 0.5% is a meaningful move relative to tick/volatility. A single AI reviewer is not independent broker certification; preserve the rubric and disagreements for Ben.
2. **Second: execution/attrition ledger on spent history.** Count candidate → confirmed → PIT liquid → next-open/fillable → resolved per side, exchange and year; separately report ceiling rejects, floor deferrals/unresolved, matched turnover and plausible order-size/slippage sensitivity. Do not hide discarded downside tails.
3. **Third: freeze v3 only if a geometry or execution defect is found.** Register the revised rule, all sides/horizons, sample floor and date-block/multiplicity method before looking at revised outcome effects. Do not choose thresholds based on v2's attractive cells.
4. **Fourth: prospective log.** Day by day, timestamp candidates and no-signal decisions, then after outcomes mature compare the *entire* registered family with same-gate base rates, stock→tier→market fallback and one-stake-per-day results. A promising historical cell is only a question for that future test.

### Gaps
- The v2-specific blind chart review, fill ledger, actual-cost calibration, and prospective outcome record are not done in this review.
