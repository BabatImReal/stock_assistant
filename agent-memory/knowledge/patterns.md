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
