"""Volume measures (doc §4.1).

Ben's correction to a pattern-only view: a candle shape without volume behind it
is just a drawing. Heavy volume sustained over several days means real capital is
entering the company, and that is often more informative than the shape. So each
of these is a rule in exactly the sense a pattern is: written down once, run over
all history, and measured against what happened next.

ALL of them read MATCHED volume only (doc §4.3). `bar_adjusted.matched_volume`
is matched volume -- that is what the G12 test established, on the 20 stock-days
with the largest block deals, where it equalled matched-only 20/20 and
matched+deal 0/20. Negotiated volume lives in its own table and nothing here
touches it.

Two conventions used throughout:

- A "relative" figure divides today by the average of the PREVIOUS N sessions,
  excluding today. Including today would let a huge day inflate its own
  denominator and quietly understate exactly the spikes we care about.
- Thresholds come from config, never from here (doc §3.5).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import measure


def _rvol(bars: pd.DataFrame, lookback: int) -> pd.Series:
    """Today's matched volume ÷ the mean of the previous `lookback` sessions."""
    vol = bars["matched_volume"].astype("float64")
    prior_mean = vol.shift(1).rolling(lookback, min_periods=lookback).mean()
    return vol / prior_mean.replace(0.0, np.nan)


@measure(
    name="rvol",
    doc_ref="doc §4.1",
    kind="numeric",
    needs=("matched_volume",),
    lookback=lambda p: int(p["lookback_days"]) + 1,
)
def rvol(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Relative volume. Above ~1.5-2x is unusual interest (doc §4.1)."""
    return _rvol(bars, int(p["lookback_days"]))


@measure(
    name="sustained_volume",
    doc_ref="doc §4.1",
    kind="numeric",
    needs=("matched_volume",),
    lookback=lambda p: int(p["window_days"]) + int(p["rvol_lookback_days"]) + 1,
)
def sustained_volume(bars: pd.DataFrame, p: dict) -> pd.Series:
    """How many of the last N sessions were heavy.

    This is the measure that separates real accumulation from a single spike:
    doc §4 makes the point that volume persisting for 5-7 days is capital
    entering the company, while one big day is often just one big order.
    """
    window = int(p["window_days"])
    heavy = _rvol(bars, int(p["rvol_lookback_days"])) > float(p["threshold"])
    return heavy.astype("float64").rolling(window, min_periods=window).sum()


@measure(
    name="up_down_volume_ratio",
    doc_ref="doc §4.1",
    kind="numeric",
    needs=("matched_volume", "close"),
    lookback=lambda p: int(p["window_days"]),
)
def up_down_volume_ratio(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Volume traded on up days ÷ volume on down days, over the window.

    Who is in control. Above 1 means the heavy days were the rising ones.
    A window with no down days at all divides by zero, which is genuinely
    unbounded rather than infinite-and-meaningful, so it comes back NaN.
    """
    window = int(p["window_days"])
    vol = bars["matched_volume"].astype("float64")
    change = bars["close"].astype("float64").diff()
    up = vol.where(change > 0, 0.0).rolling(window, min_periods=window).sum()
    down = vol.where(change < 0, 0.0).rolling(window, min_periods=window).sum()
    return up / down.replace(0.0, np.nan)


def _changes(bars: pd.DataFrame, window: int) -> tuple[pd.Series, pd.Series]:
    """Price change and average-volume change over the window."""
    close = bars["close"].astype("float64")
    vol = bars["matched_volume"].astype("float64")
    price_change = close / close.shift(window) - 1.0
    recent = vol.rolling(window, min_periods=window).mean()
    earlier = vol.shift(window).rolling(window, min_periods=window).mean()
    volume_change = recent / earlier.replace(0.0, np.nan) - 1.0
    return price_change, volume_change


@measure(
    name="price_volume_agreement",
    doc_ref="doc §4.1",
    kind="boolean",
    needs=("matched_volume", "close"),
    lookback=lambda p: 2 * int(p["window_days"]),
)
def price_volume_agreement(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Price rising AND volume rising: a healthy move (doc §4.1)."""
    price_change, volume_change = _changes(bars, int(p["window_days"]))
    return (price_change >= float(p["min_price_change"])) & (
        volume_change >= float(p["min_volume_change"])
    )


@measure(
    name="price_volume_divergence",
    doc_ref="doc §4.1",
    kind="boolean",
    needs=("matched_volume", "close"),
    lookback=lambda p: 2 * int(p["window_days"]),
)
def price_volume_divergence(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Price rising while volume shrinks: the move running out of fuel."""
    price_change, volume_change = _changes(bars, int(p["window_days"]))
    return (price_change >= float(p["min_price_change"])) & (
        volume_change <= float(p["max_volume_change"])
    )


@measure(
    name="traded_value",
    doc_ref="doc §4.1",
    kind="numeric",
    needs=("matched_volume", "close"),
    lookback=lambda p: 0,
)
def traded_value(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Close x matched volume, in thousands of VND.

    Real money, comparable across a 5,000 VND stock and a 200,000 VND one in a
    way share counts are not. This is also the quantity the liquidity floor in
    config/rules/universe.yaml is expressed in.

    Note it is invariant under adjustment -- price x factor times volume ÷
    factor -- which is exactly the traded-value invariant the data-quality gate
    checks on every row. It still requires volume_is_adjustable, because on a
    backfilled span the price is adjusted and the volume is not, so the product
    is the one thing that ISN'T invariant there.
    """
    return bars["close"].astype("float64") * bars["matched_volume"].astype("float64")


@measure(
    name="volume_dry_up",
    doc_ref="doc §4.1",
    kind="boolean",
    needs=("matched_volume",),
    lookback=lambda p: int(p["quiet_days"]) + int(p["rvol_lookback_days"]) + 1,
)
def volume_dry_up(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Volume well below average for several sessions running.

    Doc §4.1 reads this as sellers being exhausted, and it often precedes a
    breakout. Requiring several quiet days rather than one is deliberate: a
    single thin session is frequently a holiday or a half-day, not a message.
    """
    quiet = _rvol(bars, int(p["rvol_lookback_days"])) < float(p["max_rvol"])
    days = int(p["quiet_days"])
    return quiet.astype("float64").rolling(days, min_periods=days).sum() == days
