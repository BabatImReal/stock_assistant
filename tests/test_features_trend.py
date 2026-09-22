"""Tests for the §5.1-5.2 trend and level measures.

Two things carry most of the weight here: that support and resistance do not
peek at rows after the pivot they are confirming, and that these measures REMAIN
available on backfilled spans. The second is the complement of the volume guard
-- Ben's price-yes / volume-no decision only works if both halves hold.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.features import REGISTRY, compute
from vnstock_research.features.trend import _pivots

from ._helpers import frame

MA20 = {"ma_20": {"enabled": True, "window_days": 20}}
SUPPORT = {
    "near_support": {
        "enabled": True, "lookback_days": 60, "pivot_k": 2,
        "tolerance": 0.02, "min_touches": 2,
    }
}


def test_moving_average_is_the_mean_of_the_window():
    close = list(np.arange(1.0, 41.0))
    out, _ = compute(frame(n=40, close=close), MA20)
    assert out["ma_20"].iloc[39] == pytest.approx(np.mean(close[20:40]))


def test_moving_average_needs_a_full_window():
    out, _ = compute(frame(n=40, close=list(np.arange(1.0, 41.0))), MA20)
    assert np.isnan(out["ma_20"].iloc[18])
    assert not np.isnan(out["ma_20"].iloc[19])


def test_slope_is_positive_on_a_rising_average_and_negative_on_a_falling_one():
    cfg = {"ma_20_slope": {"enabled": True, "window_days": 20, "slope_days": 5}}
    rising, _ = compute(frame(n=40, close=list(np.arange(1.0, 41.0))), cfg)
    falling, _ = compute(frame(n=40, close=list(np.arange(41.0, 1.0, -1.0))), cfg)
    assert rising["ma_20_slope"].iloc[39] > 0
    assert falling["ma_20_slope"].iloc[39] < 0


def test_price_change_measures_the_prior_move_a_reversal_needs():
    # doc §5.1: a "bottom" signal with no prior decline is not a bottom.
    close = [100.0] * 20 + [80.0] * 20
    cfg = {"price_change_10d": {"enabled": True, "window_days": 10}}
    out, _ = compute(frame(n=40, close=close), cfg)
    assert out["price_change_10d"].iloc[25] == pytest.approx(-0.2)


# --- trend measures must survive where volume measures cannot --------------

def test_trend_measures_still_compute_on_a_non_adjustable_volume_span():
    """The complement of the volume guard, and half of Ben's decision.

    A backfilled span has an adjusted price and an unadjustable volume. Price
    patterns and trend are usable there; volume signals are not. If this ever
    fails, the price half of that decision has been silently lost.
    """
    df = frame(n=40, close=list(np.arange(1.0, 41.0)), adjustable=[30, 31, 32])
    out, _ = compute(df, MA20)
    assert not np.isnan(out["ma_20"].iloc[32])
    assert not np.isnan(out["ma_20"].iloc[35])


def test_trend_measures_still_respect_the_gap_rule():
    # Price-only does not mean guard-free: an average spanning a suspension
    # still averages the wrong days.
    df = frame(n=40, close=list(np.arange(1.0, 41.0)), gaps=[25])
    out, _ = compute(df, MA20)
    assert np.isnan(out["ma_20"].iloc[30])


def test_price_only_measures_do_not_declare_volume():
    for name in ("ma_20", "ma_50", "ma_20_slope", "price_vs_ma_20",
                 "price_change_10d", "near_support", "near_resistance"):
        assert not REGISTRY[name].reads_volume, name


# --- support and resistance ------------------------------------------------

def test_pivot_low_is_the_lowest_point_of_its_neighbourhood():
    values = np.array([5.0, 4.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    flags = _pivots(values, 2, "low")
    assert flags[2]
    assert not flags[1]


def test_near_support_needs_two_touches_not_one():
    """One bounce is an accident; doc §5.2 asks for a level that held twice."""
    close = [50.0] * 80
    low = np.array(close, dtype=float)
    low[20] = 40.0                       # a single pivot low at 40
    df = frame(n=80, close=close)
    df["low"] = low
    df.loc[79, "low"] = 40.2             # today revisits it -- but only once before
    out, _ = compute(df, SUPPORT)
    assert out["near_support"].iloc[79] == 0.0

    low[45] = 40.1                       # now the level has held twice
    df["low"] = low
    df.loc[79, "low"] = 40.2
    out, _ = compute(df, SUPPORT)
    assert out["near_support"].iloc[79] == 1.0


def test_near_support_does_not_use_an_unconfirmed_pivot():
    """A pivot needs rows on BOTH sides, so one within pivot_k of today has not
    been confirmed yet and counting it would be look-ahead.

    The pivot sits at row 60 and is evaluated at row 61, which is INSIDE its
    confirmation window: confirming it needs row 62, which row 61 cannot see.
    An earlier version of this test placed the pivot at the very end of the
    frame, where `_pivots` never marks it anyway, so it passed with the guard
    removed and tested nothing.
    """
    close = [50.0] * 90
    low = np.array(close, dtype=float)
    low[20] = 40.0            # an old, fully confirmed pivot
    low[60] = 40.1            # a pivot whose confirmation window is still open
    low[61] = 40.2            # row 61, sitting on the level
    low[63] = 40.2            # and again once the window has closed
    df = frame(n=90, close=close)
    df["low"] = low
    out, _ = compute(df, SUPPORT)
    # Only ONE confirmed touch is visible from row 61, so the level does not
    # qualify. Counting the row-60 pivot would make it two.
    assert out["near_support"].iloc[61] == 0.0
    # By row 63 the confirmation window has closed and it counts.
    assert out["near_support"].iloc[63] == 1.0


def test_support_cannot_see_the_future():
    close = [50.0] * 90
    low = np.array(close, dtype=float)
    low[20], low[45] = 40.0, 40.1
    df = frame(n=90, close=close)
    df["low"] = low
    df.loc[70, "low"] = 40.2
    full, _ = compute(df, SUPPORT)
    truncated, _ = compute(df.iloc[:71].copy(), SUPPORT)
    pd.testing.assert_series_equal(
        full["near_support"].iloc[:71], truncated["near_support"],
        check_names=False,
    )


def test_a_gap_in_the_pivot_confirmation_margin_returns_nan():
    """The gap leak Ben found in shipped code.

    `near_support` looks back `lookback_days` rows for levels, but the pivot at
    that window's LEFT EDGE is itself confirmed by reading `pivot_k` rows
    further back still. Those rows sit outside the window the guard checks, so a
    suspension landing in that margin used to pass unnoticed and the measure
    could fire on a level confirmed across it.

    Row 80 scores a window starting at row 21; the pivot at row 21 reads rows 19
    and 20. The gap goes at row 20 -- inside the margin, outside the old
    declaration.
    """
    close = [50.0] * 90
    df = frame(n=90, close=close, gaps=[20])
    out, _ = compute(df, SUPPORT)
    assert np.isnan(out["near_support"].iloc[80])
    # Far enough past the margin, it scores again.
    assert not np.isnan(out["near_support"].iloc[89])
