"""Tests for patterns tranche 2 (patterns/two_candle.py): two-candle patterns.

One test per rule; each fails if its rule is removed. The last candle is
"today". Default exchange HNX on 2020 dates: a tick of 0.1, so the prior-body
floor is a raw body of 0.3.
"""

import numpy as np
import pytest

from .test_candles import bars, run

BASE = (20.0, 20.6, 19.9, 20.5)  # a neutral day, body 0.5


def today(name, candles, **kw):
    return run(name, bars(candles), **kw).iloc[-1]


def harami(name, d1, d2, **kw):
    """Twenty days of body 0.5, then yesterday (d1) and today (d2)."""
    return today(name, [BASE] * 20 + [d1, d2], **kw)


# --- bullish engulfing -------------------------------------------------------

BULL_D1 = (21.0, 21.1, 20.4, 20.5)  # red, body 0.5
BULL_D2 = (20.5, 21.2, 20.4, 21.1)  # opens AT close1 (a tie), closes above open1


def test_bullish_engulfing_fires():
    assert today("bullish_engulfing", [BULL_D1, BULL_D2]) == 1.0


def test_bullish_engulfing_needs_a_red_yesterday():
    d1 = (20.5, 21.1, 20.4, 21.0)  # green: today "covering" it is not engulfing
    assert today("bullish_engulfing", [d1, (20.4, 21.2, 20.3, 21.1)]) == 0.0


def test_bullish_engulfing_needs_the_open_at_or_below_yesterdays_close():
    assert today("bullish_engulfing", [BULL_D1, (20.6, 21.2, 20.5, 21.1)]) == 0.0


def test_bullish_engulfing_needs_the_close_at_or_above_yesterdays_open():
    # Opens well below close1 with a body (0.55) bigger than yesterday's, so
    # only this rule fails: the close stops short of open1.
    assert today("bullish_engulfing", [BULL_D1, (20.3, 20.9, 20.2, 20.85)]) == 0.0


def test_bullish_engulfing_body_cover_binds_when_set_above_one():
    # Covering already implies body2 >= body1; at 1.5x it binds (0.6 vs 0.5).
    candles = [BULL_D1, BULL_D2]
    assert today("bullish_engulfing", candles, min_body_cover=1.0) == 1.0
    assert today("bullish_engulfing", candles, min_body_cover=1.5) == 0.0


def test_bullish_engulfing_needs_yesterdays_body_above_the_tick_floor():
    tiny = (20.7, 20.8, 20.4, 20.5)  # a red body of 2 ticks
    assert today("bullish_engulfing", [tiny, (20.5, 20.9, 20.4, 20.8)]) == 0.0
    three = (20.8, 20.9, 20.4, 20.5)  # 3 ticks: a real body
    assert today("bullish_engulfing", [three, (20.5, 20.9, 20.4, 20.9)]) == 1.0


def test_a_raw_tie_nudged_by_adjustment_rounding_still_counts():
    """open2 == close1 in raw terms, 5e-5 apart after adjustment (the median
    jitter is 0, the 99th percentile 2.6e-5): still at the close."""
    d2 = (20.5 * (1 + 5e-5), 21.2, 20.4, 21.1)
    assert today("bullish_engulfing", [BULL_D1, d2]) == 1.0


# --- bearish engulfing -------------------------------------------------------

BEAR_D1 = (20.5, 21.1, 20.4, 21.0)  # green, body 0.5
BEAR_D2 = (21.0, 21.2, 20.3, 20.4)


def test_bearish_engulfing_fires():
    assert today("bearish_engulfing", [BEAR_D1, BEAR_D2]) == 1.0


def test_bearish_engulfing_needs_a_green_yesterday():
    assert today("bearish_engulfing", [BULL_D1, (21.1, 21.2, 20.3, 20.4)]) == 0.0


def test_bearish_engulfing_needs_the_open_at_or_above_yesterdays_close():
    assert today("bearish_engulfing", [BEAR_D1, (20.9, 21.0, 20.3, 20.4)]) == 0.0


def test_bearish_engulfing_needs_the_close_at_or_below_yesterdays_open():
    # Opens above close1 with a bigger body (0.6): only the close fails.
    assert today("bearish_engulfing", [BEAR_D1, (21.2, 21.3, 20.5, 20.6)]) == 0.0


