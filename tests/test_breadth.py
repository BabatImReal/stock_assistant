"""Tests for breadth (features/breadth.py) and its own market frame.

One test per rule, and each fails if its rule is removed.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.features import MARKET_REGISTRY, breadth, compute, compute_market

from ._helpers import frame
from .test_features_market import market_frame
from .test_universe import calendar, rows

DAILY = {
    "breadth_advance_share": {
        "enabled": True,
        "min_count_share": 0.8,
        "count_median_sessions": 20,
    }
}
TEN = {
    "breadth_advance_share_10d": {
        "enabled": True,
        "window_days": 10,
        "min_count_share": 0.8,
        "count_median_sessions": 20,
    }
}


def two_day(symbol_rows):
    """counts() for rows on a two-session calendar; returns the second day."""
    cal = calendar(2)
    df = pd.concat([r(cal) for r in symbol_rows], ignore_index=True)
    return breadth.counts(df, cal).iloc[1]


def breadth_frame(n=60, adv=60, dec=40, unch=10, counted=None):
    cal = calendar(n)
    counted = [adv + dec + unch] * n if counted is None else counted
    return pd.DataFrame(
        {
            "trade_date": cal,
            "advancers": adv,
            "decliners": dec,
            "unchanged": unch,
            "counted": counted,
            "gap_before": 0,
        }
    )


# --- counts: who is counted and which way --------------------------------


def test_direction_uses_the_adjusted_close_so_ex_dividend_is_not_a_decline():
    """Raw close drops 10% on the ex-date; the adjusted series is flat. Using
    the raw close would record a fake decline."""

    def exdiv(cal):
        r = rows(cal, "DIV")
        r["close"] = [10.0, 9.0]  # raw: the dividend comes off the price
        r["adj_close"] = [9.0, 9.0]  # adjusted: no real move
        return r

    day = two_day([exdiv])
    assert (day["advancers"], day["decliners"], day["unchanged"]) == (0, 0, 1)


def test_advancers_and_decliners_are_counted():
    def up(cal):
        r = rows(cal, "UP")
        r["adj_close"] = [10.0, 10.5]
        return r

    def down(cal):
        r = rows(cal, "DN")
        r["adj_close"] = [10.0, 9.5]
        return r

    day = two_day([up, down])
    assert (day["advancers"], day["decliners"], day["counted"]) == (1, 1, 2)


def test_a_stock_resuming_after_a_suspension_is_not_counted_that_day():
    # Its "previous close" is weeks old; comparing against it is the no-gap
    # rule broken with a lookback of one.
    cal = calendar(5)
    df = rows(cal, "SUS", days=[0, 4])
    df["adj_close"] = [10.0, 12.0]
    c = breadth.counts(df, cal)
    assert c["counted"].tolist() == [0, 0, 0, 0, 0]


def test_a_zero_volume_placeholder_yesterday_means_not_counted_today():
    # The placeholder is not a session the stock traded, so today has no real
    # previous close to compare with.
    cal = calendar(3)
    df = rows(cal, "PLH", zero={1})
    df["adj_close"] = [10.0, 10.0, 11.0]
    assert breadth.counts(df, cal)["counted"].tolist() == [0, 0, 0]


def test_breadth_counts_every_tradeable_stock_not_only_liquid_ones():
    """Ben, 2026-09-23: breadth measures the broad participation the
    cap-weighted index misses, so a thin stock that moved counts."""

    def thin(cal):
        r = rows(cal, "THN", volume=1.0)  # far below any liquidity floor
        r["adj_close"] = [10.0, 10.5]
        return r

    assert two_day([thin])["advancers"] == 1


# --- measures on the breadth frame ---------------------------------------


def test_advance_share_is_advancers_over_those_that_moved():
    out, _ = compute_market({"breadth": breadth_frame(adv=60, dec=20, unch=50)}, DAILY)
    assert out["breadth_advance_share"].iloc[-1] == pytest.approx(0.75)


def test_a_thin_day_is_blanked():
    """A lost exchange file (2025-05-05 HNX) leaves a count far below normal;
    a ratio over the exchanges that survived is not whole-market breadth."""
    counted = [110] * 60
    counted[50] = 70  # 64% of the trailing median
    b = breadth_frame(counted=counted)
    out, _ = compute_market({"breadth": b}, DAILY)
    assert np.isnan(out["breadth_advance_share"].iloc[50])
    assert not np.isnan(out["breadth_advance_share"].iloc[49])
    assert not np.isnan(out["breadth_advance_share"].iloc[51])


def test_a_thin_day_blanks_every_ten_day_window_containing_it():
    counted = [110] * 60
    counted[40] = 70
    out, _ = compute_market({"breadth": breadth_frame(counted=counted)}, TEN)
    col = out["breadth_advance_share_10d"]
    assert col.iloc[40:50].isna().all()
    assert not np.isnan(col.iloc[50])


def test_breadth_reads_nothing_older_than_its_declared_lookback():
    """CLAUDE.md: a declared lookback must cover every row a measure reads.
    Changing a row just outside the window must not move today's value."""
    m = MARKET_REGISTRY["breadth_advance_share_10d"]
    p = {k: v for k, v in TEN["breadth_advance_share_10d"].items() if k != "enabled"}
    i = 59
    b = breadth_frame()
    base, _ = compute_market({"breadth": b}, TEN)
    b2 = b.copy()
    # Every row outside the window, and hugely: a median shrugs off one outlier,
    # so a single changed row would not catch a measure that reads too far.
    b2.loc[: i - m.lookback(p) - 1, ["counted", "advancers"]] = [10_000, 1]
    moved, _ = compute_market({"breadth": b2}, TEN)
    assert (
        base["breadth_advance_share_10d"].iloc[i]
        == moved["breadth_advance_share_10d"].iloc[i]
    )


def test_breadth_cannot_see_the_future():
    rng = np.random.default_rng(0)
    b = breadth_frame(n=80)
    b["advancers"] = rng.integers(10, 90, 80)
    full, _ = compute_market({"breadth": b}, {**DAILY, **TEN})
    cut, _ = compute_market({"breadth": b.iloc[:60].copy()}, {**DAILY, **TEN})
    for name in ("breadth_advance_share", "breadth_advance_share_10d"):
        pd.testing.assert_series_equal(
            full[name].iloc[:60], cut[name], check_names=False
        )


# --- the separate frame and the join -------------------------------------


def test_an_index_gap_does_not_blank_breadth():
    """Breadth has its own frame. A missing index day is a defect in the index
    data; it must not remove breadth, which is computed from stock rows."""
    index = market_frame(n=60, gaps=[45])
    b = breadth_frame(n=60)
    cfg = {"index_above_ma_50": {"enabled": True, "window_days": 20}, **DAILY}
    out, _ = compute_market({"index": index, "breadth": b}, cfg)
    assert np.isnan(out["index_above_ma_50"].iloc[50])
    assert out["breadth_advance_share"].iloc[50] == pytest.approx(0.6)


def test_enabling_breadth_without_a_breadth_frame_fails_loudly():
    with pytest.raises(ValueError, match="breadth frame"):
        compute_market({"index": market_frame(n=60)}, DAILY)


def test_breadth_joins_onto_a_symbol_by_trade_date():
    b = breadth_frame(n=60)
    bars = frame(n=60)
    bars["trade_date"] = b["trade_date"]
    out, fs = compute(bars, DAILY, market={"breadth": b})
    assert out["breadth_advance_share"].iloc[-1] == pytest.approx(0.6)
    assert "breadth_advance_share" in fs.measures
