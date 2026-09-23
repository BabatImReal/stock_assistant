"""Tests for patterns tranche 3 (patterns/three_candle.py): three-candle patterns.

One test per rule; each fails if its rule is removed. The last candle is day 3
("today"). Default exchange HNX on 2020 dates: a 0.1 tick, so the large-body
floor is a raw body of 0.3.

Bearish patterns are tested by MIRRORING the bullish cases: every price p
becomes 41 - p (high and low swap). That maps a morning star onto an evening
star, soldiers onto crows and three-inside-up onto three-inside-down at the
same price level (same ticks), so each bearish rule is tested by exactly the
case that tests its bullish twin.
"""

import numpy as np
import pytest

from .test_candles import bars, run

BASE = (20.0, 20.6, 19.9, 20.5)  # body 0.5: the pre-pattern baseline
TINY = (20.0, 20.1, 19.95, 20.05)  # body 0.05: a tiny baseline


def mirror(c):
    o, h, lo, cl = c
    return (41 - o, 41 - lo, 41 - h, 41 - cl)


def fire(name, days, base=BASE, bear=False, **kw):
    """Twenty baseline days, then the pattern's days; value on the last."""
    candles = [base] * 20 + list(days)
    if bear:
        candles = [mirror(c) for c in candles]
    return run(name, bars(candles), **kw).iloc[-1]


BOTH = pytest.mark.parametrize("bear", [False, True], ids=["bullish", "bearish"])
STAR = {False: "morning_star", True: "evening_star"}
SOLDIERS = {False: "three_white_soldiers", True: "three_black_crows"}
INSIDE = {False: "three_inside_up", True: "three_inside_down"}

# --- stars (morning; evening by mirror) ---------------------------------------

D1 = (21.0, 21.1, 19.9, 20.0)  # red, body 1.0, midpoint 20.5
D2 = (19.8, 19.9, 19.6, 19.7)  # a 1-tick star opening below 20.0
D3 = (19.8, 20.8, 19.7, 20.7)  # green, body 0.9, closes past 20.5


@BOTH
def test_star_fires(bear):
    assert fire(STAR[bear], [D1, D2, D3], bear=bear) == 1.0


@BOTH
def test_star_needs_the_right_colour_first_day(bear):
    # A green d1, a star opening below its close, a long d3 past its midpoint.
    days = [
        (20.0, 21.1, 19.9, 21.0),
        (20.8, 20.9, 20.6, 20.7),
        (20.9, 21.7, 20.8, 21.6),
    ]
    assert fire(STAR[bear], days, bear=bear) == 0.0


@BOTH
def test_star_needs_a_long_first_day(bear):
    d1 = (20.4, 20.5, 19.9, 20.0)  # body 0.4 < the 0.5 baseline
    days = [d1, (19.95, 20.0, 19.8, 19.9), (19.9, 20.6, 19.8, 20.5)]
    assert fire(STAR[bear], days, bear=bear) == 0.0


@BOTH
def test_star_needs_a_small_middle_body(bear):
    d2 = (19.8, 19.9, 19.3, 19.4)  # body 0.4 > 0.3 x 1.0
    assert fire(STAR[bear], [D1, d2, D3], bear=bear) == 0.0


@BOTH
def test_the_star_opens_beyond_the_first_close_p4(bear):
    """P4: not a true gap, but the star must still OPEN beyond d1's close. At
    the close is not beyond it."""
    d2 = (20.0, 20.1, 19.8, 19.9)
    assert fire(STAR[bear], [D1, d2, D3], bear=bear) == 0.0


@BOTH
def test_the_middle_star_is_not_floored(bear):
    # A doji star (body 0) is the textbook star: its small body is the point.
    d2 = (19.8, 19.9, 19.6, 19.8)
    assert fire(STAR[bear], [D1, d2, D3], bear=bear) == 1.0


@BOTH
def test_star_needs_the_right_colour_third_day(bear):
    d3 = (21.5, 21.6, 20.5, 20.6)  # red, long, closes past the midpoint
    assert fire(STAR[bear], [D1, D2, d3], bear=bear) == 0.0


