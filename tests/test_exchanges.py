"""Tests for dated exchange membership (data/exchanges.py) and the flag it puts
on per-exchange results.

One test per rule; each fails if its rule is removed.
"""

import datetime as dt
import json

import pandas as pd

from vnstock_research.data import checks, exchanges

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
    s = spans(
        [
            ("ACG", "UPCOM", D(2015, 1, 5), D(2017, 12, 29), "cafef_transfer"),
            ("ACG", "HOSE", D(2018, 1, 2), D(2026, 9, 21), "cafef_transfer"),
            ("ACG", "HOSE", D(2018, 5, 22), None, "kbs_listing"),
        ]
    )
    r = exchanges.resolve(s, "ACG", DATES, ["HOSE"] * 4)
    assert r["exchange"].tolist() == ["UPCOM", "HOSE", "HOSE", "HOSE"]
    assert not r["exchange_unknown"].any()


def test_observed_transfer_spans_outrank_the_kbs_listing_date():
    # If KBS dates the move earlier than CafeF still shows trading on the old
    # exchange, the trading record wins for those days.
    s = spans(
        [
            ("XYZ", "HNX", D(2015, 1, 5), D(2018, 5, 21), "cafef_transfer"),
            ("XYZ", "HOSE", D(2018, 1, 1), None, "kbs_listing"),
        ]
    )
    r = exchanges.resolve(s, "XYZ", DATES, ["HOSE"] * 4)
    assert r["exchange"].tolist()[:2] == ["HNX", "HNX"]


def test_a_backfill_row_is_never_dated_by_kbs():
    """Rule B: a vnstock backfill row is pre-transfer by construction (G4 Class
    B), so a KBS date on or before it can only be the ORIGINAL listing date."""
    s = spans([("SHB", "HOSE", D(2009, 4, 20), None, "kbs_listing")])
    r = exchanges.resolve(s, "SHB", DATES, ["HOSE"] * 4, [True, True, False, False])
    assert r["exchange_unknown"].tolist() == [True, True, False, False]


def test_the_longer_transfer_span_wins_an_overlap():
    # Three stray one-day HOSE filings sit inside long UPCoM spans (2015-09-01).
    s = spans(
        [
            ("PXL", "HOSE", D(2016, 6, 1), D(2016, 6, 1), "cafef_transfer"),
            ("PXL", "UPCOM", D(2010, 12, 9), D(2026, 9, 21), "cafef_transfer"),
        ]
    )
    r = exchanges.resolve(s, "PXL", DATES, ["UPCOM", "HOSE", "UPCOM", "UPCOM"])
    assert r["exchange"].tolist() == ["UPCOM"] * 4


def test_a_symbol_with_no_evidence_is_unknown_everywhere():
    r = exchanges.resolve(spans([]), "ZZZ", DATES, ["UPCOM"] * 4)
    assert r["exchange_unknown"].all()


def test_only_a_listed_exchange_with_a_date_becomes_a_span(tmp_path):
    for sym, ex, day in [
        ("AAA", "UPCoM", "05/01/2015"),
        ("BBB", "OTC", "19/07/2023"),
        ("CCC", "", ""),
        ("DDD", "HNX", ""),
    ]:
        (tmp_path / f"{sym}.json").write_text(
            json.dumps({"symbol": sym, "exchange": ex, "listing_date": day})
        )
    (tmp_path / "EEE.json").write_text(json.dumps({"symbol": "EEE", "error": "x"}))
    rows = exchanges.kbs_rows(tmp_path)
    assert rows[["symbol", "exchange"]].values.tolist() == [["AAA", "UPCOM"]]
    assert rows["valid_from"].iloc[0] == D(2015, 1, 5)


def test_the_limit_is_the_one_in_force_for_that_exchange_and_date():
    rate = checks.limit_rate(
        ["HNX", "HNX", "UPCOM"], [D(2012, 6, 1), D(2014, 6, 1), D(2020, 1, 2)]
    )
    assert rate.tolist() == [0.07, 0.10, 0.15]  # HNX widened on 2013-01-15
