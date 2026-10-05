# Vietnam chart pattern research rulebook

Status: **research design for Ben's review, 2026-09-30**. No new pattern in this
document has been measured, validated, or approved as a daily signal. This is
the first deliverable on `codex/pattern-research-next-step`; the per-stock
report is a later project.

## What the research must answer

For every liquid HOSE, HNX, and UPCoM stock, on every eligible trading day
since 2012:

1. What price structure and stock behavior were **knowable at that close**?
2. What happened after comparable structures, relative to comparable days
   without the structure?
3. Did any difference survive across stocks, years, market regimes, costs,
   trading constraints, and a genuinely future sample?

A shape's traditional name states a hypothesis, not a probability. One US
study found that some objectively identified formations changed the
distribution of later returns; a Vietnam study of ten candlestick patterns
found no reliable directional prediction in its sample. The evidence is
specific to definitions, markets, periods, and outcome rules. [Lo, Mamaysky
and Wang](https://business.columbia.edu/sites/default/files-efs/pubfiles/19268/Lo-Mamaysky_wang_foundations.pdf);
[Son and colleagues](https://www.researchgate.net/profile/Ngo_Son3/publication/325451768_An_Analyze_on_Effectiveness_of_Candlestick_Reversal_Patterns_for_Vietnamese_Stock_Market/links/5b273c2ca6fdcc69746af008/An-Analyze-on-Effectiveness-of-Candlestick-Reversal-Patterns-for-Vietnamese-Stock-Market.pdf?origin=publication_detail).

The source-of-truth project requirements remain in
`docs/knowledge/pattern-research-knowledge.md` (§2–8); this document adds the
multiweek formations in Ben's examples and specifies how to study them.

## Coverage map

The current project already detects 21 short pattern triggers: five
single-candle shapes, six two-candle patterns, six three-candle patterns, and
four short consolidations (`tight_range`, `inside_day_run`, `higher_lows`,
`breakout`). It also computes volume, market, support/resistance, and long
trend or relative-strength features. Its `breakout` is a close above the prior
20-session high; it does **not** identify the base that preceded the break.
`higher_lows` is a short flag, not a full ascending triangle. The descriptive
2012–2025 pattern-history report covers those existing flags and eight
structural comparisons; it is not evidence for the new families.

The new catalogue groups named drawings by their measurable geometry. Variants
remain visible, but an overlapping episode is not counted as several
independent observations. The practitioner's charts provide names and
conventional readings, not Vietnamese success rates. [IG pattern guide](https://www.ig.com/uk/trading-strategies/10-chart-patterns-every-trader-needs-to-know-190514);
[CMC pattern guide](https://www.cmcmarkets.com/en/shares/stock-chart-patterns);
[Investing.com pattern guide](https://www.investing.com/academy/analysis/top-10-stock-chart-patterns/).

| Measurable family | Names and variants to catalogue | Candidate geometry | Confirmation event |
| --- | --- | --- | --- |
| Repeated level | Double/triple top or bottom | Separate highs near resistance or lows near support, with meaningful opposite swings between tests | Close through the intervening neckline in the observed direction |
| Three-extrema reversal | Head and shoulders / inverse; sometimes overlaps a triple top/bottom | Left shoulder, more extreme head, right shoulder, and two neckline anchors | Close through the neckline after the final shoulder is knowable |
| Converging bounds | Symmetrical/ascending/descending triangle; rising/falling wedge; pennant after a pole | Alternating highs and lows support two lines whose separation narrows | Close beyond a previously known/projected boundary; record **which** side |
| Parallel or flat bounds | Rectangle, range, price channel; flag after a pole | Repeated upper/lower touches at roughly stable width | Close beyond the known upper or lower boundary |
| Broadening bounds | Broadening top/bottom, expanding triangle, megaphone | Alternating swing extremes diverge | Close beyond a boundary; expansion alone is only a state |
| Rounded turn | Rounding bottom/top, cup, cup and handle, inverse cup and handle | Broad turn with two rims; the handle is a later, smaller pullback | Close beyond the relevant rim or handle boundary after both are complete |
| Boundary event | Breakout, breakdown, retest, false breakout, failed breakdown | A prior level is known independently of today's crossing | First crossing, later retest, and later failure are **separate dated events** |

These families are hierarchical. A pennant is a short triangle after a prior
impulse; a flag is a short channel after one. A cup contains a rounded base.
Two tests of one level may also be part of a rectangle. A family can have
several descriptive labels, yet one stock/formation episode should carry one
stable identity for de-clustering. The seven families cover the named
formations in Ben's three images, including their bullish/bearish mirrors;
they are not a claim that every published drawing is a distinct phenomenon.

### Required rule card for each variant

Before a historical result is viewed, each implementable variant needs one
versioned card specifying:

- **Inputs and scale:** adjusted OHLC; matched volume only if a volume claim is
  tested; formation start and maximum age in trading sessions; daily or
  completed weekly/monthly context.
- **Anchors:** whether swing points use highs/lows or closes; the rule for a
  pivot to become confirmed; minimum movement, separation, and number of
  boundary touches; handling equal prices and exchange ticks.
- **Geometry:** level tolerance, depth, relative shoulder/rim heights,
  line-slope and convergence rules, and the allowed overlap with other cards.
- **Context:** what preceding rise or fall is required to call a structure a
  reversal or continuation. Without it, record the geometry without that
  directional interpretation.
- **Event:** exact close-based confirmation crossing; optional breakout
  volume condition as a **separately counted hypothesis**; expiry and
  invalidation; at most one first-crossing signal per formation/direction.
- **Audit fields:** symbol, formation start, every anchor date and
  `confirmed_on`, boundary value at signal close, breakout side, raw input
  version, data-quality flags, and detector version.

The numerical values in these cards are **not** chosen by this rulebook.
Pivot radius, tick/percentage tolerance, minimum depth, formation duration,
breakout margin, volume threshold, retest interval, and outcome horizon must
be fixed and counted as choices before measurement. Searching many variants
and reporting only the winner would recreate the project's multiple-testing
problem. [Sullivan, Timmermann and White](https://www.fmg.ac.uk/publications/discussion-papers/data-snooping-technical-trading-rule-performance-and-bootstrap).

## Time and information rules

A pivot can occur at session `j` but require later sessions to confirm. Its
price belongs to `j`; its **first usable date** is `confirmed_on`. The existing
support/resistance feature already enforces that distinction. For any signal
at close `t`, all anchors and the projected boundary must have been knowable
by `t`. The breakout bar cannot be used to refit the line it is crossing.

Use these dated states for research: `forming`, `confirmed_up`,
`confirmed_down`, `invalidated`, `expired`. A candidate may be watched while
forming; its traditional direction is not yet an observed move. A false
breakout can only be labelled when its later failure becomes knowable; it
must never be backdated to the first crossing. A bullish name followed by a
downside break stays in the sample as a contradictory observation.

Example: the second low of a potential double bottom occurs on `j` but is
confirmed on `j+3`. If the neckline closes above on `j+5`, `j+5` is the
earliest confirmed signal. Model any entry no earlier than the next eligible
open. At `j`, `j+1`, or `j+2`, it must not appear as a completed double bottom.
Published algorithms also distinguish the formation from a later neckline
crossing. [Federal Reserve Bank of New York head-and-shoulders study](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr42.pdf).

No formation or outcome window spans a genuine trading gap, excluded bar, or
unexplained adjustment break. Weekends and market holidays are closures, not
missing sessions. Source reconciliation, stock dividends/rights adjustment,
inverse volume adjustment, and point-in-time exchange membership use the
project's existing gates. A long formation is especially exposed to the open
G2 historical-factor-restatement defect: new results cannot be treated as
current after a corporate action until the adjusted chain is checked and
rebuilt where necessary. The existing G20 defect gate blanks known bad spans.

## Stock behavior measured beside the shapes

A full research row is a **fingerprint**, not a single pattern name (source
doc §3.6). The following axes describe the stock without claiming that a
single threshold makes it "strong":

| Layer | Measurements to reuse or research | Purpose |
| --- | --- | --- |
| Long trend | Price vs 200-session average, average slope, 120-session relative strength, trend stage, depth and recovery from major drawdowns | Distinguish sustained leadership from a rebound inside a decline |
| Medium trend | 20/50-session price/average/slope, 20/60-session relative strength, support/resistance, range width, volatility, repeated level tests | Identify the environment in which a formation develops |
| Short behavior | 1–10-session candles and consolidations, first break, retest/failure, matched relative volume and traded value | Date a trigger and inspect participation |
| Market and peers | VN-Index regime and breadth; dated sector context only where genuinely point-in-time | Check whether the stock moves with or against its environment |
| Friction | Historical liquidity, venue, price limit, settlement era, unresolved floor exits, fees and sale tax | Separate a detectable movement from a feasible one |

High matched volume measures activity; it does not, by itself, prove net
capital inflow or identify who bought. Price/volume agreement, sustained
turnover, and dry-up during a pause are separate measurements. Negotiated
block trades must not enter them. Missing or nonadjustable volume stays
unknown rather than becoming a low-volume signal. Current sector labels are
not a valid substitute for historical point-in-time labels.

## Testing protocol for new formations

This protocol is a **proposal for registration**, not a new run of the frozen
`config/rules/protocol.yaml` block. The existing six accepted signals and
their paper ledger remain their own version.

1. **Lock the detector and every trial.** Record the rule-card versions,
   family/variant, price-only or volume-conditioned form, any context filter,
   direction tested, outcome horizon, and every attempted parameter set.
   State the total hypothesis count before seeing results. Preserve source,
   adjustment, feature, and outcome hashes.
2. **Census the historical events.** Produce each family on every eligible
   stock-day, with forming/confirmed/failed counts, sample cases and misses,
   unknowns and exclusion reasons. Verify truncation: computing through `t`
   must give the same `t` event as computing through later dates. Audit
   apparent shapes near corporate actions and trading gaps.
3. **Measure outcomes from the actual confirmation date.** Keep the current
   registered 3- and 5-session outcome model available. Longer observation
   horizons for multiweek structures require their own pre-registered entry,
   exit, settlement, floor/ceiling, and unresolved-case rules before use.
   Record both `P(net > 0)` and `P(net < 0)`, mean/median net, average win and
   loss, maximum favorable/adverse excursion, and time to failure or expiry.
   A bearish long-only signal is first an *avoid/risk* hypothesis; calling
   an avoided loss a trading profit requires a separately tested selection
   policy.
4. **Use the same population for each base rate.** Compare a formation with
   stock-days on which its inputs and outcome could be judged, under the same
   point-in-time liquidity, venue, regime, and horizon rules. Report the
   stock-level estimate when adequate; otherwise label the fallback to
   point-in-time group (currently liquidity tier) and then market. Report
   sample size and uncertainty; do not show a thin-cell percentage as a
   reliable probability.
5. **Handle overlap and dependence.** Keep all simultaneous flags in the
   fingerprint. De-cluster repeat dates from one formation and report raw and
   independent event counts. Resample blocks of dates, since many stocks
   react to the same market day; control false discoveries over **all** rules
   tried. Report stock, year, regime, and venue breakdowns. If the intended
   use is one pick per day, measure the selected one-pick-per-day policy as
   its own unit; per-formation returns are not a substitute.
6. **Separate research from confirmation.** Use 2012–2019 for definition and
   discovery and 2020–2023 for temporal replication under a fixed rule. The
   project has already inspected its 2024–2026 holdout; it cannot become a
   fresh confirmation sample for new chart-pattern ideas. Since earlier
   project research also inspected 2012–2023, label historical results as
   development/replication rather than pristine proof. Lock a new rule and
   begin an append-only forward record on dates after its registration.

An apparent win must survive data reconciliation, denominator checks, a
matched base rate, trading costs, and examination of both good and bad years.
Research on technical trading rules shows how searching many rules inflates
the best-looking historical result. [Sullivan, Timmermann and White](https://www.fmg.ac.uk/publications/discussion-papers/data-snooping-technical-trading-rule-performance-and-bootstrap).

## Readiness and sequence after Ben reviews this rulebook

| Order | Deliverable | Acceptance check |
| --- | --- | --- |
| 1 | Approve a small versioned rule-card set and exact outcome horizons; begin with repeated levels and converging/parallel bounds, which also cover doubles, triangles, rectangles, flags and pennants | Every threshold, event date, trial, and alias is written before historical results are viewed |
| 2 | Implement one causal pivot/level path and deterministic formation events, reusing existing feature guards and provenance | Hand-counted examples, truncation checks, gap and adjustment cases fail when the guard is removed |
| 3 | Run a full eligible-stock census and the pre-registered historical protocol; audit real charts **from computed dates** as a diagnostic, not as input to the detector | Event and exclusion counts reconcile; no future input or unregistered trials |
| 4 | Add the remaining rounded/three-extrema/broadening families only as distinct questions, then register a forward-only rule set | Every family has a known sample size, explicit ambiguity and failure cases; no result is promoted from the spent holdout |
| 5 | Accumulate future observations and evaluate the selection policy after enough signal days | One-pick-per-day results, unresolved outcomes, costs, drawdown, and comparison to its base are all visible |

The existing nightly pipeline is not known to be collecting forward rows; its
operational status must be checked before step 5. G2 and the provisional
broker fee can change long-window reliability and net expectancy. This
rulebook changes no detector, registered protocol, frozen daily scan,
database, or ledger.

## Decisions needed before implementation

1. What formation duration bands and pivot confirmation delay should be
   registered for the first rule cards? Start with one specification per
   family; treat additional variants as additional trials.
2. Should new formations be judged only at the existing 3- and 5-session
   horizons initially, or should longer horizons be registered and modeled?
3. Should a bearish pattern be studied only as a risk/avoid signal, as the
   project's long-only scope implies?
4. What is Ben's actual all-in broker fee? Until confirmed, net results remain
   provisional.

The first decision is a research-design choice, not an invitation to tune
thresholds on the already viewed data. The second changes the outcome model
and needs Ben's architectural approval. No new probability will be claimed
until the forward record exists and matures.
