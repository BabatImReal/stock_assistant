"""Tests for the G20 factor-defect detector (data/checks.py `factor_triage`)
and how a defect blanks windows like a gap. One test per rule; each fails if
its rule is removed.

HOSE 2020, flat at 20.0: the daily limit is 7%, so a jump is > 14%.
"""

import numpy as np
import pandas as pd

from vnstock_research.backtest import forward_returns as fr
from vnstock_research.data import checks
from vnstock_research.features import compute

from ._helpers import frame


def series(n=12, exchange="HOSE"):
    dates = list(pd.bdate_range("2020-01-01", periods=n).date)
    return pd.DataFrame(
        {
            "symbol": "TST",
            "trade_date": dates,
            "close": 20.0,
            "raw_close": 20.0,
            "factor": 1.0,
            "exchange": exchange,
            "gap_before": 0,
            "is_adjusted_source": False,
        }
    )


def step(df, i, adj_move, factor_ratio):
    """From row i on: the adjusted close moves by adj_move and the factor by
    factor_ratio (raw = adjusted / factor)."""
    df.loc[i:, "close"] = 20.0 * (1 + adj_move)
    df.loc[i:, "factor"] = factor_ratio
    df["raw_close"] = df["close"] / df["factor"]
    return df


def label(df, i=5):
    return checks.factor_triage(df).iloc[i]


def test_a_jump_on_a_factor_change_day_is_a_defect():
    # BNA's shape: the factor changed and the adjusted series stepped +25%.
    assert label(step(series(), 5, 0.25, 3.0)) == "defect"


def test_a_jump_with_no_factor_change_is_left_to_the_gate():
    # Raw and adjusted both +25%, same factor: the price-limit check's case.
    assert label(step(series(), 5, 0.25, 1.0)) is None


def test_a_move_within_twice_the_limit_is_not_a_jump():
    assert label(step(series(), 5, 0.13, 3.0)) is None


def test_a_resumption_is_legitimate_and_already_a_gap():
    df = step(series(), 5, 0.25, 3.0)
    df.loc[5, "gap_before"] = 25
    assert label(df) == "resumption"
    df.loc[5, "gap_before"] = 24
    assert label(df) == "defect"


def test_the_first_day_on_a_new_exchange_inside_its_band_is_legitimate():
    # UPCoM -> HOSE: HOSE's first-day band is 20%, so +18% is legal there.
    df = step(series(exchange="UPCOM"), 5, 0.18, 1.0001)
    df.loc[5:, "exchange"] = "HOSE"
    df["raw_close"] = df["close"] / df["factor"]
    assert label(df) == "new_exchange"
    df = step(series(exchange="UPCOM"), 5, 0.30, 1.0001)
    df.loc[5:, "exchange"] = "HOSE"
    assert label(df) == "defect"
    # The same +18% step with NO change of exchange is not legitimate.
    assert label(step(series(), 5, 0.18, 1.0001)) == "defect"


def test_backfilled_rows_are_not_judged():
    df = step(series(), 5, 0.25, 3.0)
    df["is_adjusted_source"] = True
    assert label(df) is None


def test_the_detector_reads_only_the_day_and_the_one_before():
    df = step(series(), 5, 0.25, 3.0)
    df = step(df, 6, -0.4, 0.2)  # another step the next day
    full, cut = checks.factor_triage(df), checks.factor_triage(df.iloc[:6])
    assert full.iloc[:6].tolist() == cut.tolist()


# --- a defect blanks every window across it, like a gap -------------------


def test_a_factor_break_blanks_feature_windows_like_a_gap():
    cfg = {"rvol": {"enabled": True, "lookback_days": 5}}
    broken = frame(n=30)
    broken["factor_break"] = False
    broken.loc[20, "factor_break"] = True
    gapped = frame(n=30, gaps=[20])
    a, b = compute(broken, cfg)[0]["rvol"], compute(gapped, cfg)[0]["rvol"]
    assert a.isna().tolist() == b.isna().tolist()
    assert a.iloc[20:25].isna().all() and a.iloc[25:].notna().all()


def outcome_bars(n=12):
    dates = list(pd.bdate_range("2020-01-01", periods=n).date)
    df = pd.DataFrame(
        {
            "symbol": "TST",
            "trade_date": dates,
            "matched_volume": 1000.0,
            "gap_before": 0,
            "excluded": False,
            "date_shifted": False,
            "exchange": "HOSE",
            "exchange_unknown": False,
            "factor_break": False,
        }
    )
    for col in ("open", "high", "low", "close"):
        df[col] = df["raw_" + col] = 20.0
    return df


def test_a_factor_break_blanks_a_return_window():
    df = outcome_bars()
    df.loc[3, "factor_break"] = True  # inside the holding window of t = 0
    out = fr.outcomes(df, list(df["trade_date"]), ks=(3,))
    assert out["reason_3"].iloc[0] == "factor_break"
    assert np.isnan(out["ret_3"].iloc[0])
    # On the entry day too: the reference for the ceiling would be wrong.
    assert out["reason_3"].iloc[2] == "factor_break"
