"""The daily output: one stock with its evidence, or nothing.

Doc §7.4 (what a recommendation contains) and §7.3 ("no recommendation today"
is a valid answer).

A recommendation is not a pick, it is a case that Ben can argue with. It
contains:

- the stock and the signal that fired (pattern + volume + context);
- its measured history: occurrences, hit rate **against the base rate**, average
  gain vs average loss, and over which years;
- a risk-defined setup: a reference entry, a **stop level** — the price that
  says this was wrong — and a target zone;
- what would invalidate it: the market regime turning, negative news, volume
  drying up;
- the runners-up and why they ranked lower;
- both columns of evidence, bullish and bearish. The bearish side is never
  hidden (doc §3.6).

And when nothing passes the funnel, the report says so. A tool that must produce
a pick every day will eventually invent bad ones; waiting is part of the
discipline the whole system is copying.

When an LLM writes the prose here it may use only numbers produced by the code
in backtest/, must cite them, and must say when a number is missing rather than
inventing one (doc §9.3).
"""
