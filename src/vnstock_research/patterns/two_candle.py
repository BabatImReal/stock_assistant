"""Tranche 2 of the pattern catalogue (doc §3.2): two-candle patterns.

Each is dated on TODAY (the second candle) and reads yesterday's candle, never
tomorrow's. The declared lookback is therefore at least 1, so base.py blanks a
pair that straddles a trading gap or an excluded row. Yesterday's close from
before a three-week suspension is not "yesterday" (the same yesterday-adjacent
rule as breadth and sector direction).

The rules, from doc §3.2 (d1 = yesterday, d2 = today):
  bullish_engulfing  d1 red, d2 green, d2's body covers d1's
                     (open2 <= close1 and close2 >= open1)
  bearish_engulfing  the mirror
  bullish_harami     d1 red AND LONG, d2's whole body inside d1's body, and at
                     most max_body_ratio of it (d2's colour is not required)
  bearish_harami     the mirror
  piercing_line      d1 red, d2 green, d2 opens BELOW close1 and closes above
                     d1's midpoint but below open1. That last bound keeps it
                     distinct from an engulfing (textbook); the doc's wording
                     gives only the midpoint.
  dark_cloud_cover   the mirror
LONG (Ben, P3): d1's body >= long_body_vs_avg_min x the mean body of the
long_body_window sessions BEFORE d1. So harami's lookback is window + 1.

COLOURS THAT ARE IMPLIED are not tested twice (a clause that cannot change the
answer cannot be tested either):
  - engulfing: d1 red + "open2 <= close1 < open1 <= close2" forces d2 green;
  - harami: "d2 inside open1 (top) .. close1 (bottom)" forces d1 red (a body-0
    d1 is already excluded by the prior-body floor);
  - piercing: "open2 < close1 < close2 < open1" forces d1 red AND d2 green.
  Mirrors likewise. Engulfing still checks d1's colour: that is not implied.
P4 (the relaxed star gaps) does not apply here.

THE PRIOR-BODY FLOOR. A 1-2 tick body yesterday makes "today covers it",
"today sits inside it" and "today closes past its midpoint" true on tick noise.
So every pattern needs yesterday's RAW body >= min_prior_body_ticks ticks, the
same tick rule as the tranche-1 range floor (data/checks.py `floor_tick`: the
dated exchange's own tick, the largest of any exchange where undated). Today's
body needs no floor: an engulfing body covers yesterday's anyway, and a
harami's small body is the point.

CROSS-DAY TIES. Prices sit on a tick grid, so "open2 == close1" is common. On
the ADJUSTED series, 43.5% of those raw ties come out unequal, by rounding in
the daily factor (measured 2026-09-23: median 0, 99th percentile 2.6e-5
relative). So cross-day comparisons use REL_TOL = 1e-4: "<=" and ">=" absorb
it, "strictly lower/higher" must clear it. That is 4x the 99th-percentile
jitter and at least 5x smaller than any real tick (the smallest relative tick
is ~0.05%).

Thresholds live in config/rules/features.yaml (P2), fixed before any measuring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.checks import floor_tick
from ..features.base import boolean_from, measure

NEEDS = (
    "open",
    "high",
    "low",
    "close",
    "raw_open",
    "raw_close",
    "exchange",
    "exchange_unknown",
)
REL_TOL = 1e-4
EPS = 1e-9


def _le(a, b):
    return a <= b * (1 + REL_TOL)


def _ge(a, b):
    return a >= b * (1 - REL_TOL)


def _lt(a, b):
    return a < b * (1 - REL_TOL)


def _gt(a, b):
    return a > b * (1 + REL_TOL)


def _pair(bars: pd.DataFrame):
    o = bars["open"].astype("float64")
    c = bars["close"].astype("float64")
    o1, c1 = o.shift(1), c.shift(1)
    return o, c, o1, c1, (c - o).abs(), (c1 - o1).abs()


def raw_body_ok(bars: pd.DataFrame, min_ticks: float) -> pd.Series:
    """Each row's RAW body is at least `min_ticks` ticks (`floor_tick`). Shared
    with the three-candle patterns, which shift it onto their large candles."""
    raw_body = (
        bars["raw_close"].astype("float64") - bars["raw_open"].astype("float64")
    ).abs()
    tick = floor_tick(
        bars["trade_date"],
        bars["raw_close"],
        bars["exchange"],
        bars["exchange_unknown"],
    )
    return raw_body >= float(min_ticks) * tick - EPS


def _prior_body_ok(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Yesterday's RAW body is at least min_prior_body_ticks ticks."""
    ok = raw_body_ok(bars, p["min_prior_body_ticks"])
    return ok.shift(1, fill_value=False)


