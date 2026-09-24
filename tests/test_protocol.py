"""Tests for the research protocol (backtest/protocol.py, E3): the
pre-registration, the hypothesis log, the split, the date-block bootstrap,
Benjamini-Hochberg, the validate rule and the reporting. One test per rule;
each fails if its rule is removed.

A synthetic gated table: 30 stocks, every row liquid and with an outcome,
k = 3; `hammer_shape` fires where the test says, and each row's net return is
+2% (a hit) or -2%.
"""

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vnstock_research.backtest import evidence as ev
from vnstock_research.backtest import protocol as pr
from vnstock_research.features.base import FLAG

from ._helpers import fails_with

K = 3


def proto(**over):
    reg = {
        "horizons": [K],
        "triggers": ["hammer_shape", "doji"],
        "conditions": {"at_support": {"near_support": 1}},
        "max_conditions": 1,
        "slices": {
            "discover": {"start": "2015-01-01", "end": "2015-12-31"},
            "validate": {"start": "2016-01-01", "end": "2016-12-31"},
            "holdout": {"start": "2017-01-01", "end": None},
        },
        "min_declustered": 30,
        "suspicious_hit_rate": 0.75,
        "regime": "index_above_ma_50",
        "fdr_q": 0.10,
        "bootstrap": {"block_sessions": 10, "resamples": 1000, "seed": 1},
        "validate_rule": {
            "same_sign": True,
            "min_edge": 0.03,
            "min_net_expectancy": 0.0,
        },
    }
    reg.update(over)
    return {"registered": reg, "additions": []}


def gated(
    n=260,
    m=30,
    fire=lambda s, d: d % 5 == 0,
    win=lambda s, d: (s + d) % 2 == 0,
    regime=lambda s, d: 1.0,
    start="2015-01-01",
    raw=False,
):
    """A Validated table (or the raw fp, rt, universe with raw=True)."""
    dates = list(pd.bdate_range(start, periods=n + 10).date)
    f, r = [], []
    for s in range(m):
        d = np.arange(n)
        fired = np.array([fire(s, x) for x in d], float)
        wins = np.array([win(s, x) for x in d])
        net = np.where(wins, 0.02, -0.02)
        f.append(
            pd.DataFrame(
                {
                    "symbol": f"S{s:02d}",
                    "trade_date": dates[:n],
                    "hammer_shape": fired,
                    "doji": 0.0,
                    "near_support": 1.0,
                    "index_above_ma_50": [regime(s, x) for x in d],
                }
            )
        )
        r.append(
            pd.DataFrame(
                {
                    "symbol": f"S{s:02d}",
                    "trade_date": dates[:n],
                    f"ret_{K}": net + 0.004,
                    f"net_{K}": net,
                    f"mfe_{K}": 0.03,
                    f"mae_{K}": -0.03,
                    f"exit_offset_{K}": 4,
                    f"deferred_{K}": 0,
                    f"known_on_{K}": dates[4 : n + 4],
                    f"reason_{K}": None,
                    f"upcom_{K}": False,
                    f"{FLAG}fill_{K}": False,
                }
            )
        )
    fp = SimpleNamespace(
        values=pd.concat(f, ignore_index=True),
        manifest={"build_id": 5, "flagged": [], "featureset": "f", "code": "c"},
    )
    rt = SimpleNamespace(
        values=pd.concat(r, ignore_index=True),
        manifest={
            "build_id": 5,
            "horizons": [K],
            "net_provisional": True,
            "rules": "r",
            "code": "c",
        },
    )
    uni = fp.values[["symbol", "trade_date"]].assign(tier=1)
    return (fp, rt, uni) if raw else ev.validated(fp, rt, uni)


HAMMER = pr.Hypothesis("hammer_shape", (), K)


def one(v, p=None, h=HAMMER, start="2015-01-01", end="2016-12-31"):
    return pr.evaluate(v, [h], p or proto(), start, end).iloc[0]


def log(rows):
    return pd.DataFrame(rows, columns=pr.LOG_COLUMNS)


# --- pre-registration ---------------------------------------------------------


def test_the_registered_vocabulary_is_1554_hypotheses_in_both_horizons():
    hyps = pr.vocabulary(pr.load_protocol())
    assert len(hyps) == 21 * (1 + 8 + 28) * 2 == 1554
    assert len({h.id for h in hyps}) == 1554
    assert {h.k for h in hyps} == {3, 5}


