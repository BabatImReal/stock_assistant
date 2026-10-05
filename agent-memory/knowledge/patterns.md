# Patterns (doc §2-3)

## How a shape becomes a signal (doc §2)
Three layers, and only the third one matters:

1. **Definition** — each pattern is plain arithmetic on OHLCV. Bullish
   engulfing = yesterday red, today green, today's body covers yesterday's.
   No image, no opinion, same answer every time.
2. **Detection** — run the rule over the whole history of every code
   (~1,500 codes × 2012→now) and flag every occurrence.
3. **Measurement** — for every flag, look *forward*: up or down after 3 and 5
   days, best gain and worst drawdown in the window, target-before-stop.

> The pattern is the question; the history is the answer.

**The base rate is the whole point.** A 58% hit rate means nothing if the stock
rises on 55% of all 5-day windows anyway. The edge is hit rate *minus* base
rate, measured over the same period. Never report one without the other.

## Catalogue (doc §3)
Vocabulary: body = |open−close|; upper wick = high − top of body; lower wick =
bottom of body − low; range = high − low.

- **Single candle (§3.1):** hammer, inverted hammer, shooting star, hanging
  man, doji, marubozu. Note hammer and hanging man are the *same shape* — only
  the preceding trend differs, which is why context (doc §5) is not optional.
- **Two candle (§3.2):** bullish/bearish engulfing, bullish/bearish harami,
  piercing line, dark cloud cover.
- **Three candle (§3.3):** morning star, evening star, three white soldiers,
  three black crows, three inside up/down. Multi-candle patterns test better
  than singles because they contain their own confirmation.
- **Short consolidations (§3.4)** — probably closest to what the broker friend
  actually watches, and not classic candlestick names: tight range/squeeze
  (avg range of last N days < X% of 20-day avg range), inside-day sequence,
  flag/pause (sharp rise then 3–5 quiet days on *falling* volume), higher lows,
  breakout day (close above N-day high on strong volume).

**Traditional labels are hypotheses, not facts (§3).** Backtests have found
patterns that move opposite to their name. Every label gets measured on VN data
before it is trusted.

**Parameters are decisions (§3.5).** "Lower wick ≥ 2× body" could be 1.5× or
3×. Picking the threshold that looks best on history is the classic way to fool
yourself. Fix textbook values first → measure → only then let the broker friend
adjust them, with reasons. Config, never hard-coded.

## The layered fingerprint (doc §3.6) — the most important idea here
Real charts never show one clean pattern. Five realities: co-occurrence
(hammer + harami + volume spike + support all on one day), conflict (bullish
candle inside a falling trend), many *cases* of the same pattern (engulfing by
a hair vs by 3×, on 0.8× vs 3× volume, at support vs in empty space —
different things, measured separately), nesting across timeframes, and
sequence (order tells a story).

So the unit of analysis is not "did pattern X fire" but the **fingerprint**:
every stock-day described by *all* its flags and measures together — patterns
fired, trend position, distance to support/resistance, volume measures, weekly
position, market regime, sector (~100 measures per stock-day).

Two ways to use it:
- **Measure combinations**, but only those with enough occurrences —
  combinations multiply fast and this is where overfitting bites hardest
  ([[validation]]).
- **Find analogs**: search history for the days most similar to today's
  fingerprint and look at what followed. This matches how a broker thinks
  ("I've seen this before") and stays explainable — the actual look-alike dates
  can be shown to Ben.

Always keep bullish and bearish evidence side by side; never hide the bearish
column. Whether a higher timeframe overrides a lower one is a rule to
**measure**, not assume.

