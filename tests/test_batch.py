"""Tests for new-hypothesis batches (backtest/batch.py). One test per rule;
each fails if its rule is removed. Synthetic tables only: nothing here runs a
slice or writes the real logs."""

import copy
import dataclasses

import pandas as pd

from vnstock_research.backtest import batch, neighbours, protocol
from vnstock_research.backtest.forward_returns import Returns
from vnstock_research.report.scan import block_hash

from ._helpers import fails_with

PROTO = protocol.load_protocol()
NAME = "complements_1"
BLOCK = PROTO["batches"][NAME]


# --- the rule that defines the batch -----------------------------------------


def test_each_condition_gets_its_exact_complement():
    assert batch.complement({"rvol": ">=1.5"}) == {"rvol": "<1.5"}
    assert batch.complement({"price_vs_ma_50": ">0"}) == {"price_vs_ma_50": "<=0"}
    assert batch.complement({"x": "<=2"}) == {"x": ">2"}
    assert batch.complement({"x": "<2"}) == {"x": ">=2"}
    assert batch.complement({"near_support": 1}) == {"near_support": "!=1"}


def test_the_batch_is_exactly_its_rule():
    hyps = batch.enumerate_batch(PROTO, NAME)
    reg = PROTO["registered"]
    assert len(hyps) == BLOCK["n"] == len(reg["triggers"]) * 92 * len(reg["horizons"])
    for h in hyps:
        assert 1 <= len(h.conditions) <= BLOCK["max_conditions"]
        assert any(c.startswith("not_") for c in h.conditions), h.id
        assert not any(f"not_{c}" in h.conditions for c in h.conditions), h.id
    assert len({h.id for h in hyps}) == len(hyps)


def test_no_batch_id_was_registered_before():
    registered = {h.id for h in protocol.vocabulary(PROTO)}
    assert not registered & {h.id for h in batch.batch_vocabulary(PROTO, NAME)}


def test_a_count_other_than_the_registered_n_is_refused():
    p = copy.deepcopy(PROTO)
    p["batches"][NAME]["n"] = 3863
    fails_with(ValueError, "registered n", batch.batch_vocabulary, p, NAME)


def test_a_registered_id_in_a_batch_is_refused(monkeypatch):
    real = batch.enumerate_batch(PROTO, NAME)
    old = protocol.vocabulary(PROTO)[0]
    clash = batch.BatchHypothesis(old.trigger, old.conditions, old.k, ())
    monkeypatch.setattr(batch, "enumerate_batch", lambda p, n: [*real[:-1], clash])
    fails_with(ValueError, "reuses registered ids", batch.batch_vocabulary, PROTO, NAME)


def test_adding_a_batch_leaves_the_registered_blocks_alone():
    assert protocol.protocol_hash(PROTO) == "0106fab4dc2f35a2"
    assert neighbours.neighbours_hash(PROTO) == "fbc042f4080bf942"
    assert block_hash(PROTO["daily_scan"]) == "a5be2561c39c60af"


# --- the batch log --------------------------------------------------------------


def log(rows):
    return pd.DataFrame(rows, columns=batch.BATCH_COLUMNS)


def row(
    name=NAME,
    slice_name="discover",
    hyp="k3:doji+not_rvol_high",
    survived=True,
    hash_=None,
    edge=0.05,
):
    return {
        "batch": name,
        "slice": slice_name,
        "hypothesis": hyp,
        "survived": survived,
        "protocol": hash_ or batch.batch_hash(BLOCK),
        "edge": edge,
    }


def test_a_changed_batch_block_is_refused():
    fails_with(
        ValueError,
        "changed after its first run",
        batch.check_frozen,
        PROTO,
        NAME,
        log([row(hash_="0000000000000000")]),
    )


def test_each_slice_runs_once_per_batch():
    fails_with(
        ValueError,
        "already run on discover",
        batch.check_once,
        log([row()]),
        NAME,
        "discover",
    )


def test_another_batchs_run_does_not_spend_this_one():
    try:
        batch.check_once(log([row(name="other")]), NAME, "discover")
    except ValueError as e:
        raise AssertionError(f"refused on another batch's run: {e}") from None


def test_validate_runs_only_this_batchs_discover_survivors():
    hyps = batch.batch_vocabulary(PROTO, NAME)
    a, b = hyps[0].id, hyps[1].id
    lg = log(
        [row(hyp=a), row(hyp=b, survived=False), row(name="other", hyp=hyps[2].id)]
    )
    assert [h.id for h in batch.discover_survivors(lg, NAME, hyps)] == [a]


def test_validate_needs_this_batchs_discover_first():
    fails_with(
        ValueError,
        "discover run first",
        batch.discover_survivors,
        log([row(name="other")]),
        NAME,
        [],
    )


