"""Tests for the tradeable forward-return definition (G3).

The settlement era logic is the part worth guarding: the 2016 change is a trap,
because moving to "T+2 settlement" did NOT make shares sellable on T+2 -- the
money landed at 16:30, after the close. A test that only checked "2016 means
T+2" would encode exactly the mistake the definition exists to avoid.
"""

import pytest

from vnstock_research.backtest import forward_returns as fr


@pytest.mark.parametrize(
    ("entry_date", "expected"),
    [
        ("2012-05-04", 3),  # first era: settles morning of T+3
        ("2015-12-30", 3),  # trades of late Dec 2015 still settled T+3
        ("2016-01-04", 3),  # T+2 settlement, but at 16:30 -- still sells T+3
        ("2020-06-01", 3),
        ("2022-08-24", 3),  # last day of the middle era
        ("2022-08-25", 2),  # settlement before 13:00 -- sellable T+2 afternoon
        ("2026-09-21", 2),
    ],
)
def test_earliest_sell_offset_by_era(entry_date, expected):
    assert fr.earliest_sell_offset(entry_date) == expected


def test_both_documented_horizons_are_valid_in_every_era():
    # doc §1: patterns form over 3-5 days and the question is the following few.
    # If an era made k=3 unsellable the whole horizon choice would need revisiting.
    for date in ("2012-05-04", "2018-06-01", "2024-06-03"):
        assert fr.valid_horizons(date, (3, 5)) == [3, 5]


def test_one_day_horizon_is_never_tradeable():
    # The doc's own warning: a 1-day edge cannot be traded under any VN
    # settlement regime, which is why the 3-5 day horizon was chosen.
    for date in ("2012-05-04", "2024-06-03"):
        assert fr.valid_horizons(date, (1,)) == []


def test_costs_are_charged_on_both_sides_and_the_tax_on_the_sale():
    costs = fr.load_costs()
    assert costs.round_trip == pytest.approx(2 * 0.0015 + 0.001)
    # A flat trade still loses the round trip: the sale tax is charged whether
    # or not the trade made money.
    assert fr.net_return(0.0, costs) < 0
    assert fr.net_return(0.0, costs) == pytest.approx(-costs.round_trip, abs=1e-5)


def test_net_return_is_below_gross_and_preserves_order():
    costs = fr.load_costs()
    assert fr.net_return(0.05, costs) < 0.05
    assert fr.net_return(0.05, costs) > fr.net_return(0.02, costs)


def test_ceiling_and_floor_detection():
    # 7% limit, previous close 100 -> ceiling 107, floor 93.
    assert fr.is_at_ceiling(107.0, 100.0, 0.07)
    assert not fr.is_at_ceiling(106.0, 100.0, 0.07)
    assert fr.is_at_floor(93.0, 100.0, 0.07)
    assert not fr.is_at_floor(94.0, 100.0, 0.07)


def test_limit_checks_are_safe_when_there_is_no_previous_close():
    # A first bar has no reference price; it must not divide by zero or claim
    # the price is at a limit it cannot compute.
    assert not fr.is_at_ceiling(50.0, 0.0, 0.07)
    assert not fr.is_at_floor(50.0, 0.0, 0.07)


def test_every_settlement_era_is_marked_verified():
    # These came from Ben with sources. If an unverified era ever appears, the
    # backtest is resting on a guess and should say so.
    assert all(era["verified"] for era in fr.settlement_eras())
