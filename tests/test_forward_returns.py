"""Tests for the tradeable forward-return definition (G3).

The settlement era logic is the part worth guarding: the 2016 change is a trap,
because moving to "T+2 settlement" did NOT make shares sellable on T+2 -- the
money landed at 16:30, after the close. A test that only checked "2016 means
T+2" would encode exactly the mistake the definition exists to avoid.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.backtest import forward_returns as fr
from vnstock_research.data import checks

from ._helpers import fails_with


@pytest.mark.parametrize(
    ("entry_date", "expected"),
    [
        ("2012-05-04", 3),  # first era: settles morning of T+3
        ("2015-12-30", 3),  # trades of late Dec 2015 still settled T+3
        ("2016-01-04", 3),  # T+2 settlement, but at 16:30 -- still sells T+3
        ("2020-06-01", 3),
        ("2022-08-24", 3),  # last day of the middle era
        ("2022-08-25", 2),  # settlement before 13:00 -- sellable T+2 afternoon
        ("2026-09-21", 2),
    ],
)
def test_earliest_sell_offset_by_era(entry_date, expected):
    assert fr.earliest_sell_offset(entry_date) == expected


def test_both_documented_horizons_are_valid_in_every_era():
    # doc §1: patterns form over 3-5 days and the question is the following few.
    # If an era made k=3 unsellable the whole horizon choice would need revisiting.
    for date in ("2012-05-04", "2018-06-01", "2024-06-03"):
        assert fr.valid_horizons(date, (3, 5)) == [3, 5]


def test_one_day_horizon_is_never_tradeable():
    # The doc's own warning: a 1-day edge cannot be traded under any VN
    # settlement regime, which is why the 3-5 day horizon was chosen.
    for date in ("2012-05-04", "2024-06-03"):
        assert fr.valid_horizons(date, (1,)) == []


def test_costs_are_charged_on_both_sides_and_the_tax_on_the_sale():
    costs = fr.load_costs()
    assert costs.round_trip == pytest.approx(2 * 0.0015 + 0.001)
    # A flat trade still loses the round trip: the sale tax is charged whether
    # or not the trade made money.
    assert fr.net_return(0.0, costs) < 0
    assert fr.net_return(0.0, costs) == pytest.approx(-costs.round_trip, abs=1e-5)


def test_net_return_is_below_gross_and_preserves_order():
    costs = fr.load_costs()
    assert fr.net_return(0.05, costs) < 0.05
    assert fr.net_return(0.05, costs) > fr.net_return(0.02, costs)


def test_every_settlement_era_is_marked_verified():
    # These came from Ben with sources. If an unverified era ever appears, the
    # backtest is resting on a guess and should say so.
    assert all(era["verified"] for era in fr.settlement_eras())


# --- the generator (B2): one symbol, HOSE 2020, flat at 20.0 unless changed.
# At 20.0 the ceiling is 21.40 and the floor 18.60 (tick 0.05).


def stock(n=12, start="2020-01-01", exchange="HOSE", unknown=False):
    dates = list(pd.bdate_range(start, periods=n).date)
    df = pd.DataFrame(
        {
            "symbol": "TST",
            "trade_date": dates,
            "open": 20.0,
            "high": 20.0,
            "low": 20.0,
            "close": 20.0,
            "matched_volume": 1000.0,
            "gap_before": 0,
            "excluded": False,
            "date_shifted": False,
            "exchange": exchange,
            "exchange_unknown": unknown,
        }
    )
    return df


def set_bar(df, i, **prices):
    """Set adjusted AND raw prices of row i (no corporate action)."""
    for col, value in prices.items():
        df.loc[i, col] = value
    return df


def run(df, k=3, extra_sessions=0):
    """Outcomes with raw = adjusted unless the test set raw_* itself."""
    df = df.copy()
    for col in ("open", "high", "low", "close"):
        if "raw_" + col not in df:
            df["raw_" + col] = df[col]
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    last = pd.Timestamp(df["trade_date"].iloc[-1])
    more = pd.bdate_range(last, periods=extra_sessions + 1).date[1:]
    return fr.outcomes(df, list(df["trade_date"]) + list(more), ks=(k,))


def test_the_return_is_exit_close_over_entry_open_on_adjusted_prices():
    """A 2-for-1 split on row 3: raw prices halve, adjusted ones do not. The
    raw return would be about -45%."""
    df = set_bar(stock(), 1, open=19.0)
    df = set_bar(df, 4, close=21.0)
    for col in ("open", "high", "low", "close"):
        df["raw_" + col] = df[col] * np.where(df.index < 3, 2.0, 1.0)
    out = run(df)
    assert out["ret_3"].iloc[0] == pytest.approx(21.0 / 19.0 - 1)
    assert out["known_on_3"].iloc[0] == df["trade_date"].iloc[4]
    assert out["exit_offset_3"].iloc[0] == 4


def test_net_is_after_both_fees_and_the_sale_tax():
    out = run(set_bar(stock(), 4, close=21.0))
    assert out["net_3"].iloc[0] == pytest.approx(
        fr.net_return(out["ret_3"].iloc[0], fr.load_costs())
    )


def test_mfe_and_mae_span_the_entry_to_the_exit_only():
    df = set_bar(stock(), 1, low=19.2)
    df = set_bar(df, 2, high=20.9)
    df = set_bar(df, 5, high=30.0, low=10.0)  # after the exit: not read
    out = run(df)
    assert out["mfe_3"].iloc[0] == pytest.approx(20.9 / 20.0 - 1)
    assert out["mae_3"].iloc[0] == pytest.approx(19.2 / 20.0 - 1)


def test_a_signal_whose_window_passes_the_last_session_is_pending():
    out = run(stock())
    assert out["reason_3"].tolist()[-4:] == ["pending"] * 4
    assert pd.isna(out["reason_3"].iloc[-5])
    assert np.isnan(out["ret_3"].iloc[-1])


def test_a_stock_that_stops_trading_is_counted_apart_from_pending():
    """G11: the market went on and the stock did not -- delisted, or still
    suspended. Never mixed with 'not known yet'."""
    out = run(stock(), extra_sessions=10)
    assert out["reason_3"].tolist()[-4:] == ["data_ends"] * 4


def test_no_entry_when_the_next_row_comes_after_a_gap():
    df = stock()
    df.loc[1, "gap_before"] = 5
    assert run(df)["reason_3"].iloc[0] == "no_next_session"


def test_a_gap_inside_the_window_blanks_the_outcome():
    df = stock()
    df.loc[3, "gap_before"] = 2
    out = run(df)
    assert out["reason_3"].iloc[0] == "window_gap"
    assert np.isnan(out["ret_3"].iloc[0])


def test_a_gap_on_a_deferral_session_blanks_it_too():
    df = set_bar(stock(), 4, close=18.6)  # the exit closes at the floor
    df.loc[5, "gap_before"] = 3
    assert run(df)["reason_3"].iloc[0] == "window_gap"


def test_an_excluded_row_on_the_signal_day_or_in_the_window_blanks_it():
    df = stock()
    df.loc[2, "excluded"] = True
    assert run(df)["reason_3"].iloc[0] == "window_excluded"
    df = stock()
    df.loc[0, "excluded"] = True
    assert run(df)["reason_3"].iloc[0] == "window_excluded"
    df = stock()
    df.loc[1, "excluded"] = True  # the entry day
    assert run(df)["reason_3"].iloc[0] == "window_excluded"


def test_an_entry_day_without_matched_volume_has_no_outcome():
    df = stock()
    df.loc[1, "matched_volume"] = 0.0
    assert run(df)["reason_3"].iloc[0] == "not_tradeable"


def test_an_exit_day_that_was_date_shifted_has_no_outcome():
    df = stock()
    df.loc[4, "date_shifted"] = True
    assert run(df)["reason_3"].iloc[0] == "not_tradeable"


def test_k_must_be_sellable_in_the_entry_era():
    # k = 2 is sellable only from 2022-08-25 (T+2 afternoon).
    assert run(stock(), k=2)["reason_2"].iloc[0] == "not_sellable"
    later = stock(start="2023-01-02")
    assert pd.isna(run(later, k=2)["reason_2"].iloc[0])


def test_an_entry_opening_at_the_ceiling_is_rejected():
    assert run(set_bar(stock(), 1, open=21.4))["reason_3"].iloc[0] == "entry_at_ceiling"
    # One tick below the ceiling is a fill.
    assert pd.isna(run(set_bar(stock(), 1, open=21.35))["reason_3"].iloc[0])


def test_an_exit_at_the_floor_moves_to_the_next_session():
    df = set_bar(stock(), 4, close=18.6)
    df = set_bar(df, 5, close=19.0)
    out = run(df)
    assert out["deferred_3"].iloc[0] == 1
    assert out["exit_offset_3"].iloc[0] == 5
    assert out["known_on_3"].iloc[0] == df["trade_date"].iloc[5]
    assert out["ret_3"].iloc[0] == pytest.approx(19.0 / 20.0 - 1)
    assert out["mae_3"].iloc[0] == pytest.approx(18.6 / 20.0 - 1)


def floor_chain(n):
    """n consecutive floor closes from 20.0, each at the floor of the last."""
    closes, c = [], 20.0
    for _ in range(n):
        c = float(
            checks.limit_prices([c], ["HOSE"], ["2020-01-08"], [False])["floor"][0]
        )
        closes.append(round(c, 2))
    return closes


def test_an_exit_still_at_the_floor_after_the_cap_is_dropped():
    cap = fr.MAX_EXIT_DEFERRAL
    df = stock(n=16)
    for j, c in enumerate(floor_chain(cap), start=4):
        set_bar(df, j, open=c, close=c)
    out = run(df)
    assert pd.isna(out["reason_3"].iloc[0])  # the last allowed attempt fills
    assert out["deferred_3"].iloc[0] == cap
    df = stock(n=16)
    for j, c in enumerate(floor_chain(cap + 1), start=4):
        set_bar(df, j, open=c, close=c)
    out = run(df)
    assert out["reason_3"].iloc[0] == "exit_floor_unresolved"
    assert np.isnan(out["ret_3"].iloc[0])


def test_the_reference_on_an_ex_date_is_the_adjusted_previous_close():
    """Entry day t+1 is a 2-for-1 ex-date: raw 20.0 yesterday, reference 10.0
    today, so an open of 10.70 is the ceiling. Against the raw 20.0 it would
    look like a collapse, not a limit-up."""
    df = stock()
    for col in ("open", "high", "low", "close"):
        df[col] = 10.0
    df = set_bar(df, 1, open=10.7, close=10.7)
    for col in ("open", "high", "low", "close"):
        df["raw_" + col] = df[col] * np.where(df.index < 1, 2.0, 1.0)
    assert run(df)["reason_3"].iloc[0] == "entry_at_ceiling"


@pytest.mark.parametrize(
    ("exchange", "unknown", "flag", "upcom"),
    [
        ("UPCOM", False, True, True),
        ("HOSE", True, True, False),
        ("HOSE", False, False, False),
    ],
)
def test_an_outcome_on_upcom_or_an_undated_exchange_is_flagged(
    exchange, unknown, flag, upcom
):
    out = run(stock(exchange=exchange, unknown=unknown))
    assert out["flag__fill_3"].iloc[0] == flag
    assert out["upcom_3"].iloc[0] == upcom


def test_an_exchange_without_limits_quarantines_the_outcome():
    # No tick table, no ceiling: "not at the ceiling" is not known.
    out = run(stock(exchange="OTC"))
    assert out["flag__fill_3"].iloc[0]


def test_a_flag_on_any_exit_attempt_flags_the_outcome():
    """Every row whose fillability was judged counts: the entry and each exit
    attempt, not only the entry."""
    df = set_bar(stock(), 4, close=18.6)  # deferred: exit on row 5
    df.loc[5, "exchange_unknown"] = True
    assert run(df)["flag__fill_3"].iloc[0]


def test_an_outcome_reads_nothing_after_it_resolves():
    df = set_bar(stock(n=14), 4, close=18.6)  # resolves on row 5
    df = set_bar(df, 3, high=20.8)
    df = set_bar(df, 6, high=25.0)  # after the outcome resolved: never read
    full = run(df, extra_sessions=5)
    cut = run(df.iloc[:6], extra_sessions=13)
    pd.testing.assert_series_equal(full.iloc[0], cut.iloc[0], check_names=False)
    shorter = run(df.iloc[:5], extra_sessions=14)
    assert shorter["reason_3"].iloc[0] == "data_ends"


# --- storage -----------------------------------------------------------------


def stored(tmp_path, build_id=5):
    values = run(set_bar(stock(n=300), 4, close=21.0), extra_sessions=0)
    fr.write(values, build_id, tmp_path)
    return values


def test_storage_round_trips_and_records_what_it_was_built_from(tmp_path):
    values = stored(tmp_path)
    rt = fr.load(5, root=tmp_path)
    assert list(rt.values.columns) == list(values.columns)
    assert rt.values["ret_3"].equals(values["ret_3"])
    assert list(rt.values["reason_3"]) == list(values["reason_3"])
    m = rt.manifest
    assert (m["build_id"], m["rules"], m["code"]) == (
        5,
        fr.rules_hash(),
        fr.code_hash(),
    )
    assert m["net_provisional"] is True  # the 0.15% broker fee is not confirmed


def test_changed_rule_files_are_refused(tmp_path, monkeypatch):
    stored(tmp_path)
    monkeypatch.setattr(fr, "rules_hash", lambda: "new-limits")
    fails_with(
        FileNotFoundError,
        "no returns for build 5, rules new-limits",
        fr.load,
        5,
        root=tmp_path,
    )


def test_changed_code_is_refused(tmp_path, monkeypatch):
    stored(tmp_path)
    monkeypatch.setattr(fr, "code_hash", lambda: "newer-code")
    fails_with(ValueError, "stale returns.*code", fr.load, 5, root=tmp_path)


def test_an_outcome_column_always_brings_its_flag(tmp_path):
    stored(tmp_path)
    rt = fr.load(5, root=tmp_path, columns=["net_3", "ret_3"])
    assert list(rt.values.columns) == [
        "symbol",
        "trade_date",
        "net_3",
        "ret_3",
        "flag__fill_3",
    ]


def test_a_join_across_two_builds_is_refused(tmp_path):
    from types import SimpleNamespace

    values = stored(tmp_path)
    rt = fr.load(5, root=tmp_path)
    keys = rt.values[["symbol", "trade_date"]].assign(rvol=1.0)
    other = SimpleNamespace(values=keys, manifest={"build_id": 6})
    fails_with(ValueError, "build 6 to returns of build 5", fr.join, other, rt)
    same = SimpleNamespace(values=keys, manifest={"build_id": 5})
    assert len(fr.join(same, rt)) == len(values)
