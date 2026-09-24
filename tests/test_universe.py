"""Tests for the point-in-time universe (data/universe.py).

One test per rule, and each fails if its rule is removed. No database: the
rules live in pure functions over synthetic bar_raw rows.
"""

import pandas as pd

from vnstock_research.data import universe

CFG = {
    "lookback_days": 60,
    "min_trading_days_in_lookback": 40,
    "min_avg_matched_value": 1000.0,
}


def calendar(n=80, start="2020-01-01"):
    return list(pd.bdate_range(start, periods=n).date)


def rows(
    cal,
    symbol="AAA",
    close=10.0,
    volume=100.0,
    days=None,
    shifted=(),
    excluded=(),
    zero=(),
):
    """One symbol's bar_raw rows on `days` (indices into cal; default all).

    Default traded value = 10 x 100 = 1000, exactly the CFG floor.
    """
    days = range(len(cal)) if days is None else days
    df = pd.DataFrame(
        {
            "trade_date": [cal[i] for i in days],
            "symbol": symbol,
            "close": float(close),
            "matched_volume": [0.0 if i in zero else float(volume) for i in days],
            "date_shifted": [i in shifted for i in days],
            "excluded": [i in excluded for i in days],
            "adj_close": float(close),
        }
    )
    return df


def col(panel, symbol="AAA"):
    return panel[symbol].tolist()


# --- tradeable ------------------------------------------------------------


def test_a_zero_volume_row_is_not_tradeable():
    # A placeholder at the previous close is not a day anyone could trade.
    cal = calendar(5)
    t = universe.tradeable_panel(rows(cal, zero={2}), cal)
    assert col(t) == [True, True, False, True, True]


def test_a_row_moved_off_a_weekend_is_not_tradeable():
    cal = calendar(5)
    t = universe.tradeable_panel(rows(cal, shifted={3}), cal)
    assert col(t) == [True, True, True, False, True]


def test_a_row_in_an_excluded_window_is_not_tradeable():
    cal = calendar(5)
    t = universe.tradeable_panel(rows(cal, excluded={1}), cal)
    assert col(t) == [True, False, True, True, True]


def test_a_delisted_stock_counts_on_the_days_it_traded():
    """G11: membership comes from rows on each date, not from who is listed
    today. A stock that stopped trading is still in the universe back when it
    traded, and out afterwards."""
    cal = calendar(10)
    both = pd.concat([rows(cal, "LIV"), rows(cal, "DEL", days=range(6))])
    t = universe.tradeable_panel(both, cal)
    assert col(t, "DEL") == [True] * 6 + [False] * 4
    assert col(t, "LIV") == [True] * 10


# --- liquid ---------------------------------------------------------------


def test_liquid_needs_the_minimum_number_of_traded_sessions():
    cal = calendar(60)
    # 40 of the 60 sessions traded, including the last one: liquid.
    ok, _ = universe.liquid_panel(rows(cal, days=range(20, 60)), cal, CFG)
    assert ok["AAA"].iloc[-1]
    # 39 of 60: not liquid.
    no, _ = universe.liquid_panel(rows(cal, days=range(21, 60)), cal, CFG)
    assert not no["AAA"].iloc[-1]


def test_average_value_is_over_the_days_traded_not_every_session():
    """40 traded days at exactly the floor must pass. Averaging over all 60
    sessions (counting untraded ones as 0) would put it at 2/3 of the floor."""
    cal = calendar(60)
    liq, avg = universe.liquid_panel(rows(cal, days=range(20, 60)), cal, CFG)
    assert liq["AAA"].iloc[-1]
    assert avg["AAA"].iloc[-1] == 1000.0


def test_below_the_value_floor_is_not_liquid():
    cal = calendar(60)
    liq, _ = universe.liquid_panel(rows(cal, volume=99.0), cal, CFG)
    assert not liq["AAA"].iloc[-1]


def test_the_window_counts_sessions_not_calendar_days():
    """A long closure (Tet, or a gap in the calendar) is not missing trading.
    30 sessions, a 7-week break, 30 more: the stock traded all 60 SESSIONS. A
    60-calendar-day window would see only the last 30 and call it illiquid."""
    cal = calendar(30, "2020-01-01") + calendar(30, "2020-04-01")
    liq, _ = universe.liquid_panel(rows(cal), cal, CFG)
    assert liq["AAA"].iloc[-1]


def test_not_liquid_on_a_day_it_did_not_trade():
    # 59 traded sessions of history cannot make it buyable on a day it was
    # suspended.
    cal = calendar(61)
    liq, _ = universe.liquid_panel(rows(cal, days=range(60)), cal, CFG)
    assert liq["AAA"].iloc[59]
    assert not liq["AAA"].iloc[60]


def test_a_short_history_is_not_judged():
    # Fewer than lookback_days sessions of calendar: the window is not full.
    cal = calendar(59)
    liq, _ = universe.liquid_panel(rows(cal), cal, CFG)
    assert not liq["AAA"].any()


def test_liquidity_cannot_see_the_future():
    cal = calendar(120)
    vol = [100.0] * 70 + [5000.0] * 50  # much busier later
    df = rows(cal)
    df["matched_volume"] = vol
    full, _ = universe.liquid_panel(df, cal, CFG)
    cut, _ = universe.liquid_panel(df.iloc[:80], cal[:80], CFG)
    pd.testing.assert_series_equal(full["AAA"].iloc[:80], cut["AAA"])


# --- liquidity tiers (the §7.1 fallback's middle level) ----------------------


def test_tiers_rank_the_days_liquid_set_by_trailing_value():
    """Terciles among the stocks liquid THAT day; a stock not liquid has no
    tier, and a thinner stock never outranks a busier one."""
    cal = calendar(70)
    r = pd.concat(
        [
            rows(cal, "AAA", volume=100.0),
            rows(cal, "BBB", volume=200.0),
            rows(cal, "CCC", volume=300.0),
            rows(cal, "EEE", volume=400.0),
            rows(cal, "DDD", volume=1.0),
        ],
        ignore_index=True,
    )
    _, avg = universe.liquid_panel(r, cal, CFG)
    last = universe.tier_panel(avg, 3).iloc[-1]
    # Four liquid stocks in three tiers: percentiles .25/.5/.75/1 -> 1/2/3/3.
    assert [last[s] for s in ("AAA", "BBB", "CCC", "EEE")] == [1.0, 2.0, 3.0, 3.0]
    assert pd.isna(last["DDD"])  # below the liquidity floor: no tier
    assert universe.tier_panel(avg, 3).iloc[:59].isna().all().all()


def test_the_universe_rows_are_the_liquid_stock_days_only():
    cal = calendar(70)
    r = pd.concat(
        [rows(cal, "AAA", volume=100.0), rows(cal, "DDD", volume=1.0)],
        ignore_index=True,
    )
    _, avg = universe.liquid_panel(r, cal, CFG)
    t = universe.tier_rows(avg, 3, cal[0])
    assert set(t["symbol"]) == {"AAA"}  # DDD is never liquid: never a row
    assert len(t) == 70 - 59  # AAA from its first full 60-session window
