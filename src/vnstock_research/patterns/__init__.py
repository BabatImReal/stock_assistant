"""Pattern rules: plain arithmetic on OHLCV that returns true or false.

Doc §3 (the catalogue) and §3.6 (the layered fingerprint).

A pattern is a rule, not a picture. Bullish engulfing is three comparisons:
yesterday closed red, today closed green, today's body covers yesterday's. No
image, no opinion, the same answer every time — which is why the doc rejects
vision models (§10.1): the chart is drawn *from* these numbers, so an image is
a blurrier copy of data we already have exactly.

What lives here: single-candle patterns (hammer, shooting star, doji,
marubozu…), two-candle (engulfing, harami, piercing line, dark cloud cover),
three-candle (morning/evening star, three white soldiers…), and the short
consolidations of §3.4 — tight range, inside days, flag, higher lows, breakout —
which are probably closest to what Ben's broker friend actually watches.

Two rules that shape the code:

- **Thresholds are decisions, not facts (doc §3.5).** "Lower wick ≥ 2× body"
  could be 1.5× or 3×, and picking the value that looks best on history is the
  most common way to fool yourself. Parameters therefore live in config/rules/,
  never inline in a function.
- **Traditional labels are hypotheses (doc §3).** A "bullish" pattern is called
  bullish until Vietnamese data says otherwise. Detection never assumes a
  direction; direction is something backtest measures.

The output is not one flag per day but a **fingerprint** (doc §3.6): every
pattern that fired, plus the trend, volume and context measures around it. Real
charts are layered, and several patterns — some conflicting — fire at once.
"""