def test_bearish_engulfing_needs_yesterdays_body_above_the_tick_floor():
    tiny = (20.5, 20.8, 20.4, 20.7)
    assert today("bearish_engulfing", [tiny, (20.7, 20.8, 20.3, 20.4)]) == 0.0


# --- bullish harami ----------------------------------------------------------

HARAMI_BULL_D1 = (21.0, 21.1, 19.9, 20.0)  # red, body 1.0 vs a 0.5 average
HARAMI_BULL_D2 = (20.3, 20.6, 20.2, 20.5)  # body 0.2 inside 20.0..21.0


def test_bullish_harami_fires():
    assert harami("bullish_harami", HARAMI_BULL_D1, HARAMI_BULL_D2) == 1.0


def test_bullish_harami_needs_a_long_yesterday():
    d1 = (20.6, 20.7, 20.1, 20.2)  # red, body 0.4 < the 0.5 average
    assert harami("bullish_harami", d1, (20.3, 20.5, 20.25, 20.4)) == 0.0


def test_long_is_judged_against_the_sessions_before_yesterday():
    """At 1.1x a 0.5 baseline, a 0.5515 body is long. Folding yesterday into its
    own baseline (0.5026) would demand 0.5528, and it would not be."""
    d1 = (20.5515, 20.6, 19.95, 20.0)
    d2 = (20.1, 20.3, 20.05, 20.2)
    assert harami("bullish_harami", d1, d2, long_body_vs_avg_min=1.1) == 1.0


def test_bullish_harami_needs_todays_body_below_yesterdays_open():
    assert harami("bullish_harami", HARAMI_BULL_D1, (20.9, 21.2, 20.8, 21.1)) == 0.0


def test_bullish_harami_needs_todays_body_above_yesterdays_close():
    assert harami("bullish_harami", HARAMI_BULL_D1, (19.9, 20.2, 19.8, 20.1)) == 0.0


def test_bullish_harami_needs_todays_body_small():
    # Inside 20.0..21.0 but 0.6 of yesterday's body.
    assert harami("bullish_harami", HARAMI_BULL_D1, (20.2, 20.9, 20.1, 20.8)) == 0.0


def test_bullish_harami_needs_yesterdays_body_above_the_tick_floor():
    """Tiny bodies all round: yesterday's 0.2 is 4x its 0.05 average (long),
    and today sits inside it, but 2 ticks is noise."""
    tiny = (20.0, 20.1, 19.95, 20.05)
    d1, d2 = (20.2, 20.25, 19.95, 20.0), (20.05, 20.15, 20.0, 20.1)
    assert today("bullish_harami", [tiny] * 20 + [d1, d2]) == 0.0


def test_harami_is_blank_when_its_long_body_baseline_spans_a_gap():
    df = bars([BASE] * 20 + [HARAMI_BULL_D1, HARAMI_BULL_D2], gaps=[10])
    assert np.isnan(run("bullish_harami", df).iloc[-1])


# --- bearish harami ----------------------------------------------------------

HARAMI_BEAR_D1 = (20.0, 21.1, 19.9, 21.0)  # green, body 1.0
HARAMI_BEAR_D2 = (20.5, 20.6, 20.2, 20.3)


def test_bearish_harami_fires():
    assert harami("bearish_harami", HARAMI_BEAR_D1, HARAMI_BEAR_D2) == 1.0


def test_bearish_harami_needs_a_long_yesterday():
    d1 = (20.2, 20.7, 20.1, 20.6)  # green, body 0.4
    assert harami("bearish_harami", d1, (20.4, 20.5, 20.25, 20.3)) == 0.0


def test_bearish_harami_needs_todays_body_below_yesterdays_close():
    assert harami("bearish_harami", HARAMI_BEAR_D1, (21.1, 21.2, 20.8, 20.9)) == 0.0


def test_bearish_harami_needs_todays_body_above_yesterdays_open():
    assert harami("bearish_harami", HARAMI_BEAR_D1, (20.1, 20.2, 19.8, 19.9)) == 0.0


def test_bearish_harami_needs_todays_body_small():
    assert harami("bearish_harami", HARAMI_BEAR_D1, (20.8, 20.9, 20.1, 20.2)) == 0.0


def test_bearish_harami_needs_yesterdays_body_above_the_tick_floor():
    tiny = (20.0, 20.1, 19.95, 20.05)
    d1, d2 = (20.0, 20.25, 19.95, 20.2), (20.15, 20.2, 20.05, 20.1)
    assert today("bearish_harami", [tiny] * 20 + [d1, d2]) == 0.0


