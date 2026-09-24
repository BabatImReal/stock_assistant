"""Tests for the look-alike search (backtest/neighbours.py, E4) and the E3
display layer (families, exploratory avoid candidates). One test per rule;
each fails if its rule is removed.

A synthetic world: 5 stocks over 30 sessions, all liquid, every outcome
resolving 4 sessions later; the query is stock A on the last day.
"""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vnstock_research.backtest import neighbours as nb
from vnstock_research.backtest import protocol as pr
from vnstock_research.features.base import FLAG

from ._helpers import fails_with

DAYS = list(pd.bdate_range("2015-01-01", periods=34).date)
SYMS = ["A", "B", "C", "D", "E"]
Q = DAYS[29]


def nproto(**over):
    spec = {
        "numeric": ["rvol", "price_vs_ma_20"],
        "boolean": ["near_support", "near_resistance", "volume_dry_up"],
        "min_known_share": 0.8,
        "k": 3,
        "horizons": [3],
        "pool_before": "2030-01-01",
    }
    spec.update(over)
    return {"registered": {"triggers": ["hammer_shape", "doji"]}, "neighbours": spec}


def world():
    f, r = [], []
    for j, d in enumerate(DAYS[:30]):
        for i, s in enumerate(SYMS):
            f.append(
                {
                    "symbol": s,
                    "trade_date": d,
                    "hammer_shape": 0.0,
                    "doji": 0.0,
                    "rvol": 1.0 + i + j / 100,
                    "price_vs_ma_20": i / 10,
                    "near_support": 0.0,
                    "near_resistance": 0.0,
                    "volume_dry_up": 0.0,
                }
            )
            r.append(
                {
                    "symbol": s,
                    "trade_date": d,
                    "ret_3": 0.014,
                    "net_3": 0.01,
                    "mfe_3": 0.02,
                    "mae_3": -0.01,
                    "exit_offset_3": 4,
                    "deferred_3": 0,
                    "known_on_3": DAYS[j + 4],
                    "reason_3": None,
                    "upcom_3": False,
                    f"{FLAG}fill_3": False,
                }
            )
    fp = SimpleNamespace(
        values=pd.DataFrame(f),
        manifest={"build_id": 5, "flagged": [], "featureset": "f", "code": "c"},
    )
    rt = SimpleNamespace(
        values=pd.DataFrame(r),
        manifest={
            "build_id": 5,
            "horizons": [3],
            "net_provisional": True,
            "rules": "r",
            "code": "c",
        },
    )
    uni = fp.values[["symbol", "trade_date"]].assign(tier=1)
    return fp, rt, uni


def at(fp, symbol, day, **values):
    m = (fp.values["symbol"] == symbol) & (fp.values["trade_date"] == day)
    for c, x in values.items():
        fp.values.loc[m, c] = x


def search(fp, rt, uni, p=None, symbol="A", day=Q):
    return nb.look_alikes(fp, rt, uni, symbol, day, p or nproto())


def hammer_world():
    """A fires a hammer on the query day; B and C fired one on day 10; D fired
    a hammer AND a doji on day 10."""
    fp, rt, uni = world()
    at(fp, "A", Q, hammer_shape=1.0)
    at(fp, "B", DAYS[10], hammer_shape=1.0)
    at(fp, "C", DAYS[10], hammer_shape=1.0)
    at(fp, "D", DAYS[10], hammer_shape=1.0, doji=1.0)
    return fp, rt, uni


def found(la):
    return list(zip(la.neighbours["symbol"], la.neighbours["trade_date"], strict=True))


# --- registration -------------------------------------------------------------


def test_the_method_is_registered_with_its_own_frozen_block(tmp_path):
    p = pr.load_protocol()
    spec = p["neighbours"]
    assert (spec["k"], spec["min_known_share"], spec["pool_before"]) == (
        50,
        0.8,
        "2024-01-01",
    )
    assert pr.protocol_hash(p) == "0106fab4dc2f35a2"  # E3 untouched
    log = tmp_path / "log.csv"
    pd.DataFrame([{"neighbours": "an-older-method"}]).to_csv(log, index=False)
    fails_with(ValueError, "changed after its first run", nb.check_frozen, p, log)