def test_a_trigger_must_be_a_boolean_pattern():
    fails_with(
        ValueError, "not a boolean pattern", pr.vocabulary, proto(triggers=["rvol"])
    )


def test_a_sector_condition_is_refused():
    p = proto(conditions={"sector_up": {"stock_vs_sector_20d": ">0"}})
    fails_with(ValueError, "sector value is flagged", pr.vocabulary, p)


def test_the_registration_is_frozen_once_run():
    p = proto()
    ok = log([{"protocol": pr.protocol_hash(p), "hypothesis": "x"}])
    pr.check_registration(p, ok)
    fails_with(
        ValueError,
        "changed after its first run",
        pr.check_registration,
        proto(fdr_q=0.2),
        ok,
    )


def test_the_holdout_is_never_run_here():
    fails_with(ValueError, "ONCE, with Ben", pr.run, None, "holdout")


# --- the log --------------------------------------------------------------------


def test_n_counts_every_hypothesis_ever_run():
    past = log([{"hypothesis": "k3:a"}, {"hypothesis": "k3:b"}])
    now = [pr.Hypothesis("b", (), 3), pr.Hypothesis("c", (), 3)]
    assert pr.n_tested(past, now) == 3


def test_a_late_hypothesis_is_refused_on_data_already_spent():
    used = log([{"run_id": "r1", "slice": "discover", "hypothesis": "k3:hammer_shape"}])
    pr.check_unused([HAMMER], "discover", used)  # part of the first use
    late = pr.Hypothesis("doji", (), K)
    fails_with(
        ValueError, "already spent", pr.check_unused, [HAMMER, late], "discover", used
    )
    pr.check_unused([HAMMER, late], "validate", used)  # validate is unused
    # A later run that slipped doji onto discover does not make it legitimate:
    # only the FIRST use counts.
    both = log(
        [
            {"run_id": "r1", "slice": "discover", "hypothesis": HAMMER.id},
            {"run_id": "r2", "slice": "discover", "hypothesis": late.id},
        ]
    )
    fails_with(ValueError, "already spent", pr.check_unused, [late], "discover", both)


def test_validate_takes_only_the_latest_discover_survivors():
    doji = pr.Hypothesis("doji", (), K)
    past = log(
        [
            {
                "run_id": "r1",
                "slice": "discover",
                "hypothesis": HAMMER.id,
                "survived": True,
            },
            {
                "run_id": "r1",
                "slice": "discover",
                "hypothesis": doji.id,
                "survived": False,
            },
            {
                "run_id": "r2",
                "slice": "discover",
                "hypothesis": HAMMER.id,
                "survived": False,
            },
            {
                "run_id": "r2",
                "slice": "discover",
                "hypothesis": doji.id,
                "survived": True,
            },
        ]
    )
    assert pr.survivors(past, [HAMMER, doji], "discover") == [doji]


# --- the split ------------------------------------------------------------------


def test_a_slice_counts_only_its_own_dates_and_purges_into_the_next():
    assert pr._slice(proto(), "discover") == ("2015-01-01", "2015-12-31", "2016-01-01")
    fp, rt, uni = gated(n=520, raw=True)
    rows = fp.values
    date = pd.to_datetime(rows["trade_date"])
    fired = rows["hammer_shape"].eq(1)
    # Only the slice's own dates, both ends.
    r = one(ev.validated(fp, rt, uni), start="2015-07-01", end="2015-12-31")
    in_range = (date >= "2015-07-01") & (date <= "2015-12-31")
    assert r["n_raw"] == int((fired & in_range).sum())
    # And the purge: an outcome known only in the next slice is not counted.
    r = one(ev.validated(fp, rt, uni, before="2016-01-01"), end="2015-12-31")
    known = pd.to_datetime(rt.values[f"known_on_{K}"]) < pd.Timestamp("2016-01-01")
    assert r["n_raw"] == int((fired & (date.dt.year == 2015) & known).sum())


# --- significance ---------------------------------------------------------------