# --- piercing line and dark cloud cover --------------------------------------

PIERCE_D1 = (21.0, 21.1, 19.9, 20.0)  # red, body 1.0, midpoint 20.5
PIERCE_D2 = (19.9, 20.8, 19.8, 20.7)  # opens lower, closes past the midpoint


def test_piercing_line_fires():
    assert today("piercing_line", [PIERCE_D1, PIERCE_D2]) == 1.0


def test_piercing_line_needs_an_open_below_yesterdays_close():
    # At the close is not below it; nor is a rounding nudge under it.
    assert today("piercing_line", [PIERCE_D1, (20.0, 20.8, 19.9, 20.7)]) == 0.0
    nudged = (20.0 * (1 - 5e-5), 20.8, 19.9, 20.7)
    assert today("piercing_line", [PIERCE_D1, nudged]) == 0.0


def test_piercing_line_needs_a_close_past_the_midpoint():
    assert today("piercing_line", [PIERCE_D1, (19.9, 20.5, 19.8, 20.4)]) == 0.0


def test_piercing_line_needs_a_close_short_of_yesterdays_open():
    # Past the open it is an engulfing, not a piercing line.
    assert today("piercing_line", [PIERCE_D1, (19.9, 21.2, 19.8, 21.1)]) == 0.0


def test_piercing_line_needs_yesterdays_body_above_the_tick_floor():
    tiny = (20.2, 20.3, 19.95, 20.0)  # 2 ticks, midpoint 20.1
    assert today("piercing_line", [tiny, (19.9, 20.2, 19.85, 20.15)]) == 0.0


DARK_D1 = (20.0, 21.1, 19.9, 21.0)  # green, body 1.0, midpoint 20.5
DARK_D2 = (21.1, 21.2, 20.2, 20.3)


def test_dark_cloud_cover_fires():
    assert today("dark_cloud_cover", [DARK_D1, DARK_D2]) == 1.0


def test_dark_cloud_cover_needs_an_open_above_yesterdays_close():
    assert today("dark_cloud_cover", [DARK_D1, (21.0, 21.1, 20.2, 20.3)]) == 0.0


def test_dark_cloud_cover_needs_a_close_past_the_midpoint():
    assert today("dark_cloud_cover", [DARK_D1, (21.1, 21.2, 20.5, 20.6)]) == 0.0


def test_dark_cloud_cover_needs_a_close_short_of_yesterdays_open():
    assert today("dark_cloud_cover", [DARK_D1, (21.1, 21.2, 19.8, 19.9)]) == 0.0


def test_dark_cloud_cover_needs_yesterdays_body_above_the_tick_floor():
    tiny = (20.0, 20.25, 19.95, 20.2)
    assert today("dark_cloud_cover", [tiny, (20.3, 20.35, 20.0, 20.05)]) == 0.0


# --- the yesterday-adjacent rule and friends -----------------------------------

PAIRS = {
    "bullish_engulfing": [BULL_D1, BULL_D2],
    "bearish_engulfing": [BEAR_D1, BEAR_D2],
    "bullish_harami": [BASE] * 20 + [HARAMI_BULL_D1, HARAMI_BULL_D2],
    "bearish_harami": [BASE] * 20 + [HARAMI_BEAR_D1, HARAMI_BEAR_D2],
    "piercing_line": [PIERCE_D1, PIERCE_D2],
    "dark_cloud_cover": [DARK_D1, DARK_D2],
}


@pytest.mark.parametrize("name", PAIRS)
def test_a_pair_that_straddles_a_trading_gap_is_blank(name):
    """Yesterday's candle before a suspension is not yesterday."""
    candles = PAIRS[name]
    assert run(name, bars(candles)).iloc[-1] == 1.0
    assert np.isnan(run(name, bars(candles, gaps=[len(candles) - 1])).iloc[-1])


@pytest.mark.parametrize("name", PAIRS)
def test_an_excluded_yesterday_blanks_the_pair(name):
    candles = PAIRS[name]
    df = bars(candles, excluded=[len(candles) - 2])
    assert np.isnan(run(name, df).iloc[-1])


@pytest.mark.parametrize("name", PAIRS)
def test_a_pair_cannot_see_the_future(name):
    candles = PAIRS[name] + [BASE] * 3
    full, cut = run(name, bars(candles)), run(name, bars(candles[:-3]))
    assert full.iloc[len(candles) - 4] == cut.iloc[-1] == 1.0
