"""Tranche 1 of the pattern catalogue (doc §3.1): candle anatomy and the
single-candle shapes. Plain arithmetic on one day's candle; no picture.

Vocabulary (doc §3): body = |close - open|; range = high - low; upper wick =
high - max(open, close); lower wick = min(open, close) - low.

Two kinds of measure:

- ANATOMY (numeric): body_to_range, upper_wick_to_range, lower_wick_to_range,
  range_rel_20d, open_gap. These carry the "cases" of doc §3.6: a hammer by a
  hair and a hammer by 5x are the same flag but different numbers. NaN where
  the range is 0 (a flat bar: every ratio is undefined).

- SHAPES (boolean): hammer_shape, inverted_hammer_shape, doji, marubozu_green,
  marubozu_red. ONE flag per shape (Ben, P1): hammer and hanging man are the
  same shape, and so are inverted hammer and shooting star (doc §3.1). The
  trend before the candle comes from the trend measures already in the
  fingerprint and is never baked into a flag.

Shapes are measured on the ADJUSTED candle. Within one day that is the raw
candle times a constant factor, so every ratio is the same.

THE TICK FLOOR (Ben, P5): every shape also requires the RAW range to be at
least `min_range_ticks` ticks. Without it, a candle 1-2 ticks tall is a doji or
a marubozu by accident, and a 1-tick candle with open = close = high passes
every hammer ratio (its body is 0, so "lower wick >= 2 x body" holds for any
wick). The flag must mean something on its own, not only when a consumer also
checks range_rel_20d. The tick (data/checks.py `floor_tick`) is the tick of the
exchange the stock was DATED to that day (data/exchanges.py). Where the
exchange is not dated, it is the LARGEST tick any exchange had at that price
and date, which can only make the floor stricter, so those days need no flag.
(Using the largest tick everywhere was tried first: it overshot HOSE's real
tick 2-10x on 64% of dated liquid HOSE days and dropped about 1 real candle in
10, on HOSE only.) On backfilled spans the "raw" prices are vnstock's adjusted
ones, lower than the real prices, so the floor is stricter there, never
looser.

Thresholds live in config/rules/features.yaml (Ben, P2), fixed before any
measuring (doc §3.5, §8.1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.checks import floor_tick
from ..features.base import boolean_from, measure

OHLC = ("open", "high", "low", "close")
RAW = ("raw_high", "raw_low", "raw_close", "exchange", "exchange_unknown")
# Prices are in thousands of VND with two decimals: absorb float noise when
# comparing a range with a whole number of ticks.
EPS = 1e-9


def _parts(bars: pd.DataFrame):
    o, h, lo, c = (bars[k].astype("float64") for k in OHLC)
    body = (c - o).abs()
    rng = h - lo
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - lo
    return o, h, lo, c, body, rng, upper, lower


def _floor_ok(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The RAW range is at least min_range_ticks ticks (`floor_tick`)."""
    raw_range = bars["raw_high"].astype("float64") - bars["raw_low"].astype("float64")
    tick = floor_tick(
        bars["trade_date"],
        bars["raw_close"],
        bars["exchange"],
        bars["exchange_unknown"],
    )
    return raw_range >= float(p["min_range_ticks"]) * tick - EPS


# --- anatomy -----------------------------------------------------------------


