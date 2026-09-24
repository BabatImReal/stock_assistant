"""Tests for the daily scan (report/scan.py) and the paper-trading ledger
(report/paper.py). One test per rule; each fails if its rule is removed.
Synthetic rows only: no database, no real ledger."""

import copy

import numpy as np
import pandas as pd

from vnstock_research.backtest.protocol import Hypothesis, load_protocol
from vnstock_research.report import paper, scan

from ._helpers import fails_with

PROTO = load_protocol()
SPEC = PROTO["daily_scan"]
BREAKOUT = Hypothesis("breakout", ("volume_dry",), 3)
MARUBOZU = Hypothesis("marubozu_red", ("ma_50_rising", "rvol_high"), 5)
VAL = {BREAKOUT.id: 0.015, MARUBOZU.id: 0.010}


# --- the registered blocks say what Ben set ------------------------------


def test_the_registered_blocks_are_bens():
    assert [(t["key"], t["prefer"]) for t in SPEC["tie_breaker"]] == [
        ("validate_expectancy", "highest"),
        ("traded_value_20d", "highest"),
        ("tier", "most_liquid"),
        ("symbol", "alphabetical"),
    ]
    assert SPEC["traded_value_sessions"] == 20
    v = PROTO["paper_trading"]["verdict"]
    assert (v["min_signal_days"], v["min_span_months"]) == (30, 3)
    assert v["pass"] == {
        "cumulative_above": 0.0,
        "drawdown_at_least": -1.0,
        "positive_months": "majority",
    }
    assert v["fail"] == {"cumulative_at_most": 0.0, "drawdown_below": -1.5}
    assert PROTO["paper_trading"]["frozen_on"] == "2026-09-24"


# --- the accepted set ----------------------------------------------------------


def log_rows():
    def run(slice_name, run_id, rows):
        return [
            {
                "slice": slice_name,
                "run_id": run_id,
                "hypothesis": h,
                "survived": s,
                "expectancy": 0.01,
            }
            for h, s in rows
        ]

    a, b = BREAKOUT.id, MARUBOZU.id
    c = "k3:doji"
    return pd.DataFrame(
        run("validate", "v1", [(a, True), (b, True), (c, True)])
        # An older holdout run that accepted c: only the LATEST run counts.
        + run("holdout", "h0", [(a, False), (b, False), (c, True)])
        + run("holdout", "h1", [(a, True), (b, False), (c, False)])
    )


def test_only_the_latest_holdouts_accepts_are_traded():
    assert [h.id for h in scan.accepted(PROTO, log_rows())] == [BREAKOUT.id]


# --- candidates ----------------------------------------------------------------


def rows(**over):
    """Two liquid stocks where both signals fire."""
    base = {
        "symbol": ["AAA", "BBB"],
        "trade_date": [pd.Timestamp("2026-10-01").date()] * 2,
        "breakout": [1.0, 0.0],
        "volume_dry_up": [1.0, 0.0],
        "marubozu_red": [0.0, 1.0],
        "ma_50_slope": [0.1, 0.1],
        "rvol": [1.0, 2.0],
        "tier": [3.0, 3.0],
    }
    base.update(over)
    return pd.DataFrame(base)


EX = pd.DataFrame(
    {
        "symbol": ["AAA", "BBB"],
        "exchange": ["HOSE", "HOSE"],
        "exchange_unknown": [False, False],
    }
)
TV = pd.Series({"AAA": 100.0, "BBB": 200.0})


def cands(r=None, ex=EX, tv=TV):
    return scan.candidates(
        r if r is not None else rows(), [BREAKOUT, MARUBOZU], PROTO, VAL, tv, ex
    )


def test_a_signal_fires_only_when_every_condition_is_known_and_true():
    c = cands(rows(volume_dry_up=[np.nan, 0.0]))
    assert c["hypothesis"].tolist() == [MARUBOZU.id]


def test_a_stock_not_liquid_on_t_is_not_eligible():
    c = cands(rows(tier=[np.nan, 3.0])).set_index("symbol")
    assert not c.loc["AAA", "eligible"] and c.loc["AAA", "why"] == "not liquid on T"


