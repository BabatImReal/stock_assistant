"""Trend and level measures for one symbol (doc §5.1 and §5.2).

Context is not decoration. Doc §5 opens on the point that a hammer and a hanging
man are the SAME SHAPE and only the preceding trend tells them apart, and that
reversal patterns need something to reverse -- a "bottom" signal with no prior
decline is not a bottom. These measures are what let a pattern rule ask that
question.

All of them read the ADJUSTED close. That matters more here than anywhere else:
a 50-session average spanning a stock dividend would otherwise average a price
series against a differently-scaled version of itself, and the resulting
"trend" would be an artefact of the corporate action.

None of them read volume, so they are available on backfilled spans where the
price is adjusted and the volume never could be. That is the price-yes /
volume-no split working as designed, and it is driven by the declared `needs`
rather than by anyone remembering it.

Support and resistance (§5.2) deserves a note on look-ahead, because the
obvious implementation has a subtle one. A pivot low is a low with higher lows
on BOTH sides, which means confirming one needs rows after it. Those rows are
in the past relative to today, so using them is legitimate -- but only if the
pivot is far enough back that its confirmation window has already closed. A
pivot within `pivot_k` rows of today is NOT yet confirmed and is excluded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import boolean_from, measure


def _ma(bars: pd.DataFrame, window: int) -> pd.Series:
    close = bars["close"].astype("float64")
    return close.rolling(window, min_periods=window).mean()


@measure(
    name="ma_20", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def ma_20(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The 20-session average of the adjusted close."""
    return _ma(bars, int(p["window_days"]))


@measure(
    name="ma_50", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def ma_50(bars: pd.DataFrame, p: dict) -> pd.Series:
    return _ma(bars, int(p["window_days"]))


def _slope(series: pd.Series, span: int) -> pd.Series:
    """Fractional change in the average over `span` sessions.

    Expressed as a fraction rather than a price difference so a 200,000 VND
    stock and a 5,000 VND one are comparable -- the same reason doc §4.1 wants
    traded value in VND rather than share counts.
    """
    return series / series.shift(span) - 1.0


@measure(
    name="ma_20_slope", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1 + int(p["slope_days"]),
)
def ma_20_slope(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Is the 20-session average rising or falling, and how fast."""
    return _slope(_ma(bars, int(p["window_days"])), int(p["slope_days"]))


@measure(
    name="ma_50_slope", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1 + int(p["slope_days"]),
)
def ma_50_slope(bars: pd.DataFrame, p: dict) -> pd.Series:
    return _slope(_ma(bars, int(p["window_days"])), int(p["slope_days"]))


@measure(
    name="price_vs_ma_20", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def price_vs_ma_20(bars: pd.DataFrame, p: dict) -> pd.Series:
    """How far above or below its 20-session average the close sits."""
    ma = _ma(bars, int(p["window_days"]))
    return bars["close"].astype("float64") / ma.replace(0.0, np.nan) - 1.0


@measure(
    name="price_vs_ma_50", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def price_vs_ma_50(bars: pd.DataFrame, p: dict) -> pd.Series:
    ma = _ma(bars, int(p["window_days"]))
    return bars["close"].astype("float64") / ma.replace(0.0, np.nan) - 1.0


@measure(
    name="price_change_10d", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]),
)
def price_change_10d(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Percentage change over the window -- the "prior decline" a reversal needs."""
    close = bars["close"].astype("float64")
    return close / close.shift(int(p["window_days"])) - 1.0


@measure(
    name="price_change_20d", doc_ref="doc §5.1", kind="numeric", needs=("close",),
    lookback=lambda p: int(p["window_days"]),
)
def price_change_20d(bars: pd.DataFrame, p: dict) -> pd.Series:
    close = bars["close"].astype("float64")
    return close / close.shift(int(p["window_days"])) - 1.0


def _pivots(values: np.ndarray, k: int, kind: str) -> np.ndarray:
    """Confirmed pivot lows or highs.

    A pivot at j needs k rows either side, so `pivots[j]` is only meaningful
    once row j+k exists. The caller enforces that; this just marks the shape.
    """
    n = len(values)
    flag = np.zeros(n, dtype=bool)
    for j in range(k, n - k):
        window = values[j - k : j + k + 1]
        if kind == "low":
            flag[j] = values[j] == window.min() and values[j] < window[k + 1 :].min()
        else:
            flag[j] = values[j] == window.max() and values[j] > window[k + 1 :].max()
    return flag


def _near_level(
    bars: pd.DataFrame, p: dict, kind: str
) -> tuple[pd.Series, pd.Series]:
    """Is today's extreme near a level that held at least `min_touches` times?

    Doc §5.2's sketch: "is today's low within ~2% of a low that held at least
    twice in the last 60 days?" A level that turned price away once is an
    accident; twice is a level.
    """
    lookback = int(p["lookback_days"])
    k = int(p["pivot_k"])
    tol = float(p["tolerance"])
    min_touches = int(p["min_touches"])

    price_col = "low" if kind == "low" else "high"
    prices = bars[price_col].astype("float64").to_numpy()
    pivot = _pivots(prices, k, kind)

    n = len(prices)
    near = np.full(n, np.nan)
    touches = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - lookback + 1)
        # Only pivots whose confirmation window has closed by row i.
        confirmed = [
            prices[j] for j in range(lo, max(lo, i - k + 1)) if pivot[j]
        ]
        if i < lookback - 1:
            continue
        today = prices[i]
        if today <= 0:
            continue
        hits = sum(1 for level in confirmed if abs(level - today) <= tol * today)
        touches[i] = hits
        near[i] = 1.0 if hits >= min_touches else 0.0
    return pd.Series(near, index=bars.index), pd.Series(touches, index=bars.index)


@measure(
    name="near_support", doc_ref="doc §5.2", kind="boolean", needs=("low",),
    lookback=lambda p: int(p["lookback_days"]) - 1,
)
def near_support(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Today's low sits on a level that has stopped falls at least twice."""
    near, touches = _near_level(bars, p, "low")
    return boolean_from(near.fillna(0).astype(bool), touches)


@measure(
    name="near_resistance", doc_ref="doc §5.2", kind="boolean", needs=("high",),
    lookback=lambda p: int(p["lookback_days"]) - 1,
)
def near_resistance(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Today's high sits on a level that has capped rises at least twice."""
    near, touches = _near_level(bars, p, "high")
    return boolean_from(near.fillna(0).astype(bool), touches)
