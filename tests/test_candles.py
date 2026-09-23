"""Tests for patterns tranche 1 (patterns/candles.py): candle anatomy and the
single-candle shapes. One test per rule; each fails if its rule is removed.

Prices are in thousands of VND. On the 2020 dates used by default, the largest
tick at ~20 is HNX/UPCoM's 0.1, so the 3-tick floor is a range of 0.3.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.features import compute, load_config


def bars(
    candles,
    start="2020-01-01",
    raw=None,
    gaps=(),
    excluded=(),
    exchange="HNX",
    unknown=False,
):
    """candles: [(open, high, low, close)]. raw: [(raw_high, raw_low)] or None
    (raw = adjusted). Default exchange HNX (tick 0.1), dated."""
    o, h, lo, c = (np.array([x[i] for x in candles], float) for i in range(4))
    rh, rl = (
        (h, lo)
        if raw is None
        else (
            np.array([x[0] for x in raw], float),
            np.array([x[1] for x in raw], float),
        )
    )
    df = pd.DataFrame(
        {
            "symbol": "TST",
            "trade_date": pd.bdate_range(start, periods=len(candles)).date,
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "matched_volume": 1000.0,
            "volume_is_adjustable": True,
            "gap_before": 0,
            "excluded": False,
            "raw_open": o,
            "raw_high": rh,
            "raw_low": rl,
            "raw_close": c,
            "exchange": exchange,
            "exchange_unknown": unknown,
        }
    )
    for i in gaps:
        df.loc[i, "gap_before"] = 5
    for i in excluded:
        df.loc[i, "excluded"] = True
    return df


def run(name, df, **override):
    p = dict(load_config()[name], enabled=True, **override)
    out, _ = compute(df, {name: p})
    return out[name]


def last(name, candle, **kw):
    return run(name, bars([candle]), **kw).iloc[-1]


HAMMER = (20.8, 21.0, 19.0, 21.0)  # body .2, lower 1.8, upper 0
INVERTED = (19.2, 21.0, 19.0, 19.0)  # body .2, upper 1.8, lower 0
DOJI = (20.0, 21.0, 19.0, 20.1)  # body .1 of a 2.0 range
GREEN = (19.05, 21.0, 19.0, 20.95)  # body 1.9 of 2.0, rising
RED = (20.95, 21.0, 19.0, 19.05)


# --- anatomy -------------------------------------------------------------


def test_anatomy_ratios_are_parts_of_the_range():
    c = (20.0, 21.0, 19.0, 20.5)  # body .5, upper .5, lower 1.0, range 2.0
    assert last("body_to_range", c) == pytest.approx(0.25)
    assert last("upper_wick_to_range", c) == pytest.approx(0.25)
    assert last("lower_wick_to_range", c) == pytest.approx(0.5)


def test_anatomy_is_undefined_on_a_flat_bar():
    for name in ("body_to_range", "upper_wick_to_range", "lower_wick_to_range"):
        assert np.isnan(last(name, (20.0, 20.0, 20.0, 20.0)))


def test_range_rel_is_against_the_previous_sessions_only():
    # 20 sessions of range 1.0, then one of 2.0: exactly 2x its baseline.
    # Including today in the baseline would give 2 / 1.05.
    df = bars([(20.0, 20.5, 19.5, 20.0)] * 20 + [(20.0, 21.0, 19.0, 20.0)])
    assert run("range_rel_20d", df).iloc[-1] == pytest.approx(2.0)


def test_range_rel_is_undefined_against_a_flat_baseline():
    # 20 flat bars (limit-locked or placeholders), then a real candle: the
    # ratio to a zero baseline is undefined, never infinite.
    df = bars([(20.0, 20.0, 20.0, 20.0)] * 20 + [(20.0, 21.0, 19.0, 20.0)])
    assert np.isnan(run("range_rel_20d", df).iloc[-1])


def test_range_rel_is_blank_when_its_window_spans_a_gap():
    df = bars([(20.0, 20.5, 19.5, 20.0)] * 30, gaps=[25])
    out = run("range_rel_20d", df)
    assert not np.isnan(out.iloc[24])  # rows 4..24: clean, full baseline
    assert np.isnan(out.iloc[29])  # rows 9..29 contain the gap


def test_open_gap_is_today_open_against_yesterday_close():
    df = bars([(20.0, 20.5, 19.5, 20.0), (21.0, 21.5, 20.5, 21.0)])
    assert run("open_gap", df).iloc[-1] == pytest.approx(0.05)


def test_open_gap_is_blank_after_a_trading_gap():
    # Yesterday's close is weeks old after a suspension: not a gap open.
    df = bars([(20.0, 20.5, 19.5, 20.0), (21.0, 21.5, 20.5, 21.0)], gaps=[1])
    assert np.isnan(run("open_gap", df).iloc[-1])


def test_windowed_anatomy_cannot_see_the_future():
    rng = np.random.default_rng(0)
    cs = [(20.0, 20.0 + a, 20.0 - b, 20.0) for a, b in rng.uniform(0.1, 1, (40, 2))]
    df = bars(cs)
    for name in ("range_rel_20d", "open_gap"):
        full, cut = run(name, df), run(name, df.iloc[:30].copy())
        pd.testing.assert_series_equal(full.iloc[:30], cut, check_names=False)


# --- hammer shape ----------------------------------------------------------


def test_a_textbook_hammer_fires():
    assert last("hammer_shape", HAMMER) == 1.0


def test_hammer_needs_the_lower_wick_long_enough():
    # With textbook values "body in the top third" already implies lower >= 2x
    # body, so the clause binds only when set stricter: 3x here, wick = 2.5x.
    c = (20.2, 20.4, 19.7, 20.4)  # body .2, lower .5, upper 0, range .7
    assert last("hammer_shape", c, lower_wick_to_body_min=2.0) == 1.0
    assert last("hammer_shape", c, lower_wick_to_body_min=3.0) == 0.0


def test_hammer_needs_a_small_upper_wick():
    # upper .2 > .5 x body .2; every other clause holds.
    assert last("hammer_shape", (20.8, 21.2, 19.0, 21.0)) == 0.0


def test_hammer_needs_the_body_in_the_top_third():
    # body .2, lower .45 (>= 2x body), upper .1 (<= .5x body), but the body
    # starts at 60% of the range, below the top third.
    assert last("hammer_shape", (19.45, 19.75, 19.0, 19.65)) == 0.0


def test_hammer_needs_a_range_above_the_tick_floor():
    # The same proportions two ticks tall.
    assert last("hammer_shape", (20.16, 20.2, 20.0, 20.2)) == 0.0


def test_a_one_tick_candle_is_not_a_hammer():
    """open = close = high, one tick of lower wick: body 0 makes every ratio
    pass. Only the floor stops it; four ticks tall, it is a real (dragonfly)
    hammer."""
    assert last("hammer_shape", (20.1, 20.1, 20.0, 20.1)) == 0.0
    assert last("hammer_shape", (20.4, 20.4, 20.0, 20.4)) == 1.0


def test_the_floor_is_measured_on_the_raw_range():
    # Adjusted candle 2.0 tall, but the raw range traded was one tick.
    df = bars([HAMMER], raw=[(20.1, 20.0)])
    assert run("hammer_shape", df).iloc[-1] == 0.0


def test_an_undated_exchange_uses_the_largest_tick_of_any_exchange():
    # 2015 at ~60: HOSE's tick is 0.5, HNX's 0.1. A 1.0 range is 10 HNX ticks
    # but only 2 HOSE ticks. Filed HNX but NOT dated: judge it by the largest.
    c = (60.9, 61.0, 60.0, 61.0)
    undated = bars([c], start="2015-06-01", unknown=True)
    assert run("hammer_shape", undated).iloc[-1] == 0.0
    dated = bars([c], start="2015-06-01", unknown=False)
    assert run("hammer_shape", dated).iloc[-1] == 1.0


def test_a_dated_exchange_uses_its_own_tick():
    """2020, a 5,000 VND stock: HOSE's tick is 0.01, HNX's 0.1. A 0.05 range is
    5 HOSE ticks, a real candle on HOSE, but half a tick on HNX."""
    c = (4.99, 5.0, 4.95, 5.0)  # body .01, lower .04, upper 0: a hammer shape
    assert run("hammer_shape", bars([c], exchange="HOSE")).iloc[-1] == 1.0
    assert run("hammer_shape", bars([c], exchange="HNX")).iloc[-1] == 0.0


def test_a_shape_on_an_excluded_row_is_unknown_not_false():
    df = bars([HAMMER, HAMMER], excluded=[1])
    out = run("hammer_shape", df)
    assert out.iloc[0] == 1.0 and np.isnan(out.iloc[1])


def test_a_single_candle_shape_is_still_judged_right_after_a_gap():
    # One candle spans no gap: the gap guard must not blank it.
    df = bars([HAMMER, HAMMER], gaps=[1])
    assert run("hammer_shape", df).iloc[-1] == 1.0


# --- inverted hammer shape ---------------------------------------------------


def test_a_textbook_inverted_hammer_fires():
    assert last("inverted_hammer_shape", INVERTED) == 1.0


def test_inverted_hammer_needs_the_upper_wick_long_enough():
    c = (19.9, 20.4, 19.7, 19.7)  # body .2, upper .5, lower 0
    assert last("inverted_hammer_shape", c, upper_wick_to_body_min=2.0) == 1.0
    assert last("inverted_hammer_shape", c, upper_wick_to_body_min=3.0) == 0.0


def test_inverted_hammer_needs_a_small_lower_wick():
    assert last("inverted_hammer_shape", (19.2, 21.0, 18.8, 19.0)) == 0.0


def test_inverted_hammer_needs_the_body_in_the_bottom_third():
    assert last("inverted_hammer_shape", (19.1, 19.75, 19.0, 19.3)) == 0.0


def test_inverted_hammer_needs_a_range_above_the_tick_floor():
    assert last("inverted_hammer_shape", (20.04, 20.2, 20.0, 20.0)) == 0.0


# --- doji and marubozu -----------------------------------------------------


def test_a_doji_fires_on_a_small_body_in_a_real_range():
    assert last("doji", DOJI) == 1.0


def test_doji_needs_the_body_small():
    assert last("doji", (20.0, 21.0, 19.0, 20.3)) == 0.0  # body 15% of range


def test_doji_needs_a_range_above_the_tick_floor():
    # open = close on a 2-tick candle: tick noise, not indecision.
    assert last("doji", (20.1, 20.2, 20.0, 20.1)) == 0.0
    assert last("doji", (20.0, 20.0, 20.0, 20.0)) == 0.0  # flat bar


def test_marubozu_green_and_red_fire_by_colour():
    assert last("marubozu_green", GREEN) == 1.0
    assert last("marubozu_red", RED) == 1.0
    assert last("marubozu_green", RED) == 0.0
    assert last("marubozu_red", GREEN) == 0.0


def test_marubozu_needs_nearly_all_body():
    assert last("marubozu_green", (19.3, 21.0, 19.0, 20.95)) == 0.0  # 82.5%


def test_marubozu_needs_a_range_above_the_tick_floor():
    # A 2-tick candle that is all body.
    assert last("marubozu_green", (20.0, 20.2, 20.0, 20.2)) == 0.0
    assert last("marubozu_red", (20.2, 20.2, 20.0, 20.0)) == 0.0
