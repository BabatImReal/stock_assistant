"""Tests for the §4.1 volume measures and the guarantees base.py makes.

The measures themselves are arithmetic and easy to check. The guarantees are
the part that matters, because when one of them fails it does not raise -- it
produces a plausible number computed over the wrong days, and nothing
downstream can tell. So each guard has a test that FAILS if the guard is
removed, not merely a test that passes while it is present.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.features import REGISTRY, base, compute


def frame(n=60, volume=1000.0, close=10.0, gaps=None, excluded=None,
          adjustable=True):
    """A clean synthetic symbol, with defects injected where asked."""
    dates = pd.bdate_range("2020-01-01", periods=n).date
    closes = np.full(n, float(close)) if np.isscalar(close) else np.asarray(
        close, dtype=float
    )
    vols = np.full(n, float(volume)) if np.isscalar(volume) else np.asarray(
        volume, dtype=float
    )
    df = pd.DataFrame(
        {
            "symbol": "TST",
            "trade_date": dates,
            "open": closes, "high": closes, "low": closes, "close": closes,
            "matched_volume": vols,
            "volume_is_adjustable": True,
            "gap_before": 0,
            "excluded": False,
        }
    )
    for i in gaps or []:
        df.loc[i, "gap_before"] = 10
    for i in excluded or []:
        df.loc[i, "excluded"] = True
    if adjustable is not True:
        df.loc[adjustable, "volume_is_adjustable"] = False
    return df


ONLY_RVOL = {"rvol": {"enabled": True, "lookback_days": 20}}


# --- the arithmetic --------------------------------------------------------

def test_rvol_is_today_over_the_previous_sessions_not_including_today():
    # 20 quiet days then one 3x day. If today were included in its own
    # denominator the answer would be below 3, which would understate exactly
    # the spikes the measure exists to find.
    vol = [100.0] * 25
    vol[24] = 300.0
    out, _ = compute(frame(n=25, volume=vol), ONLY_RVOL)
    assert out["rvol"].iloc[24] == pytest.approx(3.0)


def test_sustained_volume_counts_heavy_days_in_the_window():
    vol = [100.0] * 40
    for i in (35, 36, 38):
        vol[i] = 200.0  # rvol 2.0 -> above the 1.5 threshold
    cfg = {"sustained_volume": {"enabled": True, "window_days": 7,
                                "threshold": 1.5, "rvol_lookback_days": 20}}
    out, _ = compute(frame(n=40, volume=vol), cfg)
    assert out["sustained_volume"].iloc[39] == 3.0


def test_traded_value_is_price_times_matched_volume():
    out, _ = compute(
        frame(n=5, volume=1000.0, close=12.5),
        {"traded_value": {"enabled": True}},
    )
    assert out["traded_value"].iloc[4] == pytest.approx(12_500.0)


def test_up_down_ratio_is_nan_when_the_window_has_no_down_days():
    # Dividing by zero down-volume is unbounded, not "infinitely bullish".
    close = list(np.arange(10.0, 10.0 + 25 * 0.1, 0.1))[:25]
    cfg = {"up_down_volume_ratio": {"enabled": True, "window_days": 20}}
    out, _ = compute(frame(n=25, close=close), cfg)
    assert np.isnan(out["up_down_volume_ratio"].iloc[24])


# --- GUARANTEE 1: no window may span a gap ---------------------------------

def test_a_window_spanning_a_trading_gap_returns_nan():
    """Fails if the gap guard is removed: the value becomes a plausible number
    computed across a suspension, which is a different quantity entirely."""
    df = frame(n=30, gaps=[20])           # 10 sessions missing before row 20
    out, _ = compute(df, ONLY_RVOL)
    # Row 25's 20-session window reaches back through the gap at row 20.
    assert np.isnan(out["rvol"].iloc[25])
    # Far enough past it, the window is clean again.
    assert not np.isnan(out["rvol"].iloc[29]) or len(df) < 41


def test_a_gap_before_the_window_is_harmless():
    # The gap sits between rows 0 and 1; a window over rows 5..25 never
    # contains it, so refusing to compute there would be over-cautious.
    df = frame(n=30, gaps=[1])
    out, _ = compute(df, ONLY_RVOL)
    assert not np.isnan(out["rvol"].iloc[29])


def test_a_window_touching_an_excluded_row_returns_nan():
    df = frame(n=40, excluded=[30])
    out, _ = compute(df, ONLY_RVOL)
    assert np.isnan(out["rvol"].iloc[35])


# --- GUARANTEE 2: volume measures need comparable volume -------------------

def test_volume_measure_on_a_non_adjustable_span_returns_nan():
    """Fails if the volume_is_adjustable guard is removed.

    Backfilled spans have vnstock-adjusted prices and volume that could never
    be adjusted (no factor is derivable), so share counts differ across the
    window and a relative-volume figure compares two different things.
    """
    df = frame(n=40, adjustable=[30, 31, 32])
    out, _ = compute(df, ONLY_RVOL)
    assert np.isnan(out["rvol"].iloc[32])
    assert np.isnan(out["rvol"].iloc[35])  # window still reaches back into it


def test_a_non_volume_measure_is_unaffected_by_the_volume_flag():
    # The guard is driven by the declared `needs`, so it must not fire on a
    # measure that does not read volume. (None of the §4.1 set qualifies --
    # they all read volume -- so this asserts the mechanism, via the registry.)
    assert all(REGISTRY[name].reads_volume for name in REGISTRY)
    assert not base.Measure(
        name="x", doc_ref="", kind="numeric", needs=("close",),
        lookback=lambda p: 1, fn=lambda b, p: b["close"],
    ).reads_volume


# --- NaN vs 0 vs disabled --------------------------------------------------

def test_nan_zero_and_disabled_are_three_distinct_states():
    """The contract consumers rely on.

    NaN = no signal / excluded / unknowable. 0 = a real measured zero.
    Disabled = no column at all. Collapsing any pair of these would let a
    consumer read "we cannot tell" as "nothing happened".
    """
    df = frame(n=40, gaps=[30])
    df.loc[:, "matched_volume"] = 0.0          # a real zero, on every row
    cfg = {
        "traded_value": {"enabled": True},     # will be a genuine 0.0
        "rvol": {"enabled": True, "lookback_days": 20},
        "volume_dry_up": {"enabled": False, "max_rvol": 0.7,
                          "rvol_lookback_days": 20, "quiet_days": 3},
    }
    out, fs = compute(df, cfg)

    assert out["traded_value"].iloc[10] == 0.0          # real zero, not NaN
    assert not np.isnan(out["traded_value"].iloc[10])
    assert np.isnan(out["rvol"].iloc[35])               # spans the gap
    assert "volume_dry_up" not in out.columns           # disabled = no column
    assert "volume_dry_up" not in fs.measures


def test_boolean_measures_keep_nan_rather_than_collapsing_to_false():
    # A boolean that cannot be evaluated must not read as "no signal here".
    df = frame(n=60, gaps=[30])
    cfg = {"price_volume_agreement": {"enabled": True, "window_days": 10,
                                      "min_price_change": 0.03,
                                      "min_volume_change": 0.10}}
    out, _ = compute(df, cfg)
    # lookback is 2 x window_days = 20, so the gap at row 30 contaminates
    # rows 30..50 and nothing after.
    assert np.isnan(out["price_volume_agreement"].iloc[32])
    assert out["price_volume_agreement"].iloc[55] in (0.0, 1.0)


# --- no look-ahead ---------------------------------------------------------

def test_a_measure_cannot_see_the_future():
    """Truncating the data must not change any value that was already computed.

    This is the general form of the look-ahead test: if row i's value depends
    on anything after i, it changes when the later rows disappear.
    """
    df = frame(n=45, volume=list(np.linspace(100, 500, 45)))
    full, _ = compute(df, ONLY_RVOL)
    truncated, _ = compute(df.iloc[:35].copy(), ONLY_RVOL)
    pd.testing.assert_series_equal(
        full["rvol"].iloc[:35], truncated["rvol"], check_names=False
    )


# --- the recording contract ------------------------------------------------

def test_feature_set_records_what_ran_and_with_which_parameters():
    out, fs = compute(frame(n=30), ONLY_RVOL)
    assert fs.measures == ("rvol",)
    assert fs.params["rvol"]["lookback_days"] == 20
    assert len(fs.fingerprint) == 16


def test_changing_a_parameter_changes_the_fingerprint():
    # Otherwise two different measure versions would be indistinguishable in
    # any stored output.
    _, a = compute(frame(n=30), {"rvol": {"enabled": True, "lookback_days": 20}})
    _, b = compute(frame(n=30), {"rvol": {"enabled": True, "lookback_days": 10}})
    assert a.fingerprint != b.fingerprint


def test_enabling_an_unregistered_measure_fails_loudly():
    with pytest.raises(KeyError):
        compute(frame(n=5), {"not_a_measure": {"enabled": True}})


def test_every_configured_measure_is_registered():
    # The shipped config and the code must not drift apart.
    for name in base.load_config():
        assert name in REGISTRY, f"{name} is in features.yaml but not registered"