@BOTH
def test_star_needs_a_long_third_day(bear):
    d3 = (20.2, 20.7, 20.1, 20.6)  # green, past the midpoint, body 0.4
    assert fire(STAR[bear], [D1, D2, d3], bear=bear) == 0.0


@BOTH
def test_star_needs_the_third_close_past_the_midpoint(bear):
    d3 = (19.8, 20.5, 19.7, 20.4)  # green, long, closes at 20.4 < 20.5
    assert fire(STAR[bear], [D1, D2, d3], bear=bear) == 0.0


@BOTH
def test_star_needs_the_first_body_above_the_tick_floor(bear):
    # A tiny baseline makes a 0.2 body LONG; only the floor stops it.
    days = [
        (20.2, 20.25, 19.95, 20.0),
        (19.95, 20.0, 19.9, 19.97),
        (19.9, 20.35, 19.85, 20.3),
    ]
    assert fire(STAR[bear], days, base=TINY, bear=bear) == 0.0


@BOTH
def test_star_needs_the_third_body_above_the_tick_floor(bear):
    days = [
        (20.5, 20.55, 19.95, 20.0),
        (19.95, 20.0, 19.85, 19.9),
        (20.1, 20.35, 20.05, 20.3),
    ]
    assert fire(STAR[bear], days, base=TINY, bear=bear) == 0.0


@BOTH
def test_long_is_judged_against_the_sessions_before_the_pattern(bear):
    """At 1.1x a 0.5 baseline a 0.5515 first body is long; folding it into its
    own baseline would demand 0.5528."""
    days = [
        (20.5515, 20.6, 19.95, 20.0),
        (19.95, 20.0, 19.85, 19.9),
        (19.9, 20.7, 19.85, 20.6),
    ]
    assert fire(STAR[bear], days, bear=bear, long_body_vs_avg_min=1.1) == 1.0


# --- soldiers (white; crows by mirror) ----------------------------------------

S1 = (20.0, 20.5, 19.95, 20.45)
S2 = (20.3, 20.85, 20.25, 20.8)
S3 = (20.7, 21.25, 20.65, 21.2)


@BOTH
def test_soldiers_fire(bear):
    assert fire(SOLDIERS[bear], [S1, S2, S3], bear=bear) == 1.0


@BOTH
def test_second_soldier_must_not_open_below_the_first_body(bear):
    assert fire(SOLDIERS[bear], [S1, (19.9, 20.85, 19.85, 20.8), S3], bear=bear) == 0.0


@BOTH
def test_second_soldier_must_not_open_above_the_first_body(bear):
    assert fire(SOLDIERS[bear], [S1, (20.5, 20.85, 20.45, 20.8), S3], bear=bear) == 0.0


@BOTH
def test_third_soldier_must_not_open_below_the_second_body(bear):
    assert fire(SOLDIERS[bear], [S1, S2, (20.2, 21.25, 20.15, 21.2)], bear=bear) == 0.0


@BOTH
def test_third_soldier_must_not_open_above_the_second_body(bear):
    assert fire(SOLDIERS[bear], [S1, S2, (20.85, 21.25, 20.8, 21.2)], bear=bear) == 0.0


@BOTH
def test_second_soldier_must_close_beyond_the_first(bear):
    s2 = (20.1, 20.45, 20.05, 20.4)  # closes below 20.45
    s3 = (20.3, 20.85, 20.25, 20.8)
    assert fire(SOLDIERS[bear], [S1, s2, s3], bear=bear) == 0.0


@BOTH
def test_third_soldier_must_close_beyond_the_second(bear):
    assert fire(SOLDIERS[bear], [S1, S2, (20.4, 20.75, 20.35, 20.7)], bear=bear) == 0.0


@BOTH
@pytest.mark.parametrize("day", [0, 1, 2])
def test_each_soldier_must_close_near_its_extreme(bear, day):
    days = [S1, S2, S3]
    o, h, lo, c = days[day]
    days[day] = (o, h + 0.6, lo, c)  # a long upper wick
    assert fire(SOLDIERS[bear], days, bear=bear) == 0.0


