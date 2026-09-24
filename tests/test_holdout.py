"""Tests for the holdout runner (backtest/protocol.py: freeze_date,
holdout_plan, holdout_verdict, holdout, run_holdout). One test per rule; each
fails if its rule is removed.

The synthetic gated table of test_protocol: 30 stocks, k = 3, `hammer_shape`
firing every 5th session, net +2% or -2%.
"""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from vnstock_research.backtest import evidence as ev
from vnstock_research.backtest import protocol as pr
from vnstock_research.backtest.forward_returns import Costs, net_return

from ._helpers import fails_with
from .test_protocol import HAMMER, K, gated, log, proto

RULE = {
    "text": "t",
    "same_sign": True,
    "min_net_expectancy": 0.0,
    "min_declustered": 30,
}


def hproto(start="2017-01-01", end="2017-12-31", **over):
    slices = {
        "discover": {"start": "2015-01-01", "end": "2015-12-31"},
        "validate": {"start": "2016-01-01", "end": "2016-12-31"},
        "holdout": {"start": start, "end": end},
    }
    return proto(slices=slices, holdout_rule=dict(RULE), **over)


def verdict(edge, expectancy, n=100, discover_edge=0.1):
    res = pd.DataFrame(
        {"edge": [edge], "expectancy": [expectancy], "n_declustered": [n]}
    )
    return pr.holdout_verdict([discover_edge], res, hproto()).iloc[0]


def row(**cells):
    return {c: cells.get(c) for c in pr.LOG_COLUMNS}


def validated_log(p, held=("k3:hammer_shape",)):
    h = pr.protocol_hash(p)
    return log(
        [
            row(
                run_id="d",
                slice="discover",
                hypothesis="k3:hammer_shape",
                edge=0.1,
                survived=True,
                protocol=h,
            ),
            row(
                run_id="d",
                slice="discover",
                hypothesis="k3:doji",
                edge=0.1,
                survived=True,
                protocol=h,
            ),
            row(
                run_id="v",
                slice="validate",
                hypothesis="k3:hammer_shape",
                survived="k3:hammer_shape" in held,
                protocol=h,
            ),
            row(
                run_id="v",
                slice="validate",
                hypothesis="k3:doji",
                survived="k3:doji" in held,
                protocol=h,
            ),
        ]
    )


# --- the freeze -----------------------------------------------------------------


def test_the_freeze_is_the_session_before_the_first_entry_still_pending():
    days = [f"2024-01-0{i}" for i in range(1, 8)]
    values = pd.DataFrame(
        {
            "trade_date": days,
            "reason_3": [None, "pending", None, None, None, "pending", "pending"],
            "reason_5": [None, None, None, None, "pending", "pending", "pending"],
        }
    )
    # Before the start does not count; pending at EITHER horizon does.
    assert pr.freeze_date(values, "2024-01-03", [3, 5]) == "2024-01-04"


def test_the_cutoff_is_the_day_after_the_last_settled_session():
    values = pd.DataFrame(
        {"trade_date": pd.bdate_range("2024-01-01", "2024-01-05").date}
    )
    assert pr.cutoff(values) == "2024-01-06"


def test_setting_the_freeze_keeps_the_registration_hash():
    assert pr.protocol_hash(hproto(end="2017-06-30")) == pr.protocol_hash(
        hproto(end=None)
    )
    assert pr.protocol_hash(pr.load_protocol()) == "0106fab4dc2f35a2"


# --- what may run -----------------------------------------------------------------


def test_the_holdout_needs_its_end_frozen():
    p = hproto(end=None)
    fails_with(
        ValueError, "freeze the holdout end", pr.holdout_plan, p, validated_log(p)
    )


def test_the_holdout_runs_once():
    p = hproto()
    spent = pd.concat(
        [validated_log(p), log([row(run_id="h", slice="holdout", hypothesis="x")])]
    )
    fails_with(ValueError, "runs ONCE", pr.holdout_plan, p, spent)


def test_the_holdout_refuses_a_changed_registration():
    fails_with(
        ValueError,
        "changed after its first run",
        pr.holdout_plan,
        hproto(fdr_q=0.2),
        validated_log(hproto()),
    )


def test_the_holdout_takes_only_the_latest_validate_survivors():
    p = hproto()
    old = validated_log(p, held=("k3:doji",)).assign(run_id="old")
    assert pr.holdout_plan(p, pd.concat([old, validated_log(p)])) == [HAMMER]


# --- the rule, as written ---------------------------------------------------------


def test_accepted_only_if_the_edge_keeps_its_discover_sign():
    assert verdict(0.05, 0.01) == "ACCEPT"
    assert verdict(-0.05, 0.01) == "REJECT"