def test_significance_resamples_blocks_of_dates_not_rows():
    """All 30 stocks fire on the same 10 days, spread 25 sessions apart: 8 good
    days, 2 bad. 300 rows look overwhelming; 10 independent days do not."""
    days = [5 + 25 * i for i in range(10)]
    r = one(
        gated(
            fire=lambda s, d: d in days,
            win=lambda s, d: d in days[:8] or (d not in days and (s + d) % 2 == 0),
        )
    )
    assert r["edge"] > 0.25
    assert r["p"] > 0.02


def test_the_test_is_two_sided():
    # A pattern that loses: 20% hits against a 50% base is significant too.
    r = one(
        gated(
            win=lambda s, d: (
                (d % 5 == 0 and s % 5 == 0) or (d % 5 != 0 and (s + d) % 2 == 0)
            )
        )
    )
    assert r["edge"] < -0.2 and r["p"] < 0.01


def test_repeats_within_k_sessions_are_counted_once():
    r = one(gated(fire=lambda s, d: True, m=5), p=proto(min_declustered=1))
    assert r["n_raw"] == 5 * 260 and r["n_declustered"] == 5 * 65


def test_too_few_declustered_occurrences_are_not_testable():
    r = one(gated(fire=lambda s, d: s == 0 and d % 10 == 0))  # 26 occurrences
    assert (r["testable"], r["p"]) == (False, 1.0)


def test_benjamini_hochberg_over_all_n():
    p = [0.001, 0.025, 0.5]
    assert pr.benjamini_hochberg(p, 0.10).tolist() == [True, True, False]
    # The same p-values among N = 10 hypotheses: the bar rises.
    assert pr.benjamini_hochberg(p, 0.10, m=10).tolist() == [True, False, False]
    # Step-up: 0.07 passes its bar (0.10), so 0.06 below it passes too, though
    # 0.06 misses its own (0.05).
    assert pr.benjamini_hochberg([0.06, 0.07], 0.10).tolist() == [True, True]


def test_discovery_counts_every_hypothesis_ever_run_and_needs_testability():
    res = pd.DataFrame({"p": [0.004, 0.025, 0.001], "testable": [True, True, False]})
    # Among 3: all three pass BH, but the untestable one never survives.
    assert pr.discover_verdict(res, proto(), 3).tolist() == [True, True, False]
    # Among N = 30 ever run: the bar rises and 0.025 no longer passes.
    assert pr.discover_verdict(res, proto(), 30).tolist() == [True, False, False]


# --- validate ---------------------------------------------------------------------


def val(edge, expectancy):
    return pd.DataFrame({"edge": [edge], "expectancy": [expectancy]})


def test_a_survivor_must_keep_its_sign_on_validate():
    assert pr.holds([0.05], val(0.05, 0.01), proto()).iloc[0]
    assert not pr.holds([-0.05], val(0.05, 0.01), proto()).iloc[0]


def test_a_survivor_must_clear_three_points_of_edge():
    assert not pr.holds([0.05], val(0.029, 0.01), proto()).iloc[0]


def test_a_survivor_must_have_positive_net_expectancy():
    assert not pr.holds([0.05], val(0.05, 0.0), proto()).iloc[0]


# --- every result -------------------------------------------------------------------


def test_an_implausible_hit_rate_is_flagged():
    assert one(gated(win=lambda s, d: d % 5 == 0))["suspicious"]
    assert not one(gated())["suspicious"]


def test_every_result_is_split_by_year_and_by_regime():
    r = one(
        gated(
            n=520,
            regime=lambda s, d: float(s % 2),
            win=lambda s, d: s % 2 == 1 if d % 5 == 0 else (s + d) % 2 == 0,
        )
    )
    regime = json.loads(r["by_regime"])
    assert set(regime) == {"0.0", "1.0"}
    assert regime["1.0"]["hit_rate"] == 1.0 and regime["0.0"]["hit_rate"] == 0.0
    assert set(json.loads(r["by_year"])) == {"2015", "2016"}


def test_walk_forward_purges_each_year_at_its_end():
    fp, rt, uni = gated(n=520, raw=True)
    wf = json.loads(pr.walk_forward(fp, rt, uni, [HAMMER], proto(), [2015])[0])
    rows = fp.values
    in_2015 = pd.to_datetime(rows["trade_date"]).dt.year == 2015
    known = pd.to_datetime(rt.values[f"known_on_{K}"]) < pd.Timestamp("2016-01-01")
    assert wf["2015"][0] == int((rows["hammer_shape"].eq(1) & in_2015 & known).sum())