## Build status
**T5 BUILT 2026-09-23 (run 14)**: the fingerprint (`patterns/fingerprint.py`).
It is `compute()` stacked per stock-day over EVERY stock since 2012, plus the
flag columns. The schema is generated from the registries; `direction` is
report-only. Stored as Parquet by year + a manifest (build, feature set, code
hash, file hashes); `load` refuses anything stale; `validated()` is the only path
to validated values; `query` gives exact combinations with counts, unknown kept
unknown. encode/neighbours stay T6 (after G5).
**T4 BUILT 2026-09-23 (run 13)**: tight_range, inside_day_run, higher_lows,
breakout (price-only, P6; "on volume" = a combination with rvol). Flag/pause
deferred (P7). Liquid rates: 8.71 / 2.67 / 1.26 / 5.60%. **The catalogue is
complete (T1–T4); next is T5, fingerprint assembly.**
**T3 BUILT 2026-09-23 (run 12)**: morning/evening star (P4: the star opens
beyond d1's close, no true gap), three white soldiers / black crows, three
inside up/down (the harami reused). There is a large-body floor on the big
candles, not on the star. Liquid rates: 0.14 / 0.22 / 0.21 / 0.43 / 0.61 /
0.45%: rare, so they rely on the group/market fallback.
**T2 BUILT 2026-09-23 (run 11)**: bullish/bearish engulfing, bullish/bearish
harami (LONG = the 20-session mean body before yesterday), piercing line, dark
cloud cover. There is a prior-body floor (yesterday's RAW body >= 3 ticks) and a
1e-4 cross-day tolerance. Liquid rates: 2.40 / 2.36 / 4.48 / 3.89 / 0.63 /
0.84%.
**T1 BUILT 2026-09-23 (run 10, `features/patterns`)**: 5 anatomy numerics
(body/upper/lower-to-range, range_rel_20d, open_gap) and 5 shapes
(hammer_shape, inverted_hammer_shape, doji, marubozu_green/red), with a
3-tick floor on the RAW range using the dated exchange's tick. Liquid firing
rates: hammer 5.0%, inverted 3.6%, doji 11.0%, marubozu 5.2% / 5.6%. T2–T6
not started. P1–P9 answered (decisions.md run 10).

Earlier: PROPOSED 2026-09-23 (session 2026-09-23-03, run 8): catalogue with rules and
config, fingerprint = `compute()` output stacked per stock-day (Parquet +
manifest, schema from the registries), the G5 interface (`query` now;
`encode`/`neighbours` after G5), and tranches T1–T6. Awaiting P1–P9. No code.

Related: [[money-flow]] [[context-vietnam]] [[validation]] [[funnel-and-scale]]

## 2026-09-30 research design, not implementation
`reports/Vietnam chart pattern rulebook.md` groups the user-provided chart
names into seven observable geometry families: repeated levels, three-extrema
reversals, converging bounds, parallel/flat bounds, broadening bounds, rounded
turns, and boundary events. Direction, prior trend, scale, pole, handle, and
breakout side are explicit attributes; nested names can co-fire in one
stock-day fingerprint. A pivot is usable only after its causal confirmation;
the crossing signal is dated when observable, never at a later-drawn peak.
Price-only geometry and matched-volume confirmation are distinct hypotheses.
No new family is implemented or shown reliable for Vietnam by this document.

`reports/Vietnam chart rules and horizons.md` (run 3) proposes one numerical
first tranche: causal close pivots (two right-side sessions), repeated levels,
triangles, rectangles, and pole-conditioned flag/pennant overlays, with
separate forming/confirmed/failed states and one episode ID. Every number is
a candidate pre-registration choice, not a Vietnamese optimum. Ben approved
the 3/5/10/20 outcome scope in run 3; he approved a two-family pilot on
2026-10-01. Rectangles and flag/pennant overlays remain design-stage.

## 2026-10-01 chart pilot (doc §3, §8)
`config/rules/chart_research.yaml` fixes five price-only variants before the
whole-market census: double top/bottom and symmetric/ascending/descending
triangles. `chart_research.detect` dates two-right-session confirmed pivots,
candidate creation, first observed break, expiry and later failure; adjusted
data gaps cut formations. The observed first-break side is an attribute, not
implied by a name. `signal_frame` marks days before 125 clean sessions unknown.
The separate artifact for promoted build 5 has 3,965 candidate episodes,
2,770 confirmed first breaks, 844 symbols with candidates; the full panel has
2,511,070 symbol-days. The 2012–2023 k=10 comparisons in
`reports/chart-pattern-pilot-2026-10-01.md` are descriptive only. In
particular, pooled direction hides frequent opposite-side breaks; do not
describe any named pattern as an established Vietnamese predictive signal.

## 2026-10-01 fixed-sample geometry audit (doc §3.6)
An outcome-blind SHA-256 sample of 25 v1 events (four confirmed per variant,
one late per variant; 2012–2023 only) was plotted only through its event date.
All 25 reappeared on causal replay of truncated bars. Three of 20 confirmed
triangles exceeded their eventual frozen boundary during formation: VAT
(13.46%), NAB (2.10%), DVP (1.56%) against the existing 1% triangle
diagnostic band. V1 checks only from its last anchor to candidate confirmation,
so anchor-defined triangles can encompass earlier out-of-wall moves. Some
double-level examples resemble trading ranges rather than clean two-turn
reversals; that label ambiguity remains for broker review. This is not a
whole-market defect rate. Ben chose whole-formation containment before the
direction-aware v2 registration.

## 2026-10-02 contained, observed-side v2 census (doc §3.6, §8)
The separate `chart_research_v2.py` requires every adjusted close from first
through last anchor to lie inside its eventually frozen walls, using the
existing 1.5% repeated-level / 1% triangle tolerances. The stricter v1
0.5% last-anchor-to-candidate first-cross check remains. Invalid candidates
are rejected before they can suppress later valid episodes. Up and down
first breaks are distinct flags; a down break is still evaluated as a
long-only return, not a short trade. Config commit `03c5105` registered
5 variants × 2 sides × 4 horizons = 40 cells before side-specific outcomes.
Build 5 produced 3,172 candidates on 796 symbols and 2,300 confirmed
breaks (1,133 up / 1,167 down). The full signal panel has 2,511,070
stock-days. `reports/chart-pattern-v2-2026-10-02.md` records the old-period
primary-horizon description; none is predictive validation. V1 is unchanged.

## 2026-10-02 AI broker-style review (doc §3.6)
`reports/Vietnam chart pattern broker review.md` distinguishes contained
close-based geometry from textbook chart calls. No outcome-blind *v2* chart
sample was inspected in this review. Repeated-high/low cases need a prior-trend
and range-versus-reversal rubric; a first 0.5% wall cross is an observed event,
not a buy or short order. This AI critique is not licensed broker certification
or evidence that a formation predicts stock strength.