def test_a_upcom_stock_is_not_eligible():
    ex = EX.assign(exchange=["UPCOM", "HOSE"])
    c = cands(ex=ex).set_index("symbol")
    assert not c.loc["AAA", "eligible"] and "UPCoM" in c.loc["AAA", "why"]


def test_an_undated_exchange_is_not_eligible():
    ex = EX.assign(exchange_unknown=[True, False])
    c = cands(ex=ex).set_index("symbol")
    assert not c.loc["AAA", "eligible"] and "not dated" in c.loc["AAA", "why"]


def test_an_unknown_exchange_counts_as_undated():
    c = cands(ex=EX[EX["symbol"] == "BBB"]).set_index("symbol")
    assert not c.loc["AAA", "eligible"]


def test_nothing_fired_is_nothing_strong():
    c = cands(rows(breakout=[0.0, 0.0], marubozu_red=[0.0, 0.0]))
    assert c.empty and scan.rank(c, SPEC).empty


# --- the tie-breaker, in the registered order -----------------------------------


def ranked(frame):
    return scan.rank(frame.assign(eligible=True, why=None), SPEC)["symbol"].tolist()


def frame(**cols):
    n = len(cols["symbol"])
    base = {
        "validate_expectancy": [0.01] * n,
        "traded_value_20d": [100.0] * n,
        "tier": [3] * n,
        "hypothesis": ["h"] * n,
    }
    return pd.DataFrame({**base, **cols})


def test_the_validate_expectancy_ranks_first():
    f = frame(
        symbol=["AAA", "BBB"],
        validate_expectancy=[0.02, 0.01],
        traded_value_20d=[1.0, 999.0],
    )
    assert ranked(f)[0] == "AAA"


def test_then_the_higher_traded_value():
    f = frame(symbol=["AAA", "BBB"], traded_value_20d=[100.0, 200.0], tier=[3, 1])
    assert ranked(f)[0] == "BBB"


def test_then_the_more_liquid_tier():
    f = frame(symbol=["AAA", "BBB"], tier=[1, 3])
    assert ranked(f)[0] == "BBB"


def test_then_the_symbol_alphabetically():
    f = frame(symbol=["BBB", "AAA"])
    assert ranked(f)[0] == "AAA"


def test_an_unknown_traded_value_ranks_last():
    f = frame(symbol=["AAA", "BBB"], traded_value_20d=[np.nan, 1.0])
    assert ranked(f)[0] == "BBB"


def test_the_order_is_the_registered_one():
    spec = copy.deepcopy(SPEC)
    spec["tie_breaker"] = [spec["tie_breaker"][3], *spec["tie_breaker"][:3]]
    f = frame(symbol=["BBB", "AAA"], validate_expectancy=[0.02, 0.01])
    assert scan.rank(f.assign(eligible=True, why=None), spec)["symbol"][0] == "AAA"


def test_traded_value_reads_nothing_after_t_and_needs_20_sessions():
    days = pd.bdate_range("2026-09-01", periods=25).date
    v = pd.DataFrame(
        {"symbol": "AAA", "trade_date": days, "traded_value": [1.0] * 20 + [1000.0] * 5}
    )
    v = pd.concat(
        [
            v,
            pd.DataFrame(
                {"symbol": "BBB", "trade_date": days[:10], "traded_value": 5.0}
            ),
        ]
    )
    tv = scan.traded_value_20d(v, days[19], 20)
    assert tv["AAA"] == 1.0 and np.isnan(tv["BBB"])


# --- the ledger ----------------------------------------------------------------


def pick_for(day, symbol="AAA", hypothesis=BREAKOUT.id):
    c = pd.DataFrame(
        [
            {
                "symbol": symbol,
                "hypothesis": hypothesis,
                "family": hypothesis,
                "k": 3,
                "tier": 3,
                "validate_expectancy": 0.015,
                "traded_value_20d": 100.0,
                "eligible": True,
            }
        ]
    )
    return scan.Pick(
        day=day,
        proposal=None if symbol is None else c.iloc[0],
        ranked=c if symbol else c.iloc[:0],
        candidates=c,
        liquid=280,
        regime={},
        build_id=5,
        featureset="fs",
        fp_code="code",
    )