def test_accepted_only_with_net_expectancy_above_zero():
    assert verdict(0.05, 0.0) == "REJECT"


def test_below_thirty_declustered_it_is_not_testable_never_a_pass():
    assert verdict(0.05, 0.01, n=29) == "NOT TESTABLE"
    assert verdict(-0.05, -0.01, n=29) == "NOT TESTABLE"


def test_there_is_no_minimum_edge_on_the_holdout():
    assert verdict(0.001, 0.01) == "ACCEPT"  # the validate rule would need +3 pts


# --- the run ----------------------------------------------------------------------

DISC = {HAMMER.id: 0.1}


def test_only_entries_up_to_the_freeze_count():
    v = gated(start="2017-01-02")
    end = str(v.values["trade_date"].unique()[99])
    res = pr.holdout(v, [HAMMER], hproto(end=end), DISC, 0.001).iloc[0]
    assert res["n_raw"] == 20 * 30  # every 5th of the first 100 sessions


ALWAYS = lambda s, d: d % 5 == 0 or (s + d) % 2 == 0  # noqa: E731  the hammer wins


def test_the_sign_is_compared_with_the_hypothesis_own_discover_edge():
    v = gated(start="2017-01-02", win=ALWAYS)
    res = pr.holdout(v, [HAMMER], hproto(), {HAMMER.id: -0.1}, 0.001).iloc[0]
    assert res["edge"] > 0 and res["expectancy"] > 0 and res["verdict"] == "REJECT"


def test_a_not_testable_hypothesis_is_logged_as_not_accepted():
    v = gated(start="2017-01-02", m=5, win=ALWAYS)
    end = str(v.values["trade_date"].unique()[20])
    res = pr.holdout(v, [HAMMER], hproto(end=end), DISC, 0.001).iloc[0]
    assert res["n_declustered"] == 25 and res["expectancy"] > 0
    assert res["verdict"] == "NOT TESTABLE" and not res["survived"]


def test_an_outcome_not_final_inside_the_holdout_is_refused():
    fp, rt, uni = gated(start="2017-01-02", raw=True)
    rt.values.loc[5, [f"reason_{K}", f"net_{K}", f"ret_{K}"]] = ["pending", None, None]
    p = hproto(end="2017-06-30")
    v = ev.validated(fp, rt, uni)
    fails_with(ValueError, "not final", pr.holdout, v, [HAMMER], p, DISC, 0.001)
    # An outcome known only on or after the cutoff: blanked by the gate.
    fp, rt, uni = gated(start="2017-01-02", raw=True)
    v = ev.validated(fp, rt, uni, before="2017-06-30")
    fails_with(ValueError, "not final", pr.holdout, v, [HAMMER], p, DISC, 0.001)


def test_the_fee_lines_recompute_net_from_the_gross_and_never_change_the_verdict():
    # Hammer days: 60% hits of +2%, losses of -3.5%, gross = net + 0.4%: net
    # expectancy -0.2% at the registered cost, about +0.1% at a zero-fee broker.
    hammer_win = lambda s, d: s % 10 < 6 if d % 5 == 0 else (s + d) % 2 == 0  # noqa: E731
    fp, rt, uni = gated(start="2017-01-02", win=hammer_win, raw=True)
    r = rt.values
    loss = (fp.values["hammer_shape"] == 1) & (r[f"net_{K}"] < 0)
    r.loc[loss, f"net_{K}"] = -0.035
    r[f"ret_{K}"] = r[f"net_{K}"] + 0.004
    res = pr.holdout(ev.validated(fp, rt, uni), [HAMMER], hproto(), DISC, 0.001)
    x = res.iloc[0]
    assert x["edge"] > 0 and x["expectancy"] < 0 and x["verdict"] == "REJECT"
    assert x["exp_at_0.001"] > 0 and x["verdict_at_0.001"] == "ACCEPT"
    assert x["verdict_at_0.004"] == "REJECT"


def test_an_all_in_round_trip_is_both_fees_plus_the_sale_tax():
    v = gated()
    at = pr.at_round_trip(v, 0.004, 0.001).values[f"net_{K}"]
    want = net_return(v.values[f"ret_{K}"], Costs(0.0015, 0.001, True))
    np.testing.assert_allclose(at, want)
    zero = pr.at_round_trip(v, 0.001, 0.001).values[f"net_{K}"]
    np.testing.assert_allclose(
        zero, net_return(v.values[f"ret_{K}"], Costs(0, 0.001, True))
    )