def _prior_long(body: pd.Series, p: dict) -> pd.Series:
    """Yesterday's body against the mean body of the window BEFORE yesterday."""
    w = int(p["long_body_window"])
    base = body.shift(2).rolling(w, min_periods=w).mean()
    return body.shift(1) >= float(p["long_body_vs_avg_min"]) * base - EPS


def _harami_lookback(p: dict) -> int:
    return int(p["long_body_window"]) + 1


@measure(
    name="bullish_engulfing",
    direction="bullish",
    doc_ref="doc §3.2",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: 1,
)
def bullish_engulfing(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Red day, then a green day whose body covers the red body."""
    o, c, o1, c1, body, body1 = _pair(bars)
    cond = (
        (c1 < o1)  # d2 green is implied
        & _le(o, c1)
        & _ge(c, o1)
        & (body >= float(p["min_body_cover"]) * body1 - EPS)
        & _prior_body_ok(bars, p)
    )
    return boolean_from(cond, c1)


@measure(
    name="bearish_engulfing",
    direction="bearish",
    doc_ref="doc §3.2",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: 1,
)
def bearish_engulfing(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Green day, then a red day whose body covers the green body."""
    o, c, o1, c1, body, body1 = _pair(bars)
    cond = (
        (c1 > o1)  # d2 red is implied
        & _ge(o, c1)
        & _le(c, o1)
        & (body >= float(p["min_body_cover"]) * body1 - EPS)
        & _prior_body_ok(bars, p)
    )
    return boolean_from(cond, c1)


@measure(
    name="bullish_harami",
    direction="bullish",
    doc_ref="doc §3.2",
    kind="boolean",
    needs=NEEDS,
    lookback=_harami_lookback,
)
def bullish_harami(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Long red day, then a small body fully inside it: selling is fading."""
    o, c, o1, c1, body, body1 = _pair(bars)
    cond = (
        _prior_long(body, p)  # d1 red is implied by the inside bounds
        & _le(np.maximum(o, c), o1)
        & _ge(np.minimum(o, c), c1)
        & (body <= float(p["max_body_ratio"]) * body1 + EPS)
        & _prior_body_ok(bars, p)
    )
    return boolean_from(cond, c1)


@measure(
    name="bearish_harami",
    direction="bearish",
    doc_ref="doc §3.2",
    kind="boolean",
    needs=NEEDS,
    lookback=_harami_lookback,
)
def bearish_harami(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Long green day, then a small body fully inside it: buying is fading."""
    o, c, o1, c1, body, body1 = _pair(bars)
    cond = (
        _prior_long(body, p)  # d1 green is implied by the inside bounds
        & _le(np.maximum(o, c), c1)
        & _ge(np.minimum(o, c), o1)
        & (body <= float(p["max_body_ratio"]) * body1 + EPS)
        & _prior_body_ok(bars, p)
    )
    return boolean_from(cond, c1)


@measure(
    name="piercing_line",
    direction="bullish",
    doc_ref="doc §3.2",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: 1,
)
def piercing_line(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Red day, then a green day opening lower that closes past the red body's
    midpoint, but not past its open."""
    o, c, o1, c1, _, body1 = _pair(bars)
    cond = (
        _lt(o, c1)  # both colours are implied by the three bounds
        & _gt(c, c1 + float(p["min_close_into_prev_body"]) * body1)
        & _lt(c, o1)
        & _prior_body_ok(bars, p)
    )
    return boolean_from(cond, c1)


@measure(
    name="dark_cloud_cover",
    direction="bearish",
    doc_ref="doc §3.2",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: 1,
)
def dark_cloud_cover(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Green day, then a red day opening higher that closes past the green
    body's midpoint, but not past its open."""
    o, c, o1, c1, _, body1 = _pair(bars)
    cond = (
        _gt(o, c1)  # both colours are implied by the three bounds
        & _lt(c, c1 - float(p["min_close_into_prev_body"]) * body1)
        & _gt(c, o1)
        & _prior_body_ok(bars, p)
    )
    return boolean_from(cond, c1)