@BOTH
@pytest.mark.parametrize("day", [0, 1, 2])
def test_each_soldier_needs_a_body_above_the_tick_floor(bear, day):
    tiny = [
        [
            (20.0, 20.25, 19.95, 20.2),
            (20.1, 20.65, 20.05, 20.6),
            (20.5, 21.05, 20.45, 21.0),
        ],
        # body 0.2 (2 ticks), still opening/closing correctly:
        [S1, (20.3, 20.55, 20.25, 20.5), (20.4, 21.05, 20.35, 21.0)],
        # body 0.25 (2.5 ticks):
        [S1, S2, (20.7, 21.0, 20.65, 20.95)],
    ][day]
    assert fire(SOLDIERS[bear], tiny, bear=bear) == 0.0


# --- three inside (up; down by mirror) ----------------------------------------

H1 = (21.0, 21.1, 19.9, 20.0)  # long red
H2 = (20.3, 20.6, 20.2, 20.5)  # inside it: a bullish harami on d1-d2
H3 = (20.6, 21.3, 20.5, 21.2)  # closes above d1's open (21.0)


@BOTH
def test_three_inside_fires(bear):
    assert fire(INSIDE[bear], [H1, H2, H3], bear=bear) == 1.0


@BOTH
def test_three_inside_needs_a_harami_on_the_first_two_days(bear):
    h2 = (20.9, 21.2, 20.8, 21.1)  # not inside d1's body
    assert fire(INSIDE[bear], [H1, h2, H3], bear=bear) == 0.0


@BOTH
def test_three_inside_needs_the_confirming_close(bear):
    assert fire(INSIDE[bear], [H1, H2, (20.6, 21.0, 20.5, 20.9)], bear=bear) == 0.0


@BOTH
def test_three_inside_uses_the_harami_floor_on_day_one(bear):
    days = [
        (20.2, 20.25, 19.95, 20.0),
        (20.05, 20.15, 20.0, 20.1),
        (20.1, 20.3, 20.05, 20.25),
    ]
    assert fire(INSIDE[bear], days, base=TINY, bear=bear) == 0.0


# --- the window rules, for all six ----------------------------------------------

CASES = {
    "morning_star": ([D1, D2, D3], False),
    "evening_star": ([D1, D2, D3], True),
    "three_white_soldiers": ([S1, S2, S3], False),
    "three_black_crows": ([S1, S2, S3], True),
    "three_inside_up": ([H1, H2, H3], False),
    "three_inside_down": ([H1, H2, H3], True),
}


def frame_for(name, **kw):
    days, bear = CASES[name]
    candles = [BASE] * 20 + days
    if bear:
        candles = [mirror(c) for c in candles]
    return bars(candles, **kw)


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("gap_at", [21, 22], ids=["before-day2", "before-day3"])
def test_a_gap_anywhere_in_the_three_days_blanks_it(name, gap_at):
    assert run(name, frame_for(name)).iloc[-1] == 1.0
    assert np.isnan(run(name, frame_for(name, gaps=[gap_at])).iloc[-1])


@pytest.mark.parametrize(
    "name", ["morning_star", "evening_star", "three_inside_up", "three_inside_down"]
)
def test_a_gap_in_the_long_body_baseline_blanks_it(name):
    assert np.isnan(run(name, frame_for(name, gaps=[10])).iloc[-1])


@pytest.mark.parametrize("name", CASES)
def test_an_excluded_first_day_blanks_it(name):
    assert np.isnan(run(name, frame_for(name, excluded=[20])).iloc[-1])


@pytest.mark.parametrize("name", CASES)
def test_a_pattern_cannot_see_the_future(name):
    days, bear = CASES[name]
    candles = [BASE] * 20 + days + [BASE] * 3
    if bear:
        candles = [mirror(c) for c in candles]
    full, cut = run(name, bars(candles)), run(name, bars(candles[:-3]))
    assert full.iloc[22] == cut.iloc[-1] == 1.0
