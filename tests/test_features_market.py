"""Tests for the market-regime measures and the join (doc §5.3).

The join is where the new failure modes live. A market measure is computed on
the calendar and then attached to a symbol's rows, so the things that can go
wrong are different from the per-symbol case: a symbol date the market frame
lacks, and a gap in the index itself -- which, unlike a symbol suspension, is a
defect in our data rather than a fact about the market.
"""

import numpy as np
import pandas as pd

from vnstock_research.features import MARKET_REGISTRY, compute, compute_market

from ._helpers import fails_with, frame

REGIME = {"index_above_ma_50": {"enabled": True, "window_days": 50}}


def market_frame(n=120, close=100.0, gaps=None, start="2020-01-01"):
    dates = pd.bdate_range(start, periods=n).date
    closes = np.full(n, float(close)) if np.isscalar(close) else np.asarray(
        close, dtype=float
    )
    df = pd.DataFrame(
        {
            "symbol": "VNINDEX",
            "trade_date": dates,
            "open": closes, "high": closes, "low": closes, "close": closes,
            "volume": 1.0,
            "gap_before": 0,
        }
    )
    for i in gaps or []:
        df.loc[i, "gap_before"] = 5
    return df


def test_index_above_its_average_is_detected():
    close = list(np.arange(100.0, 100.0 + 120 * 0.5, 0.5))[:120]  # rising
    out, _ = compute_market(market_frame(n=120, close=close), REGIME)
    assert out["index_above_ma_50"].iloc[119] == 1.0

    close = list(np.arange(160.0, 160.0 - 120 * 0.5, -0.5))[:120]  # falling
    out, _ = compute_market(market_frame(n=120, close=close), REGIME)
    assert out["index_above_ma_50"].iloc[119] == 0.0


def test_a_gap_in_the_index_is_fatal_to_the_window():
    """Unlike a symbol suspension, this is a defect in our data: the index
    trades every session the market is open."""
    out, _ = compute_market(market_frame(n=120, gaps=[80]), REGIME)
    assert np.isnan(out["index_above_ma_50"].iloc[100])


def test_regime_joins_onto_a_symbol_by_trade_date():
    close = list(np.arange(100.0, 100.0 + 120 * 0.5, 0.5))[:120]
    market = market_frame(n=120, close=close)
    bars = frame(n=120)
    bars["trade_date"] = market["trade_date"]
    out, fs = compute(bars, REGIME, market=market)
    assert "index_above_ma_50" in out.columns
    assert out["index_above_ma_50"].iloc[119] == 1.0
    assert "index_above_ma_50" in fs.measures


def test_a_symbol_date_the_market_lacks_is_nan_not_forward_filled():
    """Carrying yesterday's regime forward would assert a market state we have
    no index for -- the quiet kind of wrong the guards exist to stop."""
    close = list(np.arange(100.0, 100.0 + 120 * 0.5, 0.5))[:120]
    market = market_frame(n=120, close=close)
    bars = frame(n=121)
    bars["trade_date"] = list(market["trade_date"]) + [
        pd.Timestamp("2035-01-01").date()  # a session the index does not cover
    ]
    out, _ = compute(bars, REGIME, market=market)
    assert not np.isnan(out["index_above_ma_50"].iloc[119])
    assert np.isnan(out["index_above_ma_50"].iloc[120])


def test_enabling_a_market_measure_without_a_market_frame_fails_loudly():
    # Silently dropping it would leave a hole exactly where the regime context
    # should be, and nothing downstream could tell.
    fails_with(ValueError, "no market frame", compute, frame(n=60), REGIME)


def test_market_measures_are_absent_from_the_per_symbol_registry():
    from vnstock_research.features import REGISTRY

    for name in MARKET_REGISTRY:
        assert name not in REGISTRY


def test_fingerprint_covers_both_registries():
    """A change to a regime parameter must change the fingerprint, or two
    different feature sets would be indistinguishable in any stored output."""
    close = list(np.arange(100.0, 100.0 + 120 * 0.5, 0.5))[:120]
    market = market_frame(n=120, close=close)
    bars = frame(n=120)
    bars["trade_date"] = market["trade_date"]

    base_cfg = {"rvol": {"enabled": True, "lookback_days": 20}, **REGIME}
    _, a = compute(bars, base_cfg, market=market)

    changed = {
        "rvol": {"enabled": True, "lookback_days": 20},
        "index_above_ma_50": {"enabled": True, "window_days": 20},
    }
    _, b = compute(bars, changed, market=market)
    assert a.fingerprint != b.fingerprint
    assert set(a.measures) == {"rvol", "index_above_ma_50"}


def test_market_measures_cannot_see_the_future():
    close = list(np.arange(100.0, 100.0 + 120 * 0.5, 0.5))[:120]
    market = market_frame(n=120, close=close)
    full, _ = compute_market(market, REGIME)
    truncated, _ = compute_market(market.iloc[:90].copy(), REGIME)
    pd.testing.assert_series_equal(
        full["index_above_ma_50"].iloc[:90],
        truncated["index_above_ma_50"],
        check_names=False,
    )