# --- matching -----------------------------------------------------------------


def test_a_neighbour_has_exactly_todays_fired_set():
    la = search(*hammer_world())
    assert la.fired == "hammer_shape|"
    assert set(found(la)) == {("B", DAYS[10]), ("C", DAYS[10])}


def test_an_unjudged_trigger_never_matches():
    fp, rt, uni = hammer_world()
    at(fp, "C", DAYS[10], doji=np.nan)
    assert set(found(search(fp, rt, uni))) == {("B", DAYS[10])}
    at(fp, "A", Q, doji=np.nan)
    assert search(fp, rt, uni).reason == "a trigger could not be judged that day"


def test_numerics_are_the_same_day_percentile_among_liquid_stocks():
    fp, rt, uni = world()
    rows = fp.values.assign(tier=1.0)
    rows.loc[(rows["symbol"] == "E") & (rows["trade_date"] == DAYS[3]), "tier"] = np.nan
    enc = nb.encode(rows, nproto()["neighbours"], ["hammer_shape", "doji"])
    day = enc[enc["trade_date"] == DAYS[3]].set_index("symbol")["rvol"]
    # Four liquid stocks that day: 0.25, 0.5, 0.75, 1.0; E is not ranked.
    assert day[["A", "B", "C", "D"]].tolist() == [0.25, 0.5, 0.75, 1.0]
    assert np.isnan(day["E"])
    # Another day's values never move this day's percentiles.
    rows.loc[rows["trade_date"] == DAYS[4], "rvol"] = 99.0
    again = nb.encode(rows, nproto()["neighbours"], ["hammer_shape", "doji"])
    np.testing.assert_array_equal(
        again[again["trade_date"] == DAYS[3]]["rvol"].to_numpy(),
        enc[enc["trade_date"] == DAYS[3]]["rvol"].to_numpy(),
    )


def test_booleans_stay_one_or_zero():
    fp, _, _ = world()
    at(fp, "B", DAYS[2], near_support=1.0)
    enc = nb.encode(
        fp.values.assign(tier=1.0), nproto()["neighbours"], ["hammer_shape", "doji"]
    )
    assert enc["near_support"].tolist() == fp.values["near_support"].tolist()


def test_a_missing_value_never_matches_a_zero():
    d, share = nb.distance(
        np.array([np.nan, 0.0, 0.0, 0.0, 0.0]),
        np.array([[0.0, 0.0, 0.0, 0.0, 0.0]]),
        0.8,
    )
    assert share[0] == 0.8 and d[0] == 0.0


def test_a_pair_needs_the_registered_share_of_columns_known():
    d, _ = nb.distance(
        np.array([0.1, 0.2, np.nan, np.nan, 0.5]),
        np.array([[0.1, 0.2, 0.3, 0.4, 0.5]]),
        0.8,
    )
    assert np.isnan(d[0])


def test_the_distance_is_the_equal_weight_mean_absolute_difference():
    d, _ = nb.distance(np.array([0.2, 0.4]), np.array([[0.6, 0.4]]), 0.8)
    assert d[0] == pytest.approx(0.2)


def test_the_k_nearest_are_returned_nearest_first():
    fp, rt, uni = world()
    for j in range(4, 12):
        # Days 4-7 differ from the query on one boolean; days 8-11 do not.
        at(fp, "B", DAYS[j], hammer_shape=1.0, near_support=float(j < 8))
    at(fp, "A", Q, hammer_shape=1.0)
    la = search(fp, rt, uni)
    assert found(la) == [("B", DAYS[8]), ("B", DAYS[9]), ("B", DAYS[10])]
    assert la.neighbours["distance"].is_monotonic_increasing


