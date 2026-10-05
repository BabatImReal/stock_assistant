"""The chart forward track's integrity rules. No database: pure functions only."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from vnstock_research import chart_forward as cf

CFG = {
    "frozen_on": "2026-10-05",
    "labels": {
        "double_top": "repeated_highs",
        "ascending_triangle": "ascending_triangle",
    },
}


def events(day="2026-10-06", state="confirmed_up", variant="double_top", sym="AAA"):
    return pd.DataFrame(
        [
            {
                "symbol": sym,
                "variant": variant,
                "episode_id": f"{sym}:2026-08-01:x",
                "state": state,
                "side": "up" if state == "confirmed_up" else "down",
                "signal_on": dt.date.fromisoformat(day),
                "boundary_at_signal": 10.5,
                "prior_trend": "other",
            }
        ]
    )


def test_the_frozen_date_itself_is_not_a_forward_day():
    assert not cf.is_forward("2026-10-05", CFG)
    assert cf.is_forward("2026-10-06", CFG)


def test_only_confirmed_breaks_on_the_day_become_rows_with_the_registered_label():
    ev = pd.concat([events(), events(state="expired"), events(day="2026-10-07")])
    rows = cf.event_rows(ev, "2026-10-06", {"AAA": 2}, CFG, "reg")
    assert len(rows) == 1
    assert rows[0]["label"] == "repeated_highs"  # label only; population unchanged
    assert rows[0]["tier"] == "2" and rows[0]["registration"] == "reg"


def test_a_day_is_written_once_and_a_repeat_is_idempotent(tmp_path):
    p = tmp_path / "log.csv"
    rows = cf.event_rows(events(), "2026-10-06", {"AAA": 2}, CFG, "reg")
    assert cf.append_day("2026-10-06", rows, p, CFG, "reg") == "new"
    assert cf.append_day("2026-10-06", rows, p, CFG, "reg") == "same"
    assert len(cf.read(p)) == 1


def test_a_different_answer_for_a_recorded_day_is_refused(tmp_path):
    p = tmp_path / "log.csv"
    cf.append_day(
        "2026-10-06",
        cf.event_rows(events(), "2026-10-06", {}, CFG, "reg"),
        p,
        CFG,
        "reg",
    )
    other = cf.event_rows(events(sym="BBB"), "2026-10-06", {}, CFG, "reg")
    with pytest.raises(ValueError, match="append-only"):
        cf.append_day("2026-10-06", other, p, CFG, "reg")


def test_a_quiet_day_is_recorded_so_a_missed_day_is_distinguishable(tmp_path):
    p = tmp_path / "log.csv"
    assert cf.append_day("2026-10-06", [], p, CFG, "reg") == "new"
    log = cf.read(p)
    assert list(log["day"]) == ["2026-10-06"] and list(log["symbol"]) == [""]


def test_nothing_on_or_before_the_freeze_date_can_be_recorded(tmp_path):
    with pytest.raises(ValueError, match="not a forward day"):
        cf.append_day("2026-10-05", [], tmp_path / "l.csv", CFG, "reg")


def test_a_changed_registration_refuses_to_extend_the_log(tmp_path):
    p = tmp_path / "log.csv"
    cf.append_day("2026-10-06", [], p, CFG, "regA")
    with pytest.raises(ValueError, match="changed"):
        cf.append_day("2026-10-07", [], p, CFG, "regB")


def test_the_pinned_detector_is_the_one_that_is_installed():
    cf.check_detector()  # raises if v2's rules or code no longer match the freeze


def test_the_registration_file_matches_its_recorded_hash_format():
    assert len(cf.registration_hash()) == 16


def test_the_comparator_is_the_same_signal_day_not_a_global_mean():
    ev = pd.DataFrame(
        {
            "symbol": ["A", "B"],
            "side": ["up", "up"],
            "signal_on": pd.to_datetime(["2026-10-06", "2026-10-07"]),
            "net": [0.10, 0.10],
        }
    )
    comp = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-10-06"] * 2 + ["2026-10-07"] * 2),
            "net": [0.00, 0.00, 0.08, 0.08],
        }
    )
    t = cf.excess_table(ev, comp)
    assert list(np.round(t["excess"], 4)) == [
        0.10,
        0.02,
    ]  # a bull day gives less credit


def test_clustering_widens_the_se_when_events_share_a_day():
    x = pd.Series([0.05, 0.05, 0.05, 0.05, -0.01, -0.01, -0.01, -0.01])
    spread = cf.cluster_stats(x, pd.Series(range(8), index=x.index))
    same_day = cf.cluster_stats(x, pd.Series([0] * 4 + [1] * 4, index=x.index))
    assert same_day["se"] > spread["se"]
    assert spread["mean"] == pytest.approx(0.02)


def test_an_empty_sample_is_reported_as_empty_not_as_a_result():
    st = cf.cluster_stats(pd.Series([], dtype=float), pd.Series([], dtype=str))
    assert st["n"] == 0 and np.isnan(st["mean"])


def test_missed_forward_days_are_found_and_pre_freeze_days_never_are():
    log = pd.DataFrame({"day": ["2026-10-06"]})
    days = [
        dt.date(2026, 10, 5),
        dt.date(2026, 10, 6),
        dt.date(2026, 10, 7),
        dt.date(2026, 10, 8),
    ]
    assert cf.missing_days(days, log, CFG) == ["2026-10-07", "2026-10-08"]
    assert cf.missing_days(days, pd.DataFrame(columns=["day"]), CFG)[0] == "2026-10-06"


def test_no_p_value_is_shown_below_the_first_registered_look():
    looks = [60, 120, 240]
    assert "not shown" in cf.p_display(0.0, 8, looks)
    assert cf.p_display(0.0123, 60, looks) == "0.012"
