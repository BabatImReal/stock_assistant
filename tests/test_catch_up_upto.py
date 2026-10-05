"""The catch-up must never put a restated symbol on a mixed price basis.

Pure-function tests: no database. Each fails if the matching rule is removed.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import catch_up_upto as cu  # noqa: E402


def series(**kw):
    return pd.Series(kw, dtype=float)


def _anchors(**kw):
    # symbol -> (anchor_day, stored factor)
    return pd.DataFrame(
        [{"symbol": k, "anchor_day": v[0], "stored": v[1]} for k, v in kw.items()]
    )


def _up(rows):
    return pd.DataFrame(rows, columns=["symbol", "trade_date", "factor"])


D = dt.date


def test_a_changed_factor_on_the_anchor_day_is_a_restatement():
    anchors = _anchors(AAA=(D(2026, 9, 21), 1.0), VPB=(D(2026, 9, 21), 1.0))
    up = _up([("AAA", D(2026, 9, 21), 1.0), ("VPB", D(2026, 9, 21), 0.7934)])
    assert list(cu.flag_restated(anchors, up).index) == ["VPB"]


def test_a_symbol_that_skipped_the_last_day_is_compared_on_its_own_last_day():
    # GLT did not trade on 09-21 (its last stored day is 09-18) but CafeF restated
    # it since. Comparing only on the database's last day never saw it.
    anchors = _anchors(GLT=(D(2026, 9, 18), 1.0))
    up = _up([("GLT", D(2026, 9, 18), 0.7576), ("GLT", D(2026, 9, 21), 1.0)])
    out = cu.flag_restated(anchors, up)
    assert list(out.index) == ["GLT"]
    assert out.loc["GLT", "anchor_day"] == D(2026, 9, 18)


def test_rounding_wobble_alone_is_not_a_restatement():
    anchors = _anchors(TPB=(D(2026, 9, 21), 0.839400))
    out = cu.flag_restated(anchors, _up([("TPB", D(2026, 9, 21), 0.839397)]))
    assert out.empty


def test_a_symbol_absent_from_the_new_file_on_its_anchor_is_not_flagged():
    out = cu.flag_restated(
        _anchors(OLD=(D(2026, 9, 21), 1.0)), _up([("NEW", D(2026, 9, 21), 0.5)])
    )
    assert out.empty


def test_no_step_yet_still_opens_a_window_the_day_after_the_last_bar():
    # restated, but it has not traded since the action: its NEXT bar is the seam
    f = pd.Series([0.8, 0.8], index=[D(2026, 9, 22), D(2026, 9, 23)])
    assert cu.event_date(f, 0.8) is None
    assert cu.event_or_next(f, 0.8) == D(2026, 9, 24)


def test_event_date_is_the_first_day_the_factor_leaves_the_base():
    f = pd.Series(
        [0.8, 0.8, 1.0, 1.0],
        index=[dt.date(2026, 9, d) for d in (22, 23, 24, 25)],
    )
    assert cu.event_date(f, 0.8) == dt.date(2026, 9, 24)
    assert cu.event_date(f.iloc[:2], 0.8) is None


def test_the_window_runs_before_and_well_past_the_event():
    ev = dt.date(2026, 9, 24)
    lo, hi = cu.exclusion_span(ev)
    assert lo <= ev < hi
    # reaches into the future: tomorrow's nightly bars would be the seam
    assert hi > dt.date(2026, 12, 1)


def _bars():
    d = [dt.date(2026, 9, x) for x in (22, 23, 24)]
    rows = []
    for day, f in zip(
        d, [0.8, 0.8, 1.0], strict=True
    ):  # VPB: action on 09-24, new-file factors
        rows.append({"symbol": "VPB", "trade_date": day, "factor": f})
    for day in d:
        rows.append({"symbol": "AAA", "trade_date": day, "factor": 1.0})
    return pd.DataFrame(rows)


def test_days_before_the_action_enter_on_the_old_basis():
    # stored 09-21 factor 1.0; new file says 0.8 on 09-21 (n = 0.8).
    new = _bars()
    ev = {"VPB": dt.date(2026, 9, 24)}
    out = cu.factors_to_insert(new, ev, series(VPB=1.0, AAA=1.0), series(VPB=0.8))
    vpb = out[out.symbol == "VPB"].set_index("trade_date")["factor"]
    assert list(vpb.index) == [dt.date(2026, 9, 22), dt.date(2026, 9, 23)]
    assert all(abs(v - 1.0) < 1e-9 for v in vpb)  # 1.0 * 0.8 / 0.8: old basis


def test_the_action_day_and_after_are_never_inserted():
    new = _bars()
    ev = {"VPB": dt.date(2026, 9, 24)}
    out = cu.factors_to_insert(new, ev, series(VPB=1.0), series(VPB=0.8))
    assert dt.date(2026, 9, 24) not in set(out[out.symbol == "VPB"]["trade_date"])


def test_unrestated_symbols_keep_every_day():
    new = _bars()
    out = cu.factors_to_insert(
        new, {"VPB": dt.date(2026, 9, 24)}, series(VPB=1.0), series(VPB=0.8)
    )
    assert len(out[out.symbol == "AAA"]) == 3


def test_the_window_starts_at_the_event_not_before():
    # days before the event are valid, spent history; blanking them was a bug
    ev = dt.date(2026, 9, 24)
    assert cu.exclusion_span(ev)[0] == ev


def test_rounding_wobble_before_an_action_is_not_the_event():
    # TPB's real pre-action factors wobbled in the 6th decimal; the action is the
    # day it steps to 1.0. A tolerance below the wobble puts the event on day one.
    f = pd.Series(
        [0.839404, 0.839397, 0.839403, 1.0],
        index=[dt.date(2026, 9, d) for d in (22, 23, 24, 25)],
    )
    assert cu.event_date(f, 0.839400) == dt.date(2026, 9, 25)


def test_index_rows_from_the_last_days_are_filled_not_only_those_after_the_last_bar():
    # 10-05 had stock bars but no index row yet; a later file must still fill it
    idx = pd.DataFrame(
        {
            "trade_date": [
                D(2026, 9, 1),
                D(2026, 10, 2),
                D(2026, 10, 5),
                D(2026, 10, 6),
            ],
            "symbol": ["VNINDEX"] * 4,
        }
    )
    out = cu.index_rows_to_fill(idx, D(2026, 10, 5))
    assert list(out["trade_date"]) == [D(2026, 10, 2), D(2026, 10, 5), D(2026, 10, 6)]