def test_a_round_trip_below_the_sale_tax_is_refused():
    fails_with(
        ValueError, "below the sale tax", pr.at_round_trip, gated(), 0.0005, 0.001
    )


def test_the_break_even_cost_zeroes_the_mean_net():
    v = gated()
    g = float(v.values[f"ret_{K}"].mean())
    net = pr.at_round_trip(v, pr.break_even(g, 0.001), 0.001).values[f"net_{K}"]
    assert net.mean() == pytest.approx(0.0, abs=1e-12)


def test_the_report_labels_the_p_value_and_fees_information_only():
    v = gated(start="2017-01-02")
    res = pr.holdout(v, [HAMMER], hproto(), DISC, 0.001)
    lines = pr.holdout_report(res, 7, hproto(), v.manifest, "run")
    assert "N = 7 | NET PROVISIONAL" in lines[0]
    assert "INFORMATION ONLY (it changes no verdict)" in lines[3]
    assert lines[4].startswith("  [N=7] k3:hammer_shape: REJECT") and "| p " in lines[4]


# --- end to end (loaders pointed at the synthetic tables) --------------------------


@pytest.fixture
def lab(tmp_path, monkeypatch):
    from vnstock_research.backtest import forward_returns as fr
    from vnstock_research.data import universe
    from vnstock_research.patterns import fingerprint as fpm

    fp, rt, uni = gated(
        n=520, win=lambda s, d: d % 5 == 0 or (s + d) % 2 == 0, raw=True
    )
    days = sorted(fp.values["trade_date"].unique())
    # F: 10 sessions before the last one. Entries up to F resolve 4 sessions
    # later, so only the cutoff at the last session keeps them all.
    p = hproto(start="2016-07-01", end=str(days[-11]))
    p["registered"]["slices"]["validate"]["end"] = "2016-06-30"
    monkeypatch.setattr(fpm, "expected", lambda conn: (5, "fs"))
    monkeypatch.setattr(fpm, "load", lambda *a, **k: fp)
    monkeypatch.setattr(fr, "load", lambda *a, **k: rt)
    monkeypatch.setattr(universe, "tiers", lambda *a, **k: uni)
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(p))
    kw = dict(log_path=tmp_path / "log.csv", out=tmp_path / "out", proto_path=path)
    pr.run(None, "discover", **kw)
    pr.run(None, "validate", **kw)
    return SimpleNamespace(
        kw=kw,
        reports=tmp_path / "reports",
        end=str(days[-11]),
        cut=pr.cutoff(fp.values),
    )


def test_the_holdout_logs_its_one_run_and_writes_its_report(lab):
    path = pr.run_holdout(None, reports=lab.reports, **lab.kw)
    assert path.name == f"holdout-{lab.end}.txt"
    assert f"outcomes final before {lab.cut}" in path.read_text()
    log = pr.read_log(lab.kw["log_path"])
    held = set(log.query("slice == 'validate' and survived")["hypothesis"])
    h = log[log["slice"] == "holdout"]
    assert set(h["hypothesis"]) == held and len(h) == len(held)
    assert set(h["protocol"]) == {
        pr.protocol_hash(pr.load_protocol(lab.kw["proto_path"]))
    }
    assert h["code"].notna().all() and set(h["build_id"]) == {5}
    assert h["survived"].all()  # the hammer always wins in this world
    fails_with(
        ValueError, "runs ONCE", pr.run_holdout, None, reports=lab.reports, **lab.kw
    )


# --- after the holdout: describe, never re-judge ------------------------------------


def holdout_log(v, p, verdicts=None, build=None):
    """A log whose holdout rows are what `holdout` really produced on v."""
    res = pr.holdout(v, [HAMMER], p, DISC, 0.001)
    rows = [
        row(
            run_id="h",
            slice="holdout",
            hypothesis=r["hypothesis"],
            build_id=v.manifest["build_id"] if build is None else build,
            n_declustered=r["n_declustered"],
            expectancy=r["expectancy"],
            survived=bool(r["survived"]) if verdicts is None else verdicts,
            protocol=pr.protocol_hash(p),
        )
        for _, r in res.iterrows()
    ]
    return res, log(rows)


def test_the_described_trades_are_the_ones_the_holdout_counted():
    v = gated(start="2017-01-02", win=ALWAYS)
    p = hproto()
    res = pr.holdout(v, [HAMMER], p, DISC, 0.001).iloc[0]
    occ = pr.occurrences(v, HAMMER, p, "2017-01-01", "2017-12-31")
    assert len(occ) == res["n_declustered"]
    assert occ["net"].mean() == pytest.approx(res["expectancy"], rel=1e-12)