def test_every_reported_result_carries_n_and_the_provisional_stamp():
    res = pr.evaluate(gated(), [HAMMER], proto(), "2015-01-01", "2015-12-31")
    res["survived"] = True
    lines = pr.report(
        res,
        "discover",
        7,
        proto(),
        {"net_provisional": True, "before": "2016-01-01"},
        "run",
    )
    assert "N = 7" in lines[0] and "NET PROVISIONAL" in lines[0]
    assert "passed discovery (BH q=0.1 over N = 7): 1" in lines[2]
    assert any(line.startswith("  [N=7] k3:hammer_shape") for line in lines)


def test_the_validate_report_gives_the_survival_count():
    res = pr.evaluate(gated(), [HAMMER], proto(), "2015-01-01", "2015-12-31")
    res["survived"], res["discover_edge"] = False, 0.1
    lines = pr.report(
        res,
        "validate",
        7,
        proto(),
        {"net_provisional": True, "before": "2017-01-01"},
        "run",
    )
    assert "discover survivors run: 1 | HELD on validate: 0" in lines[2]


@pytest.mark.parametrize("name", pr.LOG_COLUMNS)
def test_the_log_records_every_audit_field(name):
    assert name in (
        "run_id",
        "run_at",
        "protocol",
        "code",
        "build_id",
        "slice",
        "hypothesis",
        "n_raw",
        "n_declustered",
        "hit_rate",
        "base_rate",
        "edge",
        "expectancy",
        "p",
        "survived",
    )


# --- running a slice end to end (loaders pointed at the synthetic tables) ------


@pytest.fixture
def lab(tmp_path, monkeypatch):
    import yaml

    from vnstock_research.backtest import forward_returns as fr
    from vnstock_research.data import universe
    from vnstock_research.patterns import fingerprint as fpm

    fp, rt, uni = gated(
        n=520, win=lambda s, d: d % 5 == 0 or (s + d) % 2 == 0, raw=True
    )
    monkeypatch.setattr(fpm, "expected", lambda conn: (5, "fs"))
    monkeypatch.setattr(fpm, "load", lambda *a, **k: fp)
    monkeypatch.setattr(fr, "load", lambda *a, **k: rt)
    monkeypatch.setattr(universe, "tiers", lambda *a, **k: uni)
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(proto()))
    return SimpleNamespace(proto=path, log=tmp_path / "log.csv", out=tmp_path / "out")


def go(lab, name):
    return pr.run(None, name, log_path=lab.log, out=lab.out, proto_path=lab.proto)


def test_a_discover_run_logs_every_hypothesis_with_its_protocol(lab):
    d = go(lab, "discover")
    log = pr.read_log(lab.log)
    assert len(log) == 4 and set(log["slice"]) == {"discover"}
    assert set(log["protocol"]) == {pr.protocol_hash(proto())}
    assert "N = 4" in (d / "report.txt").read_text()


def test_validate_runs_only_the_discover_survivors(lab):
    go(lab, "discover")
    survivors = set(pr.read_log(lab.log).query("survived")["hypothesis"])
    assert survivors == {"k3:hammer_shape", "k3:hammer_shape+at_support"}
    go(lab, "validate")
    v = pr.read_log(lab.log).query("slice == 'validate'")
    assert set(v["hypothesis"]) == survivors


def test_validate_before_discover_is_refused(lab):
    fails_with(ValueError, "needs a discover run first", go, lab, "validate")


def test_a_run_after_the_registration_changed_is_refused(lab):
    import yaml

    go(lab, "discover")
    lab.proto.write_text(yaml.safe_dump(proto(fdr_q=0.2)))
    fails_with(ValueError, "changed after its first run", go, lab, "discover")


def test_an_addition_cannot_be_discovered_on_spent_data(lab):
    import yaml

    go(lab, "discover")
    p = proto()
    p["additions"] = [
        {"trigger": "doji", "conditions": [], "horizon": 5, "added_on": "2026-09-25"}
    ]
    lab.proto.write_text(yaml.safe_dump(p))
    fails_with(ValueError, "already spent", go, lab, "discover")
