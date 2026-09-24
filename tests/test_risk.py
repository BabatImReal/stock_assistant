"""Tests for backtest/risk.py: the numbers beside the hit rate (doc §8.3).
Every expected value is worked out by hand in the comment beside it; each test
fails if its rule is removed."""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.backtest import risk


def test_drawdown_is_the_deepest_fall_below_the_previous_peak():
    # Running total 0, 2, 1, -2, 3, 1: the peak 2 falls to -2 -> -4.
    assert risk.max_drawdown([2, -1, -3, 5, -2]) == -4


def test_the_start_counts_as_a_peak():
    # Losing from the first trade is a drawdown too: 0 -> -1 -> -3.
    assert risk.max_drawdown([-1, -2, 4]) == -3


def test_no_drawdown_when_the_total_only_rises():
    assert risk.max_drawdown([1, 0.5, 2]) == 0


def test_a_losing_streak_counts_a_trade_that_only_paid_its_costs():
    # 0 is not a hit (hit = net > 0), so -1, 0, -2 is a run of three.
    assert risk.worst_streak([1, -1, 0, -2, 3, -1]) == 3


def test_the_streak_is_the_longest_run_not_the_total_count():
    assert risk.worst_streak([-1, 1, -1, -1, 1, -1]) == 2


def test_per_trade_average_win_loss_and_payoff():
    s = risk.per_trade([0.02, -0.01, -0.03, 0.04, 0.0])
    assert s["trades"] == 5
    assert s["avg_win"] == pytest.approx(0.03)  # (0.02 + 0.04) / 2
    assert s["avg_loss"] == pytest.approx(-0.04 / 3)  # (-0.01 - 0.03 + 0) / 3
    assert s["payoff"] == pytest.approx(0.03 / (0.04 / 3))
    assert s["best"] == 0.04 and s["worst"] == -0.03


def test_the_basket_is_the_mean_of_each_signal_day_in_date_order():
    day = risk.basket(["2024-01-03", "2024-01-02", "2024-01-03"], [0.04, -0.01, 0.00])
    assert list(day.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert list(day) == pytest.approx([-0.01, 0.02])


def test_one_pick_takes_one_trade_of_that_day_each_day():
    dates = ["2024-01-02", "2024-01-02", "2024-01-03"]
    picks = risk.one_pick_paths(dates, [1.0, 3.0, 7.0], paths=400, seed=1)
    assert picks.shape == (400, 2)
    assert set(picks[:, 0]) == {1.0, 3.0}  # both of day one's trades get drawn
    assert set(picks[:, 1]) == {7.0}  # never another day's trade
    assert 0.35 < (picks[:, 0] == 1.0).mean() < 0.65  # uniformly


def test_one_pick_follows_the_dates_not_the_input_order():
    # One day's trades need not be next to each other in the input.
    dates = ["2024-01-05", "2024-01-02", "2024-01-05"]
    picks = risk.one_pick_paths(dates, [5.0, 2.0, 6.0], paths=200, seed=1)
    assert set(picks[:, 0]) == {2.0} and set(picks[:, 1]) == {5.0, 6.0}


def test_losing_windows_counts_every_stretch_whose_total_is_not_positive():
    # Stretches of 2: (1, -2) = -1, (-2, 1) = -1, (1, 1) = 2 -> 2 of 3.
    assert risk.losing_windows([1, -2, 1, 1], 2) == pytest.approx(2 / 3)
    # A stretch that ends exactly at zero made nothing: it counts.
    assert risk.losing_windows([1, -1, 1, 1], 2) == pytest.approx(2 / 3)
    assert np.isnan(risk.losing_windows([1, -2], 3))


def test_describe_puts_the_basket_and_the_picks_on_the_same_trades():
    dates = pd.bdate_range("2024-01-01", periods=100).repeat(2)
    net = np.tile([0.03, -0.02], 100)
    d = risk.describe(dates, net, paths=200, seed=3, window=60)
    assert d["trades"] == 200 and d["signal_days"] == 100
    # Every day's mean is +0.5%: the basket never falls.
    assert d["basket_total"] == pytest.approx(0.5)
    assert d["basket_drawdown"] == 0 and d["basket_streak"] == 0
    # One pick is either +3% or -2% a day: it does fall, and it is bumpier.
    assert d["pick_drawdown_bad"] <= d["pick_drawdown_median"] < 0
    assert d["pick_streak_bad"] >= d["pick_streak_median"] >= 1
    assert 0 <= d["pick_losing_windows"] < 1
