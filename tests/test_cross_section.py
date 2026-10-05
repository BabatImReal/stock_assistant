"""The cross-sectional ranking's arithmetic. Pure functions, no database."""

import numpy as np
import pandas as pd
import pytest

from vnstock_research import cross_section as cs


def bars(n=300, price=None, vol=None, gap_at=None, excl_at=None, sym="AAA"):
    price = np.linspace(10, 20, n) if price is None else np.asarray(price, float)
    vol = np.full(n, 1000.0) if vol is None else np.asarray(vol, float)
    gap = np.zeros(n)
    if gap_at is not None:
        gap[gap_at] = 3
    exc = np.zeros(n, bool)
    if excl_at is not None:
        exc[excl_at] = True
    return pd.DataFrame(
        {
            "symbol": sym,
            "trade_date": pd.bdate_range("2020-01-01", periods=n),
            "close": price,
            "high": price * 1.01,
            "matched_volume": vol,
            "gap_before": gap,
            "excluded": exc,
        }
    )


def test_a_stock_at_its_own_high_scores_near_one_and_one_far_below_scores_lower():
    up = cs.features(bars(price=np.linspace(10, 20, 300)))
    down = cs.features(bars(price=np.linspace(20, 10, 300)))
    assert up["high52"].iloc[-1] == pytest.approx(1 / 1.01)  # close / (1.01 * close)
    assert down["high52"].iloc[-1] < 0.6
    assert up["high52"].iloc[:249].isna().all()  # less than 250 sessions: no value


def test_a_recent_volume_surge_raises_abnormal_volume_above_one():
    vol = np.full(300, 1000.0)
    vol[-20:] = 3000.0
    f = cs.features(bars(vol=vol))
    assert f["abn_vol"].iloc[-1] > 1.1
    assert f["abn_vol"].iloc[-21] == pytest.approx(1.0)


def test_a_gap_inside_the_250_session_window_blanks_the_value_and_leaving_it_restores():
    # window for row i is rows i-249..i. A skipped session at row 20 is inside it for
    # i <= 269 and outside it from i = 270.
    f = cs.features(bars(n=300, gap_at=20))
    assert f["high52"].iloc[249:270].isna().all()
    assert f["high52"].iloc[270:].notna().all()
    assert (f["high52"].dropna() > 0).all()  # blanked, never a zero


def test_an_excluded_row_inside_the_window_blanks_the_value_the_same_way():
    f = cs.features(bars(n=300, excl_at=20))
    assert f["high52"].iloc[249:270].isna().all()
    assert f["high52"].iloc[270:].notna().all()


def test_a_missing_volume_day_blanks_abnormal_volume():
    vol = np.full(300, 1000.0)
    vol[150] = np.nan
    f = cs.features(bars(vol=vol))
    assert np.isnan(f["abn_vol"].iloc[-1])


def test_the_score_is_the_equal_weight_mean_of_the_two_percentile_ranks():
    d = pd.DataFrame({"high52": [0.5, 0.9, 0.7], "abn_vol": [3.0, 1.0, 2.0]})
    s = cs.score(d)
    assert list(np.round(s, 4)) == [
        round((1 / 3 + 1) / 2, 4),
        round((1 + 1 / 3) / 2, 4),
        0.6667,
    ]


def panel(n=60, days=3):
    rows = []
    for d in pd.bdate_range("2021-01-04", periods=days):
        for i in range(n):
            rows.append(
                {
                    "symbol": f"S{i:03d}",
                    "trade_date": d,
                    "high52": i / n,
                    "abn_vol": i / n,
                }
            )
    return pd.DataFrame(rows)


def test_the_top_decile_is_the_best_ranked_tenth_and_ties_are_broken_by_symbol():
    sel = cs.daily_selection(panel(60, 1), frac=0.10)
    top = sel[sel["in_top"]]
    assert len(top) == 6 and set(top["symbol"]) == {f"S{i:03d}" for i in range(54, 60)}
    assert sel.loc[sel["rank"] == 1, "symbol"].iloc[0] == "S059"


def test_a_day_with_too_few_ranked_stocks_produces_no_ranking():
    assert cs.daily_selection(panel(10, 2), min_ranked=50).empty


def test_excess_is_the_top_mean_minus_the_whole_universe_mean_that_day():
    sel = cs.daily_selection(panel(60, 1))
    sel["net_5"] = np.where(sel["in_top"], 0.05, 0.0)  # top earns +5%, the rest 0
    ex = cs.excess_series(sel)
    base = 6 * 0.05 / 60
    assert ex["excess_top"].iloc[0] == pytest.approx(0.05 - base)
    assert ex["n_universe"].iloc[0] == 60


def test_unresolved_outcomes_do_not_enter_the_means_but_did_not_change_the_ranking():
    sel = cs.daily_selection(panel(60, 1))
    sel["net_5"] = 0.01
    sel.loc[sel["rank"] > 50, "net_5"] = np.nan  # the worst-ranked 10 unresolved
    ex = cs.excess_series(sel)
    assert ex["n_universe"].iloc[0] == 50
    assert sel["n_ranked"].iloc[0] == 60  # ranked on all 60


def test_newey_west_equals_the_plain_se_with_zero_lags_and_is_larger_when_correlated():
    rng = np.random.default_rng(0)
    iid = pd.Series(rng.normal(0, 1, 400))
    plain = cs.newey_west_mean(iid, lags=0)
    assert plain["se"] == pytest.approx(iid.std(ddof=0) / np.sqrt(400), rel=1e-9)
    ar = pd.Series(
        np.cumsum(rng.normal(0, 1, 400)) * 0.0
        + np.convolve(rng.normal(0, 1, 404), np.ones(5) / 5, "valid")
    )
    assert cs.newey_west_mean(ar, lags=5)["se"] > cs.newey_west_mean(ar, lags=0)["se"]


def test_too_few_observations_give_nan_not_a_result():
    assert np.isnan(cs.newey_west_mean(pd.Series([0.1]), lags=5)["mean"])
