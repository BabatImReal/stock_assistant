"""Tests for dated exchange membership (data/exchanges.py) and the flag it puts
on per-exchange results (backtest/forward_returns.py `fillability`).

One test per rule; each fails if its rule is removed.
"""

import datetime as dt
import json

import numpy as np
import pandas as pd

from vnstock_research.backtest import forward_returns as fr
from vnstock_research.data import exchanges
from vnstock_research.features import quarantine_flagged
from vnstock_research.features.base import FLAG

D = dt.date


def spans(rows):
    return pd.DataFrame(rows, columns=exchanges.SPAN_COLUMNS)


DATES = [D(2016, 6, 1), D(2018, 5, 21), D(2018, 5, 22), D(2020, 1, 2)]


def test_a_listing_that_predates_the_history_needs_no_flag():
    s = spans([("VNM", "HOSE", D(2006, 1, 19), None, "kbs_listing")])
    r = exchanges.resolve(s, "VNM", DATES, ["HOSE"] * 4)
    assert not r["exchange_unknown"].any()


def test_before_the_listing_date_the_exchange_is_unknown_and_borrowed():
    """DPG: in CafeF's HSX file from 2017, but on HOSE only from 2018-05-22."""
    s = spans([("DPG", "HOSE", D(2018, 5, 22), None, "kbs_listing")])
    r = exchanges.resolve(s, "DPG", DATES, ["HOSE"] * 4)
    assert r["exchange_unknown"].tolist() == [True, True, False, False]
    assert r["exchange"].tolist() == ["HOSE"] * 4  # borrowed where unknown


def test_documented_transfer_spans_date_the_earlier_exchange():
    """ACG-like Class A: UPCoM to 2017-12-29, HOSE from 2018-01-02."""
    s = spans([
        ("ACG", "UPCOM", D(2015, 1, 5), D(2017, 12, 29), "cafef_transfer"),
        ("ACG", "HOSE", D(2018, 1, 2), D(2026, 9, 21), "cafef_transfer"),
        ("ACG", "HOSE", D(2018, 5, 22), None, "kbs_listing"),
    ])
    r = exchanges.resolve(s, "ACG", DATES, ["HOSE"] * 4)
    assert r["exchange"].tolist() == ["UPCOM", "HOSE", "HOSE", "HOSE"]
    assert not r["exchange_unknown"].any()


def test_observed_transfer_spans_outrank_the_kbs_listing_date():
    # If KBS dates the move earlier than CafeF still shows trading on the old
    # exchange, the trading record wins for those days.
    s = spans([
        ("XYZ", "HNX", D(2015, 1, 5), D(2018, 5, 21), "cafef_transfer"),
        ("XYZ", "HOSE", D(2018, 1, 1), None, "kbs_listing"),
    ])
    r = exchanges.resolve(s, "XYZ", DATES, ["HOSE"] * 4)
    assert r["exchange"].tolist()[:2] == ["HNX", "HNX"]


def test_a_symbol_with_no_evidence_is_unknown_everywhere():
    r = exchanges.resolve(spans([]), "ZZZ", DATES, ["UPCOM"] * 4)
    assert r["exchange_unknown"].all()


def test_only_a_listed_exchange_with_a_date_becomes_a_span(tmp_path):
    for sym, ex, day in [("AAA", "UPCoM", "05/01/2015"), ("BBB", "OTC", "19/07/2023"),
                         ("CCC", "", ""), ("DDD", "HNX", "")]:
        (tmp_path / f"{sym}.json").write_text(
            json.dumps({"symbol": sym, "exchange": ex, "listing_date": day}))
    (tmp_path / "EEE.json").write_text(json.dumps({"symbol": "EEE", "error": "x"}))
    rows = exchanges.kbs_rows(tmp_path)
    assert rows[["symbol", "exchange"]].values.tolist() == [["AAA", "UPCOM"]]
    assert rows["valid_from"].iloc[0] == D(2015, 1, 5)


# --- the flag on per-exchange results (G3 fillability) --------------------

def bars(exchange="HOSE", unknown=False, open_move=0.07, n=3):
    closes = [100.0] * n
    opens = [100.0] + [100.0 * (1 + open_move)] * (n - 1)
    return pd.DataFrame({
        "trade_date": [D(2020, 1, 2 + i) for i in range(n)],
        "open": opens, "close": closes,
        "exchange": exchange, "exchange_unknown": unknown,
    })


def test_the_limit_is_the_one_in_force_for_that_exchange_and_date():
    assert fr.limit_in_force("HNX", D(2012, 6, 1)) == 0.07   # before 2013-01-15
    assert fr.limit_in_force("HNX", D(2014, 6, 1)) == 0.10
    assert fr.limit_in_force("UPCOM", D(2020, 1, 2)) == 0.15


def test_fillability_uses_the_exchange_it_is_given():
    # +7% at the open is the ceiling on HOSE but not on HNX (+-10%).
    assert fr.fillability(bars("HOSE"))["entry_at_ceiling"].iloc[1] == 1.0
    assert fr.fillability(bars("HNX"))["entry_at_ceiling"].iloc[1] == 0.0
    assert np.isnan(fr.fillability(bars("HOSE"))["entry_at_ceiling"].iloc[0])


def test_every_fillability_result_on_an_unknown_exchange_is_flagged():
    out = fr.fillability(bars(unknown=True))
    for name in fr.FILLABILITY:
        assert out[FLAG + name].all()
    assert not fr.fillability(bars())[FLAG + "limit"].any()


def test_quarantine_blanks_flagged_fillability_like_sector_values():
    b = bars(n=4)
    b["exchange_unknown"] = [True, True, False, False]
    clean = quarantine_flagged(fr.fillability(b), fr.FILLABILITY)
    assert clean["limit"].iloc[:2].isna().all()
    assert clean["entry_at_ceiling"].iloc[2] == 1.0
    assert not any(c.startswith(FLAG) for c in clean.columns)