def test_a_day_is_recorded_once(tmp_path):
    path = tmp_path / "ledger.csv"
    paper.record(pick_for("2026-10-01"), PROTO, log_rows(), path)
    paper.record(pick_for("2026-10-01"), PROTO, log_rows(), path)
    assert len(paper.read(path)) == 1


def test_a_recorded_day_is_never_rewritten(tmp_path):
    path = tmp_path / "ledger.csv"
    paper.record(pick_for("2026-10-01"), PROTO, log_rows(), path)
    fails_with(
        ValueError,
        "append-only",
        paper.record,
        pick_for("2026-10-01", symbol="BBB"),
        PROTO,
        log_rows(),
        path,
    )


def test_a_nothing_day_re_runs_cleanly(tmp_path):
    path = tmp_path / "ledger.csv"
    paper.record(pick_for("2026-10-01", symbol=None), PROTO, log_rows(), path)
    try:
        row = paper.record(pick_for("2026-10-01", symbol=None), PROTO, log_rows(), path)
    except ValueError as e:
        raise AssertionError(f"a nothing day's re-run was refused: {e}") from None
    assert row["outcome"] == "nothing" and len(paper.read(path)) == 1


def test_every_row_carries_what_made_it(tmp_path):
    row = paper.record(pick_for("2026-10-01"), PROTO, log_rows(), tmp_path / "l.csv")
    assert row["holdout_run"] == "h1" and row["build_id"] == 5
    for col in ("scan", "paper", "protocol", "featureset", "fp_code", "code"):
        assert row[col], col


def test_a_changed_scan_block_is_refused(tmp_path):
    path = tmp_path / "ledger.csv"
    paper.record(pick_for("2026-10-01"), PROTO, log_rows(), path)
    changed = copy.deepcopy(PROTO)
    changed["daily_scan"]["traded_value_sessions"] = 10
    fails_with(
        ValueError,
        "daily_scan",
        paper.record,
        pick_for("2026-10-02"),
        changed,
        log_rows(),
        path,
    )


def test_a_changed_paper_block_is_refused(tmp_path):
    path = tmp_path / "ledger.csv"
    paper.record(pick_for("2026-10-01"), PROTO, log_rows(), path)
    changed = copy.deepcopy(PROTO)
    changed["paper_trading"]["verdict"]["min_signal_days"] = 10
    fails_with(
        ValueError,
        "paper_trading",
        paper.record,
        pick_for("2026-10-02"),
        changed,
        log_rows(),
        path,
    )


def test_the_forward_record_starts_after_the_freeze_date():
    assert not paper.is_forward("2026-09-24", PROTO)
    assert paper.is_forward("2026-09-25", PROTO)


# --- scoring, per signal day ---------------------------------------------------

CAL = list(pd.bdate_range("2026-09-01", "2027-06-30").date)


def ledger(days, k=3, forward=True, symbol="AAA"):
    return pd.DataFrame(
        {
            "day": [str(d) for d in days],
            "forward": forward,
            "outcome": "proposal",
            "symbol": symbol,
            "hypothesis": BREAKOUT.id,
            "family": "fam",
            "k": k,
        }
    )


def returns(days, net3, net5=None, reason=None, known=None, symbol="AAA"):
    n = len(days)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": list(days),
            "net_3": net3,
            "net_5": net5 if net5 is not None else [np.nan] * n,
            "reason_3": reason if reason is not None else [None] * n,
            "reason_5": [None] * n,
            "known_on_3": known if known is not None else [None] * n,
            "known_on_5": [None] * n,
        }
    )


def test_a_proposal_is_scored_at_its_own_k():
    d = [CAL[30]]
    o = paper.outcomes(ledger(d, k=5), returns(d, [0.5], [0.02]), CAL)
    assert o["net"].tolist() == [0.02]


def test_an_unresolved_outcome_is_pending():
    d = [CAL[30]]
    o = paper.outcomes(ledger(d), returns(d, [np.nan], reason=["pending"]), CAL)
    assert o["status"].tolist() == ["pending"]


