"""Tests for the structural measures (src/vnstock_research/structural.py):
relative strength vs the index, resisting down days, the 200-session trend and
the stage. One test per rule; each fails if its rule is removed. Every measure
also has a look-ahead test: its value at T is unchanged when the rows after T
are deleted."""

import numpy as np
import pandas as pd
import pytest

from vnstock_research import structural
from vnstock_research.features import compute
from vnstock_research.features.base import REGISTRY, featureset
from vnstock_research.features.base import load_config as registered_config

from ._helpers import frame

CFG = structural.load_config()


def bars(close, index, gaps=None, excluded=None):
    df = frame(n=len(close), close=close, gaps=gaps, excluded=excluded)
    df["index_close"] = np.asarray(index, dtype=float)
    return df


def run(name, df, **params):
    cfg = {name: {**CFG[name], **params}}
    return compute(df, cfg)[0][name]


def growth(rate, n, start=100.0):
    return start * (1 + rate) ** np.arange(n)


# --- relative strength vs the index ----------------------------------------------


def test_rs_is_the_stock_return_minus_the_index_return():
    stock, index = growth(0.01, 25), growth(0.004, 25)
    got = run("rs_index_20d", bars(stock, index)).iloc[-1]
    assert got == pytest.approx((1.01**20 - 1) - (1.004**20 - 1))


def test_rs_blanks_a_window_across_a_gap_at_its_far_end():
    stock, index = growth(0.01, 25), growth(0.004, 25)
    # The window at row 24 reads rows 4..24: a gap before row 5 is inside it.
    assert np.isnan(run("rs_index_20d", bars(stock, index, gaps=[5])).iloc[-1])
    assert not np.isnan(run("rs_index_20d", bars(stock, index, gaps=[4])).iloc[-1])


def test_rs_is_unknown_when_the_index_is_missing_at_an_end():
    stock, index = growth(0.01, 25), growth(0.004, 25)
    index[4] = np.nan
    assert np.isnan(run("rs_index_20d", bars(stock, index)).iloc[-1])


# --- resisting down days ------------------------------------------------------


def down_day_case():
    """Index alternates -1% / +1%; the stock falls only 0.2% on down days and
    rises 3% on up days: it beats the index by 0.8 pts on each down day (and
    by 2 pts on each up day, which must not count)."""
    n = 22
    idx_ret = np.array([0.0] + [-0.01 if i % 2 else 0.01 for i in range(1, n)])
    stk_ret = np.where(idx_ret < 0, -0.002, np.where(idx_ret > 0, 0.03, 0.0))
    return 100 * np.cumprod(1 + stk_ret), 100 * np.cumprod(1 + idx_ret)


def test_down_day_rs_averages_the_index_down_days_only():
    stock, index = down_day_case()
    got = run("down_day_rs_20d", bars(stock, index)).iloc[-1]
    assert got == pytest.approx(0.008)


def test_down_day_rs_needs_enough_down_days():
    stock, index = down_day_case()
    assert np.isnan(
        run("down_day_rs_20d", bars(stock, index), min_down_days=11).iloc[-1]
    )
    assert not np.isnan(
        run("down_day_rs_20d", bars(stock, index), min_down_days=10).iloc[-1]
    )


def test_down_day_rs_is_unknown_when_an_index_day_is_missing():
    stock, index = down_day_case()
    index[15] = np.nan  # any day of the window could have been a down day
    assert np.isnan(run("down_day_rs_20d", bars(stock, index)).iloc[-1])


def test_down_day_rs_blanks_a_gap_at_the_far_end():
    stock, index = down_day_case()
    assert np.isnan(run("down_day_rs_20d", bars(stock, index, gaps=[2])).iloc[-1])


# --- the long trend -------------------------------------------------------------


def test_price_vs_ma_200():
    close = np.concatenate([np.full(199, 10.0), [12.0]])
    got = run("price_vs_ma_200", bars(close, close)).iloc[-1]
    assert got == pytest.approx(12.0 / ((199 * 10 + 12) / 200) - 1)
    # 199 rows are not enough for a 200-session average.
    assert np.isnan(run("price_vs_ma_200", bars(close[1:], close[1:])).iloc[-1])