@measure(
    name="body_to_range",
    doc_ref="doc §3",
    kind="numeric",
    needs=OHLC,
    lookback=lambda p: 0,
)
def body_to_range(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The body's share of the day's range: 0 = all wick, 1 = all body."""
    *_, body, rng, _, _ = _parts(bars)
    return body / rng  # 0/0 on a flat bar is NaN: undefined, as it should be


@measure(
    name="upper_wick_to_range",
    doc_ref="doc §3",
    kind="numeric",
    needs=OHLC,
    lookback=lambda p: 0,
)
def upper_wick_to_range(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The upper wick's share of the day's range: selling from the high."""
    *_, rng, upper, _ = _parts(bars)
    return upper / rng  # 0/0 on a flat bar is NaN: undefined, as it should be


@measure(
    name="lower_wick_to_range",
    doc_ref="doc §3",
    kind="numeric",
    needs=OHLC,
    lookback=lambda p: 0,
)
def lower_wick_to_range(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The lower wick's share of the day's range: buying from the low."""
    *_, rng, _, lower = _parts(bars)
    return lower / rng  # 0/0 on a flat bar is NaN: undefined, as it should be


@measure(
    name="range_rel_20d",
    doc_ref="doc §3.6",
    kind="numeric",
    needs=OHLC,
    lookback=lambda p: int(p["window_days"]),
)
def range_rel_20d(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Today's range over the mean range of the PREVIOUS window_days sessions:
    how big this candle is for this stock. Today is not in its own baseline."""
    w = int(p["window_days"])
    *_, rng, _, _ = _parts(bars)
    base = rng.shift(1).rolling(w, min_periods=w).mean()
    return rng / base.replace(0.0, np.nan)


@measure(
    name="open_gap",
    doc_ref="doc §3.6",
    kind="numeric",
    needs=OHLC,
    lookback=lambda p: 1,
)
def open_gap(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Today's open against yesterday's close. Price limits keep VN gaps small,
    which is why the two-candle rules relax textbook gaps (P4)."""
    o, _, _, c, *_ = _parts(bars)
    return o / c.shift(1) - 1.0


# --- shapes ------------------------------------------------------------------


@measure(
    name="hammer_shape",
    doc_ref="doc §3.1",
    kind="boolean",
    needs=OHLC + RAW,
    lookback=lambda p: 0,
)
def hammer_shape(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Long lower wick, small upper wick, body in the top part of the range.
    A hammer after a decline, a hanging man after a rise: the trend measures
    say which."""
    o, _, lo, c, body, rng, upper, lower = _parts(bars)
    cond = (
        (lower >= float(p["lower_wick_to_body_min"]) * body - EPS)
        & (upper <= float(p["upper_wick_to_body_max"]) * body + EPS)
        & (np.minimum(o, c) >= lo + float(p["body_min_position"]) * rng - EPS)
        & _floor_ok(bars, p)
    )
    return boolean_from(cond, c)


@measure(
    name="inverted_hammer_shape",
    doc_ref="doc §3.1",
    kind="boolean",
    needs=OHLC + RAW,
    lookback=lambda p: 0,
)
def inverted_hammer_shape(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The mirror: long upper wick, small lower wick, body in the bottom part.
    Inverted hammer after a decline, shooting star after a rise."""
    o, _, lo, c, body, rng, upper, lower = _parts(bars)
    cond = (
        (upper >= float(p["upper_wick_to_body_min"]) * body - EPS)
        & (lower <= float(p["lower_wick_to_body_max"]) * body + EPS)
        & (np.maximum(o, c) <= lo + float(p["body_max_position"]) * rng + EPS)
        & _floor_ok(bars, p)
    )
    return boolean_from(cond, c)


@measure(
    name="doji",
    doc_ref="doc §3.1",
    kind="boolean",
    needs=OHLC + RAW,
    lookback=lambda p: 0,
)
def doji(bars: pd.DataFrame, p: dict) -> pd.Series:
    """A body that is a small share of a range big enough to mean something."""
    *_, c, body, rng, _, _ = _parts(bars)
    cond = (body <= float(p["body_to_range_max"]) * rng + EPS) & _floor_ok(bars, p)
    return boolean_from(cond, c)


def _marubozu(bars: pd.DataFrame, p: dict, green: bool) -> pd.Series:
    o, _, _, c, body, rng, _, _ = _parts(bars)
    colour = c > o if green else c < o
    cond = (
        colour
        & (body >= float(p["body_to_range_min"]) * rng - EPS)
        & _floor_ok(bars, p)
    )
    return boolean_from(cond, c)


@measure(
    name="marubozu_green",
    direction="bullish",
    doc_ref="doc §3.1",
    kind="boolean",
    needs=OHLC + RAW,
    lookback=lambda p: 0,
)
def marubozu_green(bars: pd.DataFrame, p: dict) -> pd.Series:
    """A rising day that is nearly all body: buyers from open to close."""
    return _marubozu(bars, p, green=True)


@measure(
    name="marubozu_red",
    direction="bearish",
    doc_ref="doc §3.1",
    kind="boolean",
    needs=OHLC + RAW,
    lookback=lambda p: 0,
)
def marubozu_red(bars: pd.DataFrame, p: dict) -> pd.Series:
    """A falling day that is nearly all body: sellers from open to close."""
    return _marubozu(bars, p, green=False)
