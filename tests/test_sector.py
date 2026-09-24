"""Tests for sector (doc §5.4): membership, the (date, sector) frame, the
measures, the join, and the current-label HARD GATE.

One test per rule; each fails if its rule is removed.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.data import sectors
from vnstock_research.features import (
    FeatureSet,
    compute,
    compute_sector,
    quarantine_flagged,
)
from vnstock_research.features.base import FLAG
from vnstock_research.features.sector import SectorInput, build_frame

from ._helpers import fails_with, frame
from .test_universe import calendar, rows

SECT = {
    "sector_change_20d": {
        "enabled": True,
        "window_days": 20,
        "min_members": 5,
        "min_count_share": 0.8,
        "count_median_sessions": 20,
    }
}
VS = {"stock_vs_sector_20d": {"enabled": True, "window_days": 20}}
LOOKBACK = 19 + 21  # window_days - 1 + count_median_sessions + 1


def labels(entries):
    """entries: (symbol, sector, snapshot_date)."""
    df = pd.DataFrame(entries, columns=["symbol", "sector", "snapshot_date"])
    df["sector_name"] = df["sector"]
    return df


def sector_frame(n=120, returns=None, counted=10, current_until=0):
    """A synthetic (date, sector) frame. returns: sector -> daily median return."""
    cal = calendar(n)
    parts = []
    for sec, r in (returns or {"8300": 0.01}).items():
        parts.append(
            pd.DataFrame(
                {
                    "trade_date": cal,
                    "sector": sec,
                    "counted": counted,
                    "median_return": r,
                    "labels_current": [i < current_until for i in range(n)],
                    "gap_before": 0,
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def one_sector(out, sec="8300"):
    return out[out["sector"] == sec].reset_index(drop=True)


# --- membership (data/sectors.py) ----------------------------------------


def test_steel_is_split_out_of_basic_resources_and_nothing_else_is():
    """The ONE manual exception. Everything else is plain ICB level 2."""
    l2 = pd.Series(["1700", "1700", "8300", "8700"])
    l4 = pd.Series(["1757", "1737", "8355", "8777"])
    assert sectors.sector_id(l2, l4).tolist() == ["1757", "1700", "8300", "8700"]


def test_a_date_uses_the_latest_snapshot_on_or_before_it():
    cal = calendar(30)
    lab = labels([("AAA", "8300", cal[10]), ("AAA", "8700", cal[20])])
    sector, current = sectors.panel(lab, cal)
    assert sector["AAA"].tolist() == ["8300"] * 20 + ["8700"] * 10
    # Before the first snapshot the label is BORROWED: flagged.
    assert current["AAA"].tolist() == [True] * 10 + [False] * 20


def test_pooling_groups_use_the_latest_snapshot():
    cal = calendar(3)
    lab = labels([("AAA", "8300", cal[0]), ("AAA", "8700", cal[2])])
    assert sectors.current_groups(lab)["AAA"] == "8700"


# --- the (date, sector) frame --------------------------------------------


def member(cal, symbol, adj, **kw):
    r = rows(cal, symbol, **kw)
    r["adj_close"] = adj
    return r


def two_day_frame(members, snapshot=None):
    cal = calendar(2)
    df = pd.concat([m(cal) for m in members], ignore_index=True)
    lab = labels([(s, "8300", snapshot or cal[0]) for s in df["symbol"].unique()])
    return build_frame(df, cal, lab).iloc[-1]


def test_sector_return_is_the_equal_weighted_median():
    """+1%, +2%, +30%: the median is 2%. A mean (11%) would let one thin
    limit-up stock move the whole sector."""
    day = two_day_frame(
        [
            lambda c: member(c, "AAA", [100.0, 101.0]),
            lambda c: member(c, "BBB", [100.0, 102.0]),
            lambda c: member(c, "CCC", [100.0, 130.0]),
        ]
    )
    assert day["median_return"] == pytest.approx(0.02)
    assert day["counted"] == 3


def test_direction_uses_the_adjusted_close():
    # Ex-dividend: the raw close drops, the adjusted close is flat.
    def exdiv(c):
        r = member(c, "DIV", [9.0, 9.0])
        r["close"] = [10.0, 9.0]
        return r

    assert two_day_frame([exdiv])["median_return"] == 0.0


def test_every_tradeable_member_counts_not_only_liquid_ones():
    day = two_day_frame([lambda c: member(c, "THN", [10.0, 11.0], volume=1.0)])
    assert day["counted"] == 1


def test_a_member_back_from_a_suspension_is_not_counted_that_day():
    cal = calendar(4)
    df = member(cal, "SUS", [10.0, 20.0], days=[0, 3])
    f = build_frame(df, cal, labels([("SUS", "8300", cal[0])]))
    assert f["counted"].tolist() == [0, 0, 0, 0]


def test_the_frame_flags_days_resting_on_borrowed_labels():
    cal = calendar(4)
    df = member(cal, "AAA", [10.0, 11.0, 12.0, 13.0])
    f = build_frame(df, cal, labels([("AAA", "8300", cal[2])]))
    # Day 0: nothing counted, fail-safe flagged. Day 1: borrowed label.
    assert f["labels_current"].tolist() == [True, True, False, False]


# --- the sector measure --------------------------------------------------


def test_sector_change_compounds_the_daily_medians():
    out, _ = compute_sector(sector_frame(), SECT)
    assert one_sector(out)["sector_change_20d"].iloc[-1] == pytest.approx(1.01**20 - 1)


def test_a_sector_day_with_too_few_members_is_blanked():
    counted = [10] * 120
    counted[80] = 4  # below min_members
    out, _ = compute_sector(sector_frame(counted=counted), SECT)
    col = one_sector(out)["sector_change_20d"]
    assert col.iloc[80:100].isna().all()  # every window containing it
    assert not np.isnan(col.iloc[100])
    # A steady four members passes the relative guard (no drop) but never the
    # floor: a median of four stocks is not a sector.
    steady, _ = compute_sector(sector_frame(counted=4), SECT)
    assert one_sector(steady)["sector_change_20d"].isna().all()
    # A lost exchange file halves a big sector (20 -> 10): still above the
    # floor, but a drop against its own trailing median, so blanked too.
    halved = [20] * 120
    halved[80] = 10
    out, _ = compute_sector(sector_frame(counted=halved), SECT)
    assert one_sector(out)["sector_change_20d"].iloc[80:100].isna().all()


def test_sector_change_reads_nothing_older_than_its_declared_lookback():
    i = 110
    f = sector_frame()
    base, _ = compute_sector(f, SECT)
    moved = f.copy()
    # Every row outside the window, and hugely (a median absorbs one outlier).
    moved.loc[moved.index[: i - LOOKBACK], ["counted", "median_return"]] = [10_000, 0.5]
    after, _ = compute_sector(moved, SECT)
    assert (
        one_sector(base)["sector_change_20d"].iloc[i]
        == one_sector(after)["sector_change_20d"].iloc[i]
    )


def test_sector_change_cannot_see_the_future():
    f = sector_frame()
    f["median_return"] = np.random.default_rng(0).normal(0, 0.01, len(f))
    full, _ = compute_sector(f, SECT)
    cut, _ = compute_sector(f.iloc[:90].copy(), SECT)
    pd.testing.assert_series_equal(
        one_sector(full)["sector_change_20d"].iloc[:90],
        one_sector(cut)["sector_change_20d"],
        check_names=False,
    )


# --- the join: symbol -> sector -> (date, sector) ------------------------


def sector_input(f, lab, basis="test basis"):
    return SectorInput(frame=f, labels=lab, basis=basis)


def test_the_join_uses_the_symbols_sector_on_each_date():
    cal = calendar(120)
    f = sector_frame(returns={"8300": 0.01, "8700": -0.01})
    lab = labels([("TST", "8300", cal[0]), ("TST", "8700", cal[100])])
    out, _ = compute(frame(n=120), SECT, sector=sector_input(f, lab))
    assert out["sector_change_20d"].iloc[90] == pytest.approx(1.01**20 - 1)
    assert out["sector_change_20d"].iloc[110] == pytest.approx(0.99**20 - 1)


def test_stock_vs_sector_is_the_stock_change_minus_the_sector_change():
    cal = calendar(120)
    close = 100 * 1.02 ** np.arange(120)
    out, _ = compute(
        frame(n=120, close=close),
        {**SECT, **VS},
        sector=sector_input(sector_frame(), labels([("TST", "8300", cal[0])])),
    )
    expected = (1.02**20 - 1) - (1.01**20 - 1)
    assert out["stock_vs_sector_20d"].iloc[-1] == pytest.approx(expected)


def test_stock_vs_sector_needs_the_stocks_own_window_clean():
    """The sector value exists, but the stock's own 20-session window crosses a
    suspension: the comparison is over the wrong period, so NaN."""
    cal = calendar(120)
    out, _ = compute(
        frame(n=120, gaps=[110]),
        {**SECT, **VS},
        sector=sector_input(sector_frame(), labels([("TST", "8300", cal[0])])),
    )
    assert not np.isnan(out["sector_change_20d"].iloc[115])
    assert np.isnan(out["stock_vs_sector_20d"].iloc[115])


def test_a_symbol_with_no_label_at_all_is_blank_and_flagged():
    """A delisted stock missing from every snapshot (125 of 1,705 in build 5):
    no sector, so no sector value, and flagged, not a crash."""
    cal = calendar(120)
    try:
        out, _ = compute(
            frame(n=120),
            {**SECT, **VS},
            sector=sector_input(sector_frame(), labels([("OTH", "8300", cal[0])])),
        )
    except Exception as e:  # noqa: BLE001 - not crashing IS the rule under test
        raise AssertionError(f"compute crashed, no label: {e!r}") from None
    for name in ("sector_change_20d", "stock_vs_sector_20d"):
        assert out[name].isna().all()
        assert out[FLAG + name].all()


def test_stock_vs_sector_must_use_the_sectors_window():
    cal = calendar(120)
    fails_with(
        ValueError,
        "same window_days",
        compute,
        frame(n=120),
        {**SECT, "stock_vs_sector_20d": {"enabled": True, "window_days": 10}},
        sector=sector_input(sector_frame(), labels([("TST", "8300", cal[0])])),
    )


def test_enabling_sector_measures_without_sector_input_fails_loudly():
    fails_with(ValueError, "no sector input", compute, frame(n=60), SECT)


# --- the current-label HARD GATE -----------------------------------------


def flagged_run():
    """Snapshot on session 50; the frame's labels are borrowed before it."""
    cal = calendar(120)
    f = sector_frame(current_until=50)
    lab = labels([("TST", "8300", cal[50])])
    return compute(frame(n=120), {**SECT, **VS}, sector=sector_input(f, lab))