def test_ma_200_slope_reads_slope_days_back_and_blanks_a_gap_there():
    close = growth(0.001, 220)
    got = run("ma_200_slope", bars(close, close)).iloc[-1]
    ma = pd.Series(close).rolling(200).mean()
    assert got == pytest.approx(ma.iloc[-1] / ma.iloc[-21] - 1)
    assert np.isnan(run("ma_200_slope", bars(close, close, gaps=[1])).iloc[-1])


def stage(close):
    return run("trend_stage", bars(close, close)).iloc[-1]


N = 260


def test_stage_2_advancing():
    assert stage(growth(0.002, N)) == 2.0


def test_stage_4_declining():
    assert stage(growth(-0.002, N)) == 4.0


def test_stage_3_topping():
    # A long rise, then a short sharp fall below the MA50: MA200 still rising.
    close = np.concatenate([growth(0.003, N - 10), growth(-0.02, 10, 100 * 1.003**249)])
    assert stage(close) == 3.0


def test_stage_1_basing():
    # A long fall, then a short sharp rise above the MA50: MA200 still falling.
    close = np.concatenate([growth(-0.003, N - 10), growth(0.02, 10, 100 * 0.997**249)])
    assert stage(close) == 1.0


def test_stage_is_unknown_without_the_long_average():
    assert np.isnan(stage(growth(0.002, 200)))
    # A missing close inside an otherwise clean window: unknown, never "basing".
    close = growth(0.002, N)
    close[N - 3] = np.nan
    assert np.isnan(stage(close))


def test_stage_blanks_a_gap_at_the_far_end():
    close = growth(0.002, 220)
    # Row 219 reads rows 0..219 (199 for the MA200 + 20 for its slope).
    assert np.isnan(run("trend_stage", bars(close, close, gaps=[1])).iloc[-1])


def test_an_excluded_day_blanks_every_structural_measure():
    close = growth(0.002, N)
    out = compute(bars(close, close * 0.9, excluded=[N - 5]), CFG)[
        0
    ]  # inside every window
    for name in CFG:
        assert np.isnan(out[name].iloc[-1]), name


# --- no look-ahead ----------------------------------------------------------------


@pytest.mark.parametrize("name", list(CFG))
def test_a_value_at_t_uses_only_data_known_by_t(name):
    rng = np.random.default_rng(7)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, N))
    index = 100 * np.cumprod(1 + rng.normal(0.0, 0.01, N))
    t = N - 15
    full = compute(bars(close, index), {name: CFG[name]})[0][name]
    cut = compute(bars(close[: t + 1], index[: t + 1]), {name: CFG[name]})[0][name]
    assert not np.isnan(cut.iloc[-1])
    assert full.iloc[t] == pytest.approx(cut.iloc[-1])


# --- the featureset ----------------------------------------------------------------


def test_the_index_is_joined_by_date_and_never_filled():
    df = frame(n=4)
    idx = pd.DataFrame(
        {
            "trade_date": [df["trade_date"][0], df["trade_date"][2]],
            "close": [1000.0, 1010.0],
        }
    )
    got = structural.with_index(df, idx)["index_close"]
    assert got.iloc[0] == 1000.0 and np.isnan(got.iloc[1]) and got.iloc[2] == 1010.0


def test_every_structural_measure_carries_its_code_hash():
    assert {c.get("code") for c in CFG.values()} == {structural.code_hash()}


def test_the_registered_featureset_is_unchanged():
    """Importing the structural measures adds nothing to features.yaml: the
    featureset the holdout and the scan depend on keeps its fingerprint."""
    names = set(registered_config())
    assert not names & set(CFG)
    assert all(n in REGISTRY for n in CFG)
    old = featureset(registered_config(), "basis")
    new = featureset(structural.full_config(), "basis")
    assert set(new.measures) - set(old.measures) == set(CFG)
    assert old.fingerprint != new.fingerprint


def test_the_schema_can_describe_every_structural_measure():
    """The stored fingerprint's schema is generated from the registry (group =
    the registering module). It must work for the structural featureset, or
    a 20-minute build dies at its write."""
    from vnstock_research.patterns.fingerprint import schema

    sch = schema(featureset(structural.full_config(), "basis")).set_index("column")
    for name in CFG:
        assert sch.loc[name, "group"] == "structural", name