# --- the pool -------------------------------------------------------------------


def test_the_pool_holds_only_outcomes_resolved_before_the_query_day():
    fp, rt, uni = world()
    at(fp, "A", Q, hammer_shape=1.0)
    at(fp, "B", DAYS[25], hammer_shape=1.0)  # resolves on DAYS[29], the query day
    at(fp, "C", DAYS[24], hammer_shape=1.0)  # resolves the day before
    assert found(search(fp, rt, uni)) == [("C", DAYS[24])]


def test_until_the_holdout_is_run_the_pool_stops_before_it():
    fp, rt, uni = hammer_world()
    at(fp, "E", DAYS[20], hammer_shape=1.0)
    la = search(fp, rt, uni, p=nproto(pool_before=str(DAYS[18])))
    assert ("E", DAYS[20]) not in found(la) and la.pool_before == str(DAYS[18])


def test_the_pool_passes_the_gate():
    fp, rt, uni = hammer_world()
    m = (rt.values["symbol"] == "B") & (rt.values["trade_date"] == DAYS[10])
    rt.values.loc[m, f"{FLAG}fill_3"] = True  # fillability flagged
    uni = uni[~((uni["symbol"] == "C") & (uni["trade_date"] == DAYS[10]))]  # not liquid
    assert found(search(fp, rt, uni)) == []


def test_the_query_must_be_liquid_that_day():
    fp, rt, uni = hammer_world()
    uni = uni[~((uni["symbol"] == "A") & (uni["trade_date"] == Q))]
    assert search(fp, rt, uni).reason == "not liquid that day"


def test_every_report_is_stamped_illustrative_and_provisional():
    lines = nb.report(search(*hammer_world()), nproto())
    assert "ILLUSTRATIVE, not a statistical claim" in lines[0]
    assert "NET PROVISIONAL" in lines[0]


# --- E3 display: families and exploratory avoid candidates ----------------------


def test_nested_survivors_form_one_family_across_horizons():
    ids = ["k3:m+a", "k5:m+a+b", "k3:m+b", "k3:x+a", "k3:m+c"]
    fams = pr.families(ids)
    assert ["k3:m+a", "k3:m+b", "k5:m+a+b"] in fams  # {a},{b} joined via {a,b}
    assert ["k3:m+c"] in fams and ["k3:x+a"] in fams


def test_a_family_is_listed_most_general_first():
    assert pr.families(["k3:m+a+b", "k3:m+a"]) == [["k3:m+a", "k3:m+a+b"]]


def test_negative_edge_survivors_are_shown_only_as_exploratory_avoid_candidates():
    rows = [
        {
            "run_id": "d",
            "slice": "discover",
            "hypothesis": "k3:m+a",
            "edge": 0.05,
            "p": 0.001,
            "survived": True,
        },
        {
            "run_id": "d",
            "slice": "discover",
            "hypothesis": "k3:e+a",
            "edge": -0.2,
            "p": 0.002,
            "survived": True,
        },
        {
            "run_id": "d",
            "slice": "discover",
            "hypothesis": "k3:z",
            "edge": -0.3,
            "p": 0.5,
            "survived": False,
        },
        {
            "run_id": "v",
            "slice": "validate",
            "hypothesis": "k3:m+a",
            "edge": 0.04,
            "expectancy": 0.01,
            "survived": True,
        },
        {
            "run_id": "v",
            "slice": "validate",
            "hypothesis": "k3:e+a",
            "edge": -0.1,
            "expectancy": -0.01,
            "survived": False,
        },
    ]
    lines = pr.summary(pd.DataFrame(rows, columns=pr.LOG_COLUMNS))
    text = "\n".join(lines)
    assert "held on validate 1, in 1 families" in lines[0]
    assert "EXPLORATORY 'avoid' candidates: 1" in text
    assert "k3:e+a: discover edge -20.0%" in text and "k3:z" not in text
