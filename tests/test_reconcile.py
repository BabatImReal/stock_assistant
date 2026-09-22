"""Tests for the two-source reconciliation.

These matter more than they look. Reconciliation is the thing that decides
whether a dataset is allowed to be used at all (CLAUDE.md: "mismatches beyond
tolerance are flagged and excluded until explained"), so a bug here fails in the
worst direction — quietly approving bad data.
"""

from datetime import date

import pandas as pd
import pytest

from vnstock_research.data import reconcile


def frame(rows):
    return reconcile.normalise(
        pd.DataFrame(rows, columns=["symbol", "date", "close", "volume"])
    )


def test_identical_sources_match_completely():
    rows = [
        ("VNM", date(2012, 1, 3), 100.0, 1000),
        ("VNM", date(2012, 1, 4), 101.0, 900),
    ]
    (res,) = reconcile.reconcile(frame(rows), frame(rows), volume_columns=())
    assert res.compared == 2
    assert res.match_rate == 1.0
    assert res.mismatches.empty


def test_difference_inside_tolerance_passes_and_outside_fails():
    left = frame([("VNM", date(2012, 1, 3), 100.0, 1000)])
    # 0.4% apart: rounding between two independently adjusted series.
    near = frame([("VNM", date(2012, 1, 3), 100.4, 1000)])
    # 2% apart: far too big to be rounding; this is a missed corporate action.
    far = frame([("VNM", date(2012, 1, 3), 102.0, 1000)])

    (ok,) = reconcile.reconcile(left, near, volume_columns=())
    (bad,) = reconcile.reconcile(left, far, volume_columns=())
    assert ok.match_rate == 1.0
    assert bad.match_rate == 0.0
    assert len(bad.mismatches) == 1


def test_missing_days_are_reported_per_side_not_silently_dropped():
    # The dangerous failure is a truncated download looking like a clean match,
    # so days present on only one side must never be counted as agreement.
    left = frame(
        [("VNM", date(2012, 1, 3), 100.0, 10), ("VNM", date(2012, 1, 4), 101.0, 10)]
    )
    right = frame([("VNM", date(2012, 1, 3), 100.0, 10)])
    (res,) = reconcile.reconcile(left, right, volume_columns=())
    assert res.compared == 1
    assert len(res.left_only) == 1
    assert res.left_only.iloc[0]["date"] == date(2012, 1, 4)


def test_zero_on_one_side_is_a_mismatch_not_a_crash():
    left = frame([("VNM", date(2012, 1, 3), 100.0, 1000)])
    right = frame([("VNM", date(2012, 1, 3), 0.0, 1000)])
    (res,) = reconcile.reconcile(left, right, volume_columns=())
    assert res.match_rate == 0.0  # a zero price is missing data, not a small number


def test_nothing_compared_is_not_a_perfect_score():
    left = frame([("VNM", date(2012, 1, 3), 100.0, 10)])
    right = frame([("HPG", date(2012, 1, 3), 100.0, 10)])
    (res,) = reconcile.reconcile(left, right, volume_columns=())
    assert res.compared == 0
    assert res.match_rate == 0.0


def test_volume_uses_its_own_looser_tolerance():
    # Sources disagree on whether volume includes block trades (doc §4.3), so
    # price and volume cannot share one threshold.
    left = frame([("VNM", date(2012, 1, 3), 100.0, 1000)])
    right = frame([("VNM", date(2012, 1, 3), 100.0, 1005)])
    results = reconcile.reconcile(left, right)
    by_col = {r.column: r for r in results}
    assert by_col["volume"].match_rate == 1.0  # 0.5% is inside the 1% volume band
    assert by_col["close"].match_rate == 1.0


def test_median_ratio_exposes_a_systematic_difference():
    # A constant ratio is the signature of a definition difference (one source
    # including negotiated volume), not of random corruption.
    left = frame([("VNM", date(2012, 1, d), 100.0, 2000) for d in range(3, 8)])
    right = frame([("VNM", date(2012, 1, d), 100.0, 1000) for d in range(3, 8)])
    results = {r.column: r for r in reconcile.reconcile(left, right)}
    assert results["volume"].median_ratio == pytest.approx(2.0)


def test_missing_trading_days_only_looks_inside_the_listed_range():
    # Days before a stock listed are not gaps; counting them would bury the real
    # ones under thousands of meaningless rows.
    df = frame(
        [("VNM", date(2012, 1, 4), 100.0, 10), ("VNM", date(2012, 1, 6), 100.0, 10)]
    )
    calendar = {date(2012, 1, d) for d in (3, 4, 5, 6)}
    gaps = reconcile.missing_trading_days(df, calendar, symbol="VNM")
    assert gaps == [date(2012, 1, 5)]


def test_sample_by_year_touches_every_year():
    rows = [
        ("VNM", date(y, 1, d), 100.0, 10)
        for y in (2012, 2013, 2014)
        for d in range(3, 9)
    ]
    sample = reconcile.sample_by_year(frame(rows), per_year=2)
    assert sorted(pd.to_datetime(sample["date"]).dt.year.unique()) == [2012, 2013, 2014]
    assert len(sample) == 6