def test_the_described_trades_are_de_clustered_like_the_holdout():
    # The hammer fires every 2nd session with k = 3: every other one repeats.
    v = gated(start="2017-01-02", fire=lambda s, d: d % 2 == 0, win=ALWAYS)
    p = hproto()
    res = pr.holdout(v, [HAMMER], p, DISC, 0.001).iloc[0]
    occ = pr.occurrences(v, HAMMER, p, "2017-01-01", "2017-12-31")
    assert res["n_declustered"] < res["n_raw"]
    assert len(occ) == res["n_declustered"]


def test_describe_refuses_trades_that_do_not_reproduce_the_log():
    v = gated(start="2017-01-02", win=ALWAYS)
    p = hproto()
    _, lg = holdout_log(v, p)
    lg.loc[0, "expectancy"] = lg.loc[0, "expectancy"] + 1e-4
    fails_with(
        ValueError, "not the trades it judged", pr.describe_holdout, v, p, lg, 0.001
    )


def test_describe_refuses_another_build():
    v = gated(start="2017-01-02", win=ALWAYS)
    p = hproto()
    _, lg = holdout_log(v, p, build=4)
    fails_with(ValueError, "ran on build", pr.describe_holdout, v, p, lg, 0.001)


def test_describe_keeps_the_logged_verdict_whatever_the_cost():
    v = gated(start="2017-01-02", win=ALWAYS)
    p = hproto()
    _, lg = holdout_log(v, p, verdicts=False)  # the hammer wins, the log says no
    d = pr.describe_holdout(v, p, lg, 0.001, costs=(0.0016, 0.004), paths=20)
    assert set(d["verdict"]) == {"REJECT"} and len(d) == 2


def test_describe_marks_a_hypothesis_below_the_floor_not_testable():
    v = gated(start="2017-01-02", m=5, win=ALWAYS)
    end = str(v.values["trade_date"].unique()[20])
    p = hproto(end=end)
    _, lg = holdout_log(v, p)
    d = pr.describe_holdout(v, p, lg, 0.001, costs=(0.004,), paths=20)
    assert d.iloc[0]["verdict"] == "NOT TESTABLE"


MIXED = lambda s, d: s % 10 < 6 if d % 5 == 0 else (s + d) % 2 == 0  # noqa: E731


def test_describe_recomputes_net_from_the_gross_at_each_cost():
    v = gated(start="2017-01-02", win=MIXED)  # the hammer wins 60%
    p = hproto()
    v.values[f"ret_{K}"] = v.values[f"net_{K}"] + 0.004
    _, lg = holdout_log(v, p)
    d = pr.describe_holdout(
        v, p, lg, 0.001, costs=(0.0016, 0.004, 0.006), paths=20
    ).set_index("cost")
    occ = pr.occurrences(v, HAMMER, p, "2017-01-01", "2017-12-31")
    want = net_return(occ["ret"], Costs(0.0015, 0.001, True))
    assert d.loc[0.004, "worst"] == pytest.approx(want.min())
    # Cheaper trading: every trade keeps more, so the wins grow and losses shrink.
    assert d.loc[0.0016, "avg_win"] > d.loc[0.004, "avg_win"] > d.loc[0.006, "avg_win"]
    assert d.loc[0.0016, "avg_loss"] > d.loc[0.004, "avg_loss"]


def test_the_describe_report_says_information_only_and_nothing_re_judged():
    v = gated(start="2017-01-02", win=ALWAYS)
    p = hproto()
    _, lg = holdout_log(v, p)
    d = pr.describe_holdout(v, p, lg, 0.001, costs=(0.0016, 0.004), paths=20)
    lines = pr.describe_report(d, p, 0.004)
    assert "INFORMATION ONLY" in lines[0] and "nothing is re-judged" in lines[0]
    assert lines[4].startswith("  k3:hammer_shape: ACCEPT")
    assert "avg win" in lines[5] and "max drawdown" in lines[6]
    assert lines[8].startswith("      at 0.16%")


def test_describe_runs_after_the_holdout_and_writes_no_log_row(lab):
    pr.run_holdout(None, reports=lab.reports, **lab.kw)
    before = pr.read_log(lab.kw["log_path"])
    kw = {x: lab.kw[x] for x in ("log_path", "proto_path")}
    path = pr.run_describe_holdout(None, reports=lab.reports, **kw)
    assert path.name == f"holdout-{lab.end}-describe.txt"
    assert "INFORMATION ONLY" in path.read_text()
    pd.testing.assert_frame_equal(pr.read_log(lab.kw["log_path"]), before)
    # Safe to repeat: describing spends nothing.
    pr.run_describe_holdout(None, reports=lab.reports, **kw)
