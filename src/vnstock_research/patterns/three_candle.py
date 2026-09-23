"""Tranche 3 of the pattern catalogue (doc §3.3): three-candle patterns.

Each is dated on the THIRD candle (today) and reads the two before it, never
after. So the declared lookback is at least 2 (plus the 20-session LONG
baseline where used), and base.py blanks a pattern with a gap or an excluded
row anywhere in its window. Multi-candle patterns test better than singles
because they contain their own confirmation (doc §3.3), and that
confirmation is today's candle: nothing is back-dated.

The rules (d1, d2, d3 = the three days, d3 = today):
  morning_star   d1 red and LONG; d2 a star: body <= star_body_max x d1's body,
                 opening BELOW d1's close; d3 green and LONG, closing past d1's
                 midpoint (min_close_into_first_body).
  evening_star   the mirror.
  three_white_soldiers  each of d2 and d3 opens WITHIN the previous body
                 (between its open and close) and closes above the previous
                 close; each of the three closes near its high (upper wick <=
                 max_wick_to_range of its range).
  three_black_crows     the mirror (opens within, closes lower, near its low).
  three_inside_up       a bullish harami on d1-d2 (the tranche-2 rule, reused)
                 confirmed by d3 closing above d1's open.
  three_inside_down     the mirror.

P4, THE VN DEVIATION (Ben, 2026-09-23): the textbook star GAPS away from d1's
body. Daily price limits (HOSE +-7%) make true gaps rare in Vietnam, so the
star only has to OPEN beyond d1's close. The same deviation, documented once,
applies to both stars. d3 has no gap requirement (doc §3.3 gives none).

LONG (P3): a body >= long_body_vs_avg_min x the mean body of the
long_body_window sessions BEFORE d1. d1 and d3 of a star are both judged against
that same pre-pattern baseline, so the pattern cannot raise its own bar.

THE LARGE-BODY FLOOR (same tick rule as tranches 1-2, `raw_body_ok`): the
LARGE candles need a RAW body >= min_large_body_ticks ticks. That means d1 and
d3 of a star, all three soldiers/crows, and d1 of three-inside (via the reused
harami's own floor). A star's middle candle is NOT floored: its small body is
the point, as with a harami's second day.

IMPLIED COLOURS are not tested twice: soldiers' "open within the previous
body (open .. close)" plus "close above the previous close" forces all three
green (a body-0 day is already excluded by the floor); crows likewise red.
The stars' d1 and d3 colours are not implied and are checked.

Cross-day comparisons use tranche 2's REL_TOL (adjustment rounding).
Thresholds live in config/rules/features.yaml (P2), fixed before measuring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..features.base import boolean_from, measure
from .two_candle import (
    EPS,
    NEEDS,
    _ge,
    _gt,
    _le,
    _lt,
    bearish_harami,
    bullish_harami,
    raw_body_ok,
)


def _days(bars: pd.DataFrame):
    """(open, close, body) for d1, d2, d3, aligned on d3 (today)."""
    o = bars["open"].astype("float64")
    c = bars["close"].astype("float64")
    body = (c - o).abs()
    return [(o.shift(k), c.shift(k), body.shift(k)) for k in (2, 1, 0)], body


def _long(body: pd.Series, k: int, p: dict) -> pd.Series:
    """The body k days back is LONG against the window before d1."""
    w = int(p["long_body_window"])
    base = body.shift(3).rolling(w, min_periods=w).mean()
    return body.shift(k) >= float(p["long_body_vs_avg_min"]) * base - EPS


def _floor(bars: pd.DataFrame, p: dict, k: int) -> pd.Series:
    """The body k days back is at least min_large_body_ticks ticks (RAW)."""
    return raw_body_ok(bars, p["min_large_body_ticks"]).shift(k, fill_value=False)


def _star_lookback(p: dict) -> int:
    return int(p["long_body_window"]) + 2


# --- stars -------------------------------------------------------------------


@measure(
    name="morning_star",
    doc_ref="doc §3.3",
    kind="boolean",
    needs=NEEDS,
    lookback=_star_lookback,
)
def morning_star(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Long red day, a small star opening below it, then a long green day
    closing well into the red body: a bottom reversal."""
    ((o1, c1, b1), (o2, _, b2), (o3, c3, _)), body = _days(bars)
    cond = (
        (c1 < o1)
        & _long(body, 2, p)
        & (b2 <= float(p["star_body_max"]) * b1 + EPS)
        & _lt(o2, c1)  # P4: opens below d1's close, not a true gap
        & (c3 > o3)
        & _long(body, 0, p)
        & _gt(c3, c1 + float(p["min_close_into_first_body"]) * b1)
        & _floor(bars, p, 2)
        & _floor(bars, p, 0)
    )
    return boolean_from(cond, c1)


