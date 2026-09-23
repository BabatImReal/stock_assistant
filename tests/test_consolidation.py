"""Tests for patterns tranche 4 (patterns/consolidation.py): short
consolidations. One test per rule; each fails if its rule is removed.

Default exchange HNX on 2020 dates: a 0.1 tick, so the 3-tick floors are 0.3.
"""

import numpy as np
import pytest

from .test_candles import bars, run

WIDE = (20.0, 20.5, 19.5, 20.0)  # range 1.0
TIGHT = (20.0, 20.2, 19.8, 20.0)  # range 0.4


def last(name, candles, **kw):
    return run(name, bars(candles), **kw).iloc[-1]


# --- tight range ------------------------------------------------------------


def test_tight_range_fires():
    assert last("tight_range", [WIDE] * 20 + [TIGHT] * 5) == 1.0


def test_tight_range_needs_the_recent_range_small_enough():
    loose = (20.0, 20.35, 19.65, 20.0)  # range 0.7 = 70% of normal
    assert last("tight_range", [WIDE] * 20 + [loose] * 5) == 0.0


def test_the_recent_window_is_kept_out_of_its_own_baseline():
    """0.55 is tight against the 1.0 baseline before it. Folding the five
    recent days into the baseline (0.8875) would demand below 0.5325."""
    mid = (20.0, 20.275, 19.725, 20.0)
    assert last("tight_range", [WIDE] * 20 + [mid] * 5) == 1.0


def test_tight_range_needs_a_baseline_above_the_tick_floor():
    # A normal range of 2 ticks: "tight" against it is tick noise.
    two_ticks, half_tick = (20.0, 20.1, 19.9, 20.0), (20.0, 20.03, 19.98, 20.0)
    assert last("tight_range", [two_ticks] * 20 + [half_tick] * 5) == 0.0


# --- inside-day run ---------------------------------------------------------

MOTHER = (20.0, 21.0, 19.0, 20.0)  # range 2.0
IN1 = (20.0, 20.5, 19.5, 20.0)  # inside it, range 1.0
IN2 = (20.0, 20.3, 19.7, 20.0)  # inside IN1, range 0.6


def test_inside_day_run_fires():
    assert last("inside_day_run", [MOTHER, IN1, IN2]) == 1.0


def test_the_latest_day_must_not_break_above_the_day_before():
    assert last("inside_day_run", [MOTHER, IN1, (20.0, 20.6, 19.8, 20.0)]) == 0.0


def test_the_earlier_day_must_not_break_below_the_mother_bar():
    in1 = (20.0, 20.5, 18.9, 20.0)  # range 1.6 < 2.0 but below the low
    assert last("inside_day_run", [MOTHER, in1, IN2]) == 0.0


def test_an_identical_repeat_is_not_inside():
    # Same high and low: contained, but not a smaller range.
    assert last("inside_day_run", [MOTHER, IN1, IN1]) == 0.0


def test_the_mother_bar_must_be_above_the_tick_floor():
    tiny = [
        (20.0, 20.1, 19.9, 20.0),
        (20.0, 20.08, 19.93, 20.0),
        (20.0, 20.05, 19.95, 20.0),
    ]
    assert last("inside_day_run", tiny) == 0.0


def test_only_the_mother_bar_is_floored():
    # The last inside day is 1.5 ticks: small is the point of an inside day.
    days = [
        (20.0, 20.5, 19.5, 20.0),
        (20.0, 20.3, 19.8, 20.0),
        (20.0, 20.1, 19.95, 20.0),
    ]
    assert last("inside_day_run", days) == 1.0


def test_min_days_counts_every_day_of_the_run():
    before = (20.0, 20.8, 19.5, 20.0)  # the mother bar is NOT inside this one
    candles = [before, MOTHER, IN1, IN2]
    assert last("inside_day_run", candles, min_days=2) == 1.0
    assert last("inside_day_run", candles, min_days=3) == 0.0


# --- higher lows ------------------------------------------------------------

HL = [
    (19.5, 20.0, 19.0, 19.8),
    (19.8, 20.1, 19.2, 20.0),
    (20.0, 20.0, 19.4, 19.9),
    (19.9, 20.1, 19.6, 20.0),
]


def test_higher_lows_fires():
    assert last("higher_lows", HL) == 1.0


def test_every_low_must_be_above_the_one_before():
    days = list(HL)
    days[2] = (20.0, 20.0, 19.2, 19.9)  # equal to the day before
    assert last("higher_lows", days) == 0.0


def test_the_highs_must_stay_flat():
    days = list(HL)
    days[2] = (20.0, 20.6, 19.4, 19.9)  # highs spread 0.6 > 2% of ~20
    assert last("higher_lows", days) == 0.0


def test_lookback_days_counts_every_low():
    before = (19.5, 20.0, 19.3, 19.8)  # its low is ABOVE the next day's
    assert last("higher_lows", [before] + HL, lookback_days=4) == 1.0
    assert last("higher_lows", [before] + HL, lookback_days=5) == 0.0


# --- breakout ---------------------------------------------------------------

UP = (20.4, 20.9, 20.3, 20.8)  # closes above 20.5


def test_breakout_fires():
    assert last("breakout", [WIDE] * 20 + [UP]) == 1.0


def test_a_close_at_the_old_high_is_not_a_breakout():
    assert last("breakout", [WIDE] * 20 + [(20.0, 20.6, 19.9, 20.5)]) == 0.0


def test_a_higher_high_inside_the_window_blocks_it():
    # At the OLDEST session in the window (20 back): any shorter window misses it.
    days = [WIDE] * 20
    days[0] = (20.0, 21.0, 19.5, 20.0)
    assert last("breakout", days + [UP]) == 0.0


def test_a_high_older_than_the_window_does_not_count():
    old = (20.0, 21.0, 19.5, 20.0)  # 21 sessions back
    assert last("breakout", [old] + [WIDE] * 20 + [UP]) == 1.0


def test_breakout_is_price_only():
    # Volume plays no part: the same prices on almost no volume still fire.
    df = bars([WIDE] * 20 + [UP])
    df["matched_volume"] = 1.0
    assert run("breakout", df).iloc[-1] == 1.0


# --- the window rules, for all four ------------------------------------------

CASES = {
    "tight_range": [WIDE] * 20 + [TIGHT] * 5,
    "inside_day_run": [MOTHER, IN1, IN2],
    "higher_lows": HL,
    "breakout": [WIDE] * 20 + [UP],
}


@pytest.mark.parametrize("name", CASES)
def test_a_gap_before_the_last_day_blanks_it(name):
    candles = CASES[name]
    assert run(name, bars(candles)).iloc[-1] == 1.0
    assert np.isnan(run(name, bars(candles, gaps=[len(candles) - 1])).iloc[-1])


@pytest.mark.parametrize("name", CASES)
def test_a_gap_at_the_far_end_of_the_window_blanks_it(name):
    """Between the two OLDEST sessions read: only a lookback that covers every
    session read catches it."""
    assert np.isnan(run(name, bars(CASES[name], gaps=[1])).iloc[-1])


@pytest.mark.parametrize("name", CASES)
def test_an_excluded_first_day_blanks_it(name):
    assert np.isnan(run(name, bars(CASES[name], excluded=[0])).iloc[-1])


@pytest.mark.parametrize("name", CASES)
def test_a_consolidation_cannot_see_the_future(name):
    candles = CASES[name] + [WIDE] * 3
    full, cut = run(name, bars(candles)), run(name, bars(candles[:-3]))
    assert full.iloc[len(candles) - 4] == cut.iloc[-1] == 1.0