def test_no_trade_at_entry_is_void_and_a_stuck_stake_is_stuck():
    d = [CAL[30], CAL[31]]
    rt = returns(
        d,
        [np.nan, np.nan],
        reason=["entry_at_ceiling", "window_gap"],
        known=[CAL[31], CAL[33]],
    )
    o = paper.outcomes(ledger(d), rt, CAL)
    assert o["status"].tolist() == ["void", "stuck"]


def record(nets, start=40, forward=True):
    days = CAL[start : start + len(nets)]
    return paper.outcomes(ledger(days, forward=forward), returns(days, nets), CAL)


def spread(nets, step=3):
    """One signal day every `step` sessions, so 30 days span > 3 months."""
    days = CAL[40::step][: len(nets)]
    return paper.outcomes(ledger(days), returns(days, nets), CAL)


def test_the_record_is_per_signal_day_in_stakes():
    sm = paper.summary(record([0.10, -0.30, 0.05, 0.0]))
    assert sm["signal_days"] == 4
    assert np.isclose(sm["cumulative"], -0.15)
    assert np.isclose(sm["drawdown"], -0.30)
    assert sm["hit_rate"] == 0.5  # 0.0 is not a hit


def test_before_the_freeze_is_not_the_forward_record():
    led = pd.concat([ledger(CAL[40:43]), ledger(CAL[10:12], forward=False)])
    rt = pd.concat([returns(CAL[40:43], [0.1] * 3), returns(CAL[10:12], [-0.5] * 2)])
    s = paper.score(led, rt, CAL, PROTO, fee_provisional=False)
    assert s.forward["signal_days"] == 3 and s.before["signal_days"] == 2


RULE = PROTO["paper_trading"]


def verdict(nets, fee_provisional=False, step=3, o=None):
    o = spread(nets, step) if o is None else o
    return paper.verdict(paper.summary(o), RULE, fee_provisional)


def good(n=30):
    return [0.02] * n


def test_no_verdict_before_30_signal_days():
    assert verdict(good(29)).startswith("NO VERDICT")


def test_no_verdict_before_three_months():
    assert verdict(good(30), step=1).startswith("NO VERDICT")  # 30 sessions


def test_a_good_record_passes():
    assert verdict(good()) == "PASS"


def test_a_record_at_zero_fails():
    nets = [0.25, -0.25] * 15  # exactly 0 stakes, drawdown only -0.25
    assert verdict(nets) == "FAIL"


def test_a_deep_drawdown_fails_even_when_positive():
    nets = [0.2] * 10 + [-0.16] * 10 + [0.2] * 10  # cumulative +2.4, dd -1.6
    assert verdict(nets) == "FAIL"


def test_a_drawdown_between_the_bars_stays_provisional():
    nets = [0.2] * 10 + [-0.12] * 10 + [0.2] * 10  # cumulative +2.8, dd -1.2
    assert verdict(nets) == "PROVISIONAL"


def test_half_the_months_positive_is_not_a_majority():
    # 4 months of signal days; two net positive, two slightly negative.
    days = [
        d
        for m in ("2026-11", "2026-12", "2027-01", "2027-02")
        for d in pd.bdate_range(f"{m}-02", periods=8).date
    ]
    nets = [0.1] * 8 + [-0.01] * 8 + [0.1] * 8 + [-0.01] * 8
    o = paper.outcomes(ledger(days), returns(days, nets), CAL)
    assert paper.summary(o)["months"] == 4
    assert verdict(None, o=o) == "PROVISIONAL"


def test_no_pass_or_fail_is_declared_on_a_provisional_fee():
    assert verdict(good(), fee_provisional=True).startswith(
        "would be PASS, NOT DECLARED"
    )


def test_a_stuck_stake_withholds_the_verdict():
    days = CAL[40::3][:31]
    nets = [0.02] * 30 + [np.nan]
    rt = returns(
        days,
        nets,
        reason=[None] * 30 + ["window_gap"],
        known=[None] * 30 + [CAL[40 + 90 + 5]],
    )
    o = paper.outcomes(ledger(days), rt, CAL)
    assert verdict(None, o=o).startswith("WITHHELD")
