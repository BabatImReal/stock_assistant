"""A symbol is rescaled only if CafeF's history is the stored one times ONE constant.

Pure tests: no database.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import rescale_build as rb  # noqa: E402

D = dt.date


def days(n, start=None):
    start = start or D(2026, 9, 1)
    return [start + dt.timedelta(days=i) for i in range(n)]


def s(values, idx):
    return pd.Series(values, index=idx, dtype=float)


def test_a_constant_ratio_before_the_action_is_rescalable():
    idx = days(5)
    stored = s([1.0] * 5, idx)
    current = s([0.8] * 5, idx)  # the whole past moved by 0.8
    p = rb.plan_symbol(stored, current, D(2026, 9, 10))
    assert p["ok"] and abs(p["ratio"] - 0.8) < 1e-12


def test_rounding_wobble_is_still_constant():
    idx = days(3)
    p = rb.plan_symbol(
        s([1.0, 1.0, 1.0], idx),
        s([0.839404, 0.839397, 0.839403], idx),
        D(2026, 9, 10),
    )
    assert p["ok"]


def test_a_second_action_or_a_repair_breaks_constancy_and_is_refused():
    idx = days(4)
    stored = s([1.0, 1.0, 1.0, 1.0], idx)
    current = s([0.8, 0.8, 0.9, 0.9], idx)  # two different ratios
    p = rb.plan_symbol(stored, current, D(2026, 9, 10))
    assert not p["ok"] and "not constant" in p["reason"]


def test_a_stored_day_missing_from_cafef_is_refused():
    idx = days(3)
    p = rb.plan_symbol(s([1.0] * 3, idx), s([0.8] * 2, idx[:2]), D(2026, 9, 10))
    assert not p["ok"] and "absent" in p["reason"]


def test_only_days_before_the_action_are_judged():
    idx = days(4)  # the last day is ON the action and has a new basis
    stored = s([1.0, 1.0, 1.0, 1.0], idx)
    current = s([0.8, 0.8, 0.8, 1.0], idx)
    p = rb.plan_symbol(stored, current, idx[3])
    assert p["ok"] and abs(p["ratio"] - 0.8) < 1e-12


def test_no_history_is_refused():
    p = rb.plan_symbol(s([], []), s([], []), D(2026, 9, 10))
    assert not p["ok"]


def test_a_date_shifted_day_may_be_absent_from_cafef_but_nothing_else():
    idx = days(4)
    stored = s([1.0] * 4, idx)
    current = s([0.9] * 3, idx[:3])  # CafeF has no bar on the 4th day (the shifted one)
    ev = D(2026, 9, 10)
    assert rb.plan_symbol(stored, current, ev, shifted=frozenset({idx[3]}))["ok"]
    refused = rb.plan_symbol(stored, current, ev, shifted=frozenset({D(2020, 1, 1)}))
    assert not refused["ok"] and "absent" in refused["reason"]


def test_the_days_that_are_present_must_still_fit_one_ratio_around_a_shifted_gap():
    idx = days(4)
    stored = s([1.0] * 4, idx)
    current = s([0.9, 0.9, 0.8], idx[:3])  # a shifted day is absent AND the rest drifts
    p = rb.plan_symbol(stored, current, D(2026, 9, 10), shifted=frozenset({idx[3]}))
    assert not p["ok"]