def test_a_run_is_logged_with_the_batch_and_its_hash(tmp_path):
    res = pd.DataFrame([{c: 0 for c in batch.BATCH_COLUMNS}])
    path = tmp_path / "b.csv"
    batch.append(res, NAME, "discover", PROTO, 5, path)
    got = pd.read_csv(path).iloc[0]
    assert got["batch"] == NAME and got["protocol"] == batch.batch_hash(BLOCK)
    assert got["slice"] == "discover" and got["build_id"] == 5


def test_the_holdout_is_never_run_for_a_batch():
    fails_with(ValueError, "holdout is spent", batch.run, None, NAME, "holdout")


# --- the statistics and verdicts ----------------------------------------------


def test_every_statistic_is_gross():
    values = pd.DataFrame(
        {"ret_3": [0.02], "net_3": [-0.01], "ret_5": [0.03], "net_5": [0.0]}
    )
    g = batch.gross(Returns(values, {"horizons": [3, 5]}))
    assert g.values["net_3"].tolist() == [0.02] and g.values["net_5"].tolist() == [0.03]


def res(**cols):
    n = len(cols["p"])
    base = {
        "edge": [0.05] * n,
        "testable": [True] * n,
        "gross": [0.01] * n,
        "net_expectancy": [0.0] * n,
        "hypothesis": [f"h{i}" for i in range(n)],
    }
    return pd.DataFrame({**base, **cols})


def test_discovery_uses_bh_over_the_batchs_n():
    # 0.001 passes BH among 1 test but not among the registered 3,864.
    assert not batch.discover_verdict(res(p=[0.001]), BLOCK).iloc[0]
    assert batch.discover_verdict(res(p=[1e-6]), BLOCK).iloc[0]


def test_discovery_needs_the_edge_magnitude():
    assert not batch.discover_verdict(res(p=[1e-6], edge=[0.02]), BLOCK).iloc[0]


def test_discovery_is_two_sided():
    assert batch.discover_verdict(res(p=[1e-6], edge=[-0.05]), BLOCK).iloc[0]


def test_discovery_needs_testable():
    assert not batch.discover_verdict(res(p=[1e-6], testable=[False]), BLOCK).iloc[0]


def test_validate_keeps_the_discover_sign():
    v = res(p=[0.5], edge=[-0.04])
    assert not batch.holds([0.05], v, BLOCK).iloc[0]


def test_validate_is_on_gross_not_net_and_has_no_edge_floor():
    v = res(p=[0.5], edge=[0.01], gross=[0.004], net_expectancy=[-0.002])
    assert batch.holds([0.05], v, BLOCK).iloc[0]
    assert not batch.holds([0.05], res(p=[0.5], gross=[0.0]), BLOCK).iloc[0]


def test_only_a_positive_edge_is_a_paper_trading_candidate():
    v = res(p=[0.5, 0.5], edge=[0.04, -0.04]).assign(survived=[True, True])
    assert batch.candidates(v)["edge"].tolist() == [0.04]


WF_GOOD = '{"2012": [50, 0.05], "2013": [50, 0.04], "2014": [50, 0.03]}'
WF_TWO = '{"2012": [50, 0.05], "2013": [50, -0.04], "2014": [50, 0.03]}'


def six():
    return pd.DataFrame(
        {
            "edge": [0.06, 0.03],
            "gross": [0.008, 0.004],
            "walk_forward": [WF_TWO, WF_TWO],
        }
    )


def cand(edge=0.08, gross=0.01, wf=WF_GOOD):
    return pd.DataFrame({"edge": [edge], "gross": [gross], "walk_forward": [wf]})


def test_stronger_needs_a_higher_edge_than_the_best_six():
    assert batch.stronger(cand(), six()).iloc[0]
    assert not batch.stronger(cand(edge=0.05), six()).iloc[0]


def test_stronger_needs_a_higher_gross_than_the_best_six():
    assert not batch.stronger(cand(gross=0.007), six()).iloc[0]


def test_stronger_needs_as_many_years_positive():
    wf_one = '{"2012": [50, 0.05], "2013": [50, -0.04], "2014": [50, -0.03]}'
    assert not batch.stronger(cand(wf=wf_one), six()).iloc[0]


def test_years_positive_counts_positive_years_only():
    assert batch.years_positive(WF_TWO) == 2
    assert batch.years_positive('{"2012": [0, NaN]}') == 0


def test_gross_keeps_the_returns_manifest():
    rt = Returns(pd.DataFrame({"ret_3": [0.1], "net_3": [0.0]}), {"horizons": [3]})
    assert dataclasses.asdict(batch.gross(rt))["manifest"] == {"horizons": [3]}