@measure(
    name="evening_star",
    doc_ref="doc §3.3",
    kind="boolean",
    needs=NEEDS,
    lookback=_star_lookback,
)
def evening_star(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Long green day, a small star opening above it, then a long red day
    closing well into the green body: a top reversal."""
    ((o1, c1, b1), (o2, _, b2), (o3, c3, _)), body = _days(bars)
    cond = (
        (c1 > o1)
        & _long(body, 2, p)
        & (b2 <= float(p["star_body_max"]) * b1 + EPS)
        & _gt(o2, c1)  # P4: opens above d1's close, not a true gap
        & (c3 < o3)
        & _long(body, 0, p)
        & _lt(c3, c1 - float(p["min_close_into_first_body"]) * b1)
        & _floor(bars, p, 2)
        & _floor(bars, p, 0)
    )
    return boolean_from(cond, c1)


# --- soldiers and crows ------------------------------------------------------


def _wick_ok(bars: pd.DataFrame, p: dict, k: int, upper: bool) -> pd.Series:
    """Day k back closes near its high (upper=True) or its low."""
    o, h, lo, c = (bars[x].astype("float64") for x in ("open", "high", "low", "close"))
    wick = h - np.maximum(o, c) if upper else np.minimum(o, c) - lo
    ok = wick <= float(p["max_wick_to_range"]) * (h - lo) + EPS
    return ok.shift(k, fill_value=False)


@measure(
    name="three_white_soldiers",
    doc_ref="doc §3.3",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: 2,
)
def three_white_soldiers(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Three rising real bodies, each opening inside the last and closing near
    its high: strong buying."""
    ((o1, c1, _), (o2, c2, _), (o3, c3, _)), _ = _days(bars)
    cond = (
        _ge(o2, o1)
        & _le(o2, c1)  # d2 opens within d1's body
        & _ge(o3, o2)
        & _le(o3, c2)  # d3 opens within d2's body
        & _gt(c2, c1)
        & _gt(c3, c2)
        & _wick_ok(bars, p, 2, upper=True)
        & _wick_ok(bars, p, 1, upper=True)
        & _wick_ok(bars, p, 0, upper=True)
        & _floor(bars, p, 2)
        & _floor(bars, p, 1)
        & _floor(bars, p, 0)
    )
    return boolean_from(cond, c1)


@measure(
    name="three_black_crows",
    doc_ref="doc §3.3",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: 2,
)
def three_black_crows(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Three falling real bodies, each opening inside the last and closing near
    its low: strong selling."""
    ((o1, c1, _), (o2, c2, _), (o3, c3, _)), _ = _days(bars)
    cond = (
        _le(o2, o1)
        & _ge(o2, c1)  # d2 opens within d1's body
        & _le(o3, o2)
        & _ge(o3, c2)  # d3 opens within d2's body
        & _lt(c2, c1)
        & _lt(c3, c2)
        & _wick_ok(bars, p, 2, upper=False)
        & _wick_ok(bars, p, 1, upper=False)
        & _wick_ok(bars, p, 0, upper=False)
        & _floor(bars, p, 2)
        & _floor(bars, p, 1)
        & _floor(bars, p, 0)
    )
    return boolean_from(cond, c1)


# --- three inside ------------------------------------------------------------


def _inside_lookback(p: dict) -> int:
    # The harami on d1-d2 reads long_body_window + 1 rows before d2.
    return int(p["long_body_window"]) + 2


@measure(
    name="three_inside_up",
    doc_ref="doc §3.3",
    kind="boolean",
    needs=NEEDS,
    lookback=_inside_lookback,
)
def three_inside_up(bars: pd.DataFrame, p: dict) -> pd.Series:
    """A bullish harami yesterday, confirmed today by a close above the first
    day's open: a confirmed reversal. The confirmation is TODAY's candle."""
    harami = pd.Series(bullish_harami(bars, p), index=bars.index).shift(1)
    o = bars["open"].astype("float64")
    c = bars["close"].astype("float64")
    cond = (harami == 1.0) & _gt(c, o.shift(2))
    return boolean_from(cond, harami)


@measure(
    name="three_inside_down",
    doc_ref="doc §3.3",
    kind="boolean",
    needs=NEEDS,
    lookback=_inside_lookback,
)
def three_inside_down(bars: pd.DataFrame, p: dict) -> pd.Series:
    """A bearish harami yesterday, confirmed today by a close below the first
    day's open."""
    harami = pd.Series(bearish_harami(bars, p), index=bars.index).shift(1)
    o = bars["open"].astype("float64")
    c = bars["close"].astype("float64")
    cond = (harami == 1.0) & _lt(c, o.shift(2))
    return boolean_from(cond, harami)
