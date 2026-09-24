"""Tests for the ONE ceiling/floor definition (data/checks.py `limit_prices`,
B1). One test per rule; each fails if its rule is removed. The agreement with
the gate's SQL twin is tested on real data in test_data_integrity.py.
"""

import numpy as np
import pytest

from vnstock_research.data import checks


def limits(ref, exchange="HOSE", day="2020-06-01", first_day=False):
    out = checks.limit_prices([ref], [exchange], [day], [first_day])
    return out.iloc[0]


def test_the_limit_is_the_one_in_force_on_the_date():
    # HOSE widened from 5% to 7% on 2013-01-15.
    assert limits(20.0, day="2012-06-01")["ceiling"] == pytest.approx(21.0)
    assert limits(20.0, day="2014-06-02")["ceiling"] == pytest.approx(21.4)


def test_the_ceiling_rounds_down_and_the_floor_up_to_the_tick():
    # 23.45 x 1.07 = 25.0915 and x 0.93 = 21.8085, on a 0.05 tick.
    lim = limits(23.45)
    assert lim["ceiling"] == pytest.approx(25.05)
    assert lim["floor"] == pytest.approx(21.85)


def test_the_tick_is_the_one_of_the_limit_price_itself():
    # 9.5 x 1.07 = 10.165 sits in the 10-50 band (tick 0.05), 9.5 x 0.93 =
    # 8.835 in the under-10 band (tick 0.01).
    lim = limits(9.5)
    assert (lim["ceiling"], lim["ceiling_tick"]) == pytest.approx((10.15, 0.05))
    assert (lim["floor"], lim["floor_tick"]) == pytest.approx((8.84, 0.01))


def test_float_noise_never_costs_a_tick():
    # 2.0 x 1.15 = 2.3 exactly, but 2.3 / 0.1 is 22.999999999999996 in binary:
    # rounding that down would put UPCoM's ceiling at 2.2.
    assert limits(2.0, exchange="UPCOM", day="2014-06-02")["ceiling"] == pytest.approx(
        2.3
    )


def test_the_first_day_band_applies_when_asked():
    assert limits(20.0, first_day=True)["rate"] == pytest.approx(0.20)
    assert limits(20.0, first_day=True)["ceiling"] == pytest.approx(24.0)


def test_a_limit_smaller_than_a_tick_is_one_tick_from_the_reference():
    # 500 VND on HNX: 10% is 50 VND, half a tick; rounding lands on the
    # reference itself, so the band is one tick either side.
    lim = limits(0.5, exchange="HNX", day="2014-06-02")
    assert (lim["ceiling"], lim["floor"]) == pytest.approx((0.6, 0.4))


def test_at_the_ceiling_is_within_half_a_tick_not_a_flat_epsilon():
    """The B1 case: 123.4 x 1.07 = 132.038 rounds down to 132.0. A flat
    0.0015 tolerance around 132.038 never sees an open of 132.0."""
    lim = checks.limit_prices(
        [123.4] * 2, ["HOSE"] * 2, ["2020-06-01"] * 2, [False] * 2
    )
    assert checks.at_ceiling([132.0, 131.9], lim).tolist() == [True, False]
    # 123.4 x 0.93 = 114.762 rounds up to 114.8.
    assert checks.at_floor([114.8, 114.9], lim).tolist() == [True, False]
    # Off the tick grid (backfilled prices are): the boundary is HALF a tick.
    assert checks.at_ceiling([131.96, 131.94], lim).tolist() == [True, False]
    assert checks.at_floor([114.84, 114.86], lim).tolist() == [True, False]


def test_an_exchange_without_a_tick_table_has_no_limits():
    assert np.isnan(limits(20.0, exchange="OTC")["ceiling"])