def test_each_sector_measure_is_individually_flagged():
    out, fs = flagged_run()
    assert set(fs.flagged) == {"sector_change_20d", "stock_vs_sector_20d"}
    # Every flagged measure carries its flag column: judged here, so a missing
    # one fails this assert rather than crashing on the lookup below.
    flags = {c for c in out.columns if c.startswith(FLAG)}
    assert flags == {FLAG + n for n in fs.flagged}
    for name in fs.flagged:
        assert out[FLAG + name].iloc[45]  # pre-snapshot: flagged
        assert not out[FLAG + name].iloc[100]  # whole window after it: dated


def test_a_symbols_own_borrowed_label_flags_its_values():
    """The sector's rows are all dated, but THIS symbol's first snapshot comes
    later: before it, putting the symbol in that sector is itself look-ahead."""
    cal = calendar(120)
    out, _ = compute(
        frame(n=120),
        SECT,
        sector=sector_input(
            sector_frame(current_until=0), labels([("TST", "8300", cal[100])])
        ),
    )
    assert out[FLAG + "sector_change_20d"].iloc[90]
    assert not out[FLAG + "sector_change_20d"].iloc[110]


def test_a_value_straddling_the_first_snapshot_is_still_flagged():
    # Day 60 is after the snapshot, but its window reaches back before it.
    out, _ = flagged_run()
    assert out[FLAG + "sector_change_20d"].iloc[60]


def test_quarantine_blanks_every_flagged_value():
    out, fs = flagged_run()
    clean = quarantine_flagged(out, fs)
    # Day 89's window (rows 49..89) still reads row 49, the last borrowed one;
    # day 90's (rows 50..90) does not.
    assert clean["sector_change_20d"].iloc[45:90].isna().all()
    assert not np.isnan(clean["sector_change_20d"].iloc[90])
    assert clean["sector_change_20d"].iloc[100] == out["sector_change_20d"].iloc[100]
    assert not any(c.startswith(FLAG) for c in clean.columns)
    # Unflagged measures pass through untouched.
    assert "rvol" not in fs.flagged


def test_the_label_basis_is_in_the_fingerprint():
    cal = calendar(120)
    f, lab = sector_frame(), labels([("TST", "8300", cal[0])])
    _, a = compute(frame(n=120), SECT, sector=sector_input(f, lab, "snapshots A"))
    _, b = compute(frame(n=120), SECT, sector=sector_input(f, lab, "snapshots B"))
    assert isinstance(a, FeatureSet) and a.fingerprint != b.fingerprint
