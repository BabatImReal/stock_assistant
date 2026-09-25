"""Tests for the pattern-history study (backtest/history.py): a DESCRIPTIVE,
information-only aggregation. One test per rule; each fails if its rule is
removed. Synthetic tables only: nothing here reads the database or writes a
real log or report.

THE FIXTURE (k = 3, counted by hand below). Symbols A and B on a few chosen
days; Z on every business day 2019-2022 with no outcome (it supplies the
trading calendar, so de-clustering measures real session distances, and it
shows up in the blank counts as window_gap). C is fired but NOT liquid.

  day         sym hammer  rs    regime  gross   note
  2019-03-04  A   1       +0.1  up      +0.02   counted fire
  2019-03-05  A   1       -     up      -0.01   1 session later: raw only
  2019-03-04  B   0       -0.1  up      +0.01
  2019-03-05  B   0       -     down    -0.03
  2019-07-01  A   1       -     down    -0.02   counted fire
  2019-07-01  B   NaN     -     down    +0.05   hammer unknown: not in its base
  2019-12-31  A   1       -     up      +0.09   known 2020-01-03: after discover
  2020-02-03  A   1       -     up      +0.07
  2020-02-03  B   1       -     up       0.00   flat is not "up"
  2020-02-03  C   1       -     up      +0.10   not liquid
  2020-02-04  B   1       -     up      +0.07   fill flagged
  2021-06-01  A   0       -     NaN     +0.01   regime unknown
  2021-12-31  A   1       -     up      +0.06   known 2022-01-04: after the end
  2022-01-03  A   1       -     up      +0.08   after the study end
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vnstock_research.backtest import evidence as ev
from vnstock_research.backtest import history as hs
from vnstock_research.backtest.batch import gross
from vnstock_research.backtest.forward_returns import Returns
from vnstock_research.features.base import FLAG

from ._helpers import fails_with

K = 3
CFG = {
    "start": "2019-01-01",
    "end": "2021-12-31",
    "horizons": [K],
    "regime": "index_above_ma_50",
    "periods": {
        "discover": {"start": "2019-01-01", "end": "2019-12-31"},
        "validate": {"start": "2020-01-01", "end": "2020-12-31"},
        "holdout_spent": {"start": "2021-01-01", "end": "2021-12-31"},
    },
    "structural": {"rs_60_strong": {"rs_index_60d": ">0"}},
    "summary": {
        "min_declustered_year": 1,
        "min_declustered_total": 1,
        "drop_years": 1,
        "lean_share": 0.5,
        "regime_gap": 0.03,
        "top": 10,
    },
}
PROTO = {"registered": {"triggers": ["hammer_shape"]}}
N = np.nan
ROWS = [
    # day, sym, hammer, rs, regime, gross, known_on, liquid, fill_flagged
    ("2019-03-04", "A", 1, 0.1, 1, 0.02, "2019-03-07", True, False),
    ("2019-03-05", "A", 1, N, 1, -0.01, "2019-03-08", True, False),
    ("2019-03-04", "B", 0, -0.1, 1, 0.01, "2019-03-07", True, False),
    ("2019-03-05", "B", 0, N, 0, -0.03, "2019-03-08", True, False),
    ("2019-07-01", "A", 1, N, 0, -0.02, "2019-07-04", True, False),
    ("2019-07-01", "B", N, N, 0, 0.05, "2019-07-04", True, False),
    ("2019-12-31", "A", 1, N, 1, 0.09, "2020-01-03", True, False),
    ("2020-02-03", "A", 1, N, 1, 0.07, "2020-02-06", True, False),
    ("2020-02-03", "B", 1, N, 1, 0.00, "2020-02-06", True, False),
    ("2020-02-03", "C", 1, N, 1, 0.10, "2020-02-06", False, False),
    ("2020-02-04", "B", 1, N, 1, 0.07, "2020-02-07", True, True),
    ("2021-06-01", "A", 0, N, N, 0.01, "2021-06-04", True, False),
    ("2021-12-31", "A", 1, N, 1, 0.06, "2022-01-04", True, False),
    ("2022-01-03", "A", 1, N, 1, 0.08, "2022-01-06", True, False),
]


def tables(rows=ROWS):
    d = pd.DataFrame(
        rows,
        columns=[
            "trade_date", "symbol", "hammer_shape", "rs_index_60d",
            "index_above_ma_50", "ret", "known_on", "liquid", "fill",
        ],
    )  # fmt: skip
    z = pd.DataFrame({"trade_date": pd.bdate_range("2019-01-01", "2022-01-31")})
    z = z.assign(
        symbol="Z", hammer_shape=0.0, rs_index_60d=N, index_above_ma_50=N,
        ret=N, known_on=None, liquid=True, fill=False,
    )  # fmt: skip
    d["trade_date"] = pd.to_datetime(d["trade_date"])
    d = pd.concat([d, z], ignore_index=True)
    d["trade_date"] = d["trade_date"].dt.date
    d["known_on"] = pd.to_datetime(d["known_on"]).dt.date
    fp = SimpleNamespace(
        values=d[
            [
                "symbol",
                "trade_date",
                "hammer_shape",
                "rs_index_60d",
                "index_above_ma_50",
            ]
        ],  # fmt: skip
        manifest={"build_id": 5, "flagged": [], "featureset": "f", "code": "c"},
    )
    reason = np.where(d["symbol"] == "Z", "window_gap", None)
    rt = Returns(
        pd.DataFrame(
            {
                "symbol": d["symbol"],
                "trade_date": d["trade_date"],
                f"ret_{K}": d["ret"],
                f"net_{K}": d["ret"] - 0.004,
                f"mfe_{K}": 0.03,
                f"mae_{K}": -0.03,
                f"known_on_{K}": d["known_on"],
                f"reason_{K}": reason,
                f"{FLAG}fill_{K}": d["fill"],
            }
        ),
        {
            "build_id": 5,
            "horizons": [K],
            "net_provisional": True,
            "rules": "r",
            "code": "c",
        },
    )
    uni = d.loc[d["liquid"], ["symbol", "trade_date"]].assign(tier=1)
    return fp, rt, uni


def loader(fp, rt, uni):
    return lambda start, end, before: ev.validated(fp, gross(rt), uni, before=before)


@pytest.fixture(scope="module")
def result():
    return hs.study(loader(*tables()), CFG, PROTO)


def cell(table, signal="hammer_shape", level="month", regime="all", **key):
    t = table[
        (table["signal"] == signal)
        & (table["k"] == K)
        & (table["level"] == level)
        & (table["regime"] == regime)
    ]
    for c, v in key.items():
        t = t[t[c] == v]
    assert len(t) <= 1, t
    return None if t.empty else t.iloc[0]


# --- the hand counts ----------------------------------------------------------


def test_a_month_matches_the_hand_count(result):
    r = cell(result[0], year=2019, month=3)
    assert (r["fires_raw"], r["fires_declustered"]) == (2, 1)
    assert r["mean_gross"] == pytest.approx(0.02)
    assert r["median_gross"] == pytest.approx(0.02)
    assert r["hit_rate"] == 1.0
    # the base: A 03-04, A 03-05, B 03-04, B 03-05
    assert r["base_n"] == 4
    assert r["base_mean"] == pytest.approx(-0.0025)
    assert r["base_median"] == pytest.approx(0.0)
    assert r["base_hit"] == 0.5
    assert r["edge"] == pytest.approx(0.5)
    assert r["excess_mean"] == pytest.approx(0.0225)
    assert r["period"] == "discover"


def test_a_year_and_a_period_match_the_hand_count(result):
    for r in (
        cell(result[0], level="year", year=2019),
        cell(result[0], level="period", period="discover"),
    ):
        assert (r["fires_raw"], r["fires_declustered"]) == (3, 2)
        assert r["mean_gross"] == pytest.approx(0.0)
        assert r["hit_rate"] == 0.5
        assert (r["base_n"], r["base_hit"]) == (5, 0.4)
        assert r["edge"] == pytest.approx(0.1)


def test_the_whole_study_matches_the_hand_count(result):
    r = cell(result[0], level="all")
    assert (r["fires_raw"], r["fires_declustered"]) == (5, 4)
    # de-clustered: +0.02, -0.02, +0.07, 0.00
    assert r["mean_gross"] == pytest.approx(0.0175)
    assert r["median_gross"] == pytest.approx(0.01)
    assert (r["hit_rate"], r["base_n"], r["base_hit"]) == (0.5, 8, 0.5)
    assert r["period"] == "all"


def test_the_regime_split_is_on_the_signal_day(result):
    up = cell(result[0], level="all", regime="up")
    assert (up["fires_raw"], up["fires_declustered"], up["base_n"]) == (4, 3, 5)
    assert up["hit_rate"] == pytest.approx(2 / 3)
    assert up["base_hit"] == pytest.approx(0.6)
    down = cell(result[0], level="all", regime="down")
    assert (down["fires_raw"], down["fires_declustered"], down["base_n"]) == (1, 1, 2)
    assert (down["hit_rate"], down["base_hit"]) == (0.0, 0.0)
    m = cell(result[0], year=2019, month=3, regime="up")
    assert (m["fires_raw"], m["fires_declustered"], m["base_n"]) == (2, 1, 3)
    assert m["base_hit"] == pytest.approx(2 / 3)


def test_an_unknown_regime_counts_in_all_only(result):
    assert cell(result[0], level="year", year=2021)["base_n"] == 1
    assert cell(result[0], level="year", year=2021, regime="up") is None
    assert cell(result[0], level="year", year=2021, regime="down") is None


def test_declustering_runs_on_the_whole_history_then_splits(result):
    # A 03-05 is one session after A 03-04: raw in March, never de-clustered;
    # A 07-01 is far enough to count again. B 02-03 (another symbol) counts.
    assert cell(result[0], year=2019, month=7)["fires_declustered"] == 1
    assert cell(result[0], year=2020, month=2)["fires_declustered"] == 2


def test_flat_is_not_up(result):
    r = cell(result[0], year=2020, month=2)
    assert r["hit_rate"] == 0.5  # A +7%, B 0.00%
    assert r["base_hit"] == 0.5


def test_the_base_is_where_the_signal_could_be_judged(result):
    # B 07-01: hammer unknown -> out of the hammer's base, in the market's.
    assert cell(result[0], year=2019, month=7)["base_n"] == 1
    m = cell(result[0], signal=hs.BASE, year=2019, month=7)
    assert (m["base_n"], m["base_hit"]) == (2, 0.5)
    assert m["base_mean"] == pytest.approx(0.015)


def test_the_market_base_is_not_declustered(result):
    m = cell(result[0], signal=hs.BASE, year=2019, month=3)
    assert m["fires_declustered"] == m["base_n"] == 4
    assert m["hit_rate"] == m["base_hit"]


def test_the_structural_signals_use_their_fixed_comparison(result):
    r = cell(result[0], signal="rs_60_strong", year=2019, month=3)
    assert r is not None
    assert (r["fires_raw"], r["base_n"], r["base_hit"]) == (1, 2, 1.0)
    assert r["family"] == "structural"
    assert cell(result[0], signal="rs_60_strong", year=2020, month=2) is None


# --- point in time ------------------------------------------------------------


def test_an_illiquid_or_fill_flagged_day_never_enters(result):
    t = result[0]
    r = cell(t, signal=hs.BASE, year=2020, month=2)
    assert r["base_n"] == 2  # A, B 02-03: not C (illiquid), not B 02-04 (fill)


def test_an_outcome_known_after_its_period_is_blanked(result):
    # A 2019-12-31 resolves 2020-01-03, after discover ends: not in 2019.
    assert cell(result[0], signal=hs.BASE, year=2019, month=12) is None
    # A 2021-12-31 resolves in 2022, after the study end.
    assert cell(result[0], signal=hs.BASE, year=2021, month=12) is None
    d = result[1].set_index("period")
    # only liquid days are carried: A/B's rows + Z's calendar, never C
    z2020 = len(pd.bdate_range("2020-01-01", "2020-12-31"))
    assert d.loc["validate", "liquid"] == 3 + z2020
    assert d.loc["discover", "not_yet_known"] == 1
    assert d.loc["holdout_spent", "not_yet_known"] == 1


def test_nothing_after_the_study_end_enters(result):
    assert result[0]["year"].dropna().max() == 2021


def test_a_study_end_in_2026_is_refused(tmp_path):
    import yaml

    path = tmp_path / "history.yaml"
    for end, ok in (("2025-12-31", True), ("2026-01-01", False)):
        path.write_text(yaml.safe_dump({"study": {**CFG, "end": end}}))
        if ok:
            assert hs.load_config(path)["end"] == end
        else:
            fails_with(ValueError, "2026 is excluded", hs.load_config, path)


def test_the_real_config_excludes_2026_and_labels_the_periods():
    cfg = hs.load_config()
    assert pd.Timestamp(cfg["end"]) < pd.Timestamp("2026-01-01")
    assert [p[0] for p in hs.periods(cfg)] == ["discover", "validate", "holdout_spent"]
    assert hs.periods(cfg)[-1][3] == "2026-01-01"
    from vnstock_research.backtest.protocol import load_protocol

    slices = load_protocol()["registered"]["slices"]
    for name in ("discover", "validate"):
        assert cfg["periods"][name] == {
            "start": slices[name]["start"],
            "end": slices[name]["end"],
        }
    assert cfg["periods"]["holdout_spent"]["start"] == slices["holdout"]["start"]


def test_each_period_is_purged_at_the_next_periods_start():
    assert [p[3] for p in hs.periods(CFG)] == ["2020-01-01", "2021-01-01", "2022-01-01"]


def test_the_periods_must_tile_the_study_on_whole_years():
    gap = {**CFG, "periods": {**CFG["periods"]}}
    gap["periods"]["validate"] = {"start": "2020-02-01", "end": "2020-12-31"}
    fails_with(ValueError, "whole years", hs.periods, gap)
    # whole years, but 2020 belongs to no period
    hole = {**CFG, "periods": {"discover": CFG["periods"]["discover"],
            "holdout_spent": CFG["periods"]["holdout_spent"]}}  # fmt: skip
    fails_with(ValueError, "must start 2020-01-01", hs.periods, hole)
    short = {**CFG, "end": "2022-12-31"}
    fails_with(ValueError, "study end", hs.periods, short)


def test_only_a_validated_table_is_described():
    fp, rt, uni = tables()
    fails_with(TypeError, "Validated", hs.gated_rows, fp, "discover",
               "2019-01-01", "2019-12-31", [K], [])  # fmt: skip


def test_the_signals_are_the_21_patterns_and_8_structural():
    from vnstock_research.backtest.protocol import load_protocol

    sigs = hs.signals(hs.load_config(), load_protocol())
    fam = pd.Series([f for f, _ in sigs.values()]).value_counts()
    assert (fam["pattern"], fam["structural"]) == (21, 8)
    assert sigs["hammer_shape"] == ("pattern", {"hammer_shape": 1})
    assert sigs["stage_2_advancing"] == ("structural", {"trend_stage": 2})


# --- information only: no log, no holdout path ------------------------------


def _md5s():
    research = Path(__file__).resolve().parents[1] / "research"
    return {
        p.name: hashlib.md5(p.read_bytes()).hexdigest()
        for p in sorted(research.glob("*.csv"))
    }


def test_a_run_writes_only_the_report_and_the_csv(tmp_path, result):
    before = _md5s()
    sigs = hs.signals(CFG, PROTO)
    table, dropped, summary, manifest = result
    txt, csv = hs.write(table, dropped, summary, CFG, manifest, sigs, tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "pattern-history.csv",
        "pattern-history.txt",
    ]
    assert _md5s() == before
    back = pd.read_csv(csv)
    assert list(back.columns) == hs.COLUMNS
    text = txt.read_text()
    assert text.count(hs.HEADER) == 2  # at the top and above the summary
    assert "2026 EXCLUDED ENTIRELY" in text
    assert "ALREADY-SPENT holdout window" in text


def test_there_is_no_holdout_or_log_path_in_the_study():
    # Nothing that writes a log or opens the holdout is even imported, and no
    # log file is named.
    for name in ("_holdout_gated", "run_holdout", "holdout", "_append_log",
                 "append", "LOG", "BATCH_LOG"):  # fmt: skip
        assert not hasattr(hs, name), name
    assert "hypothesis_log" not in Path(hs.__file__).read_text()


# --- the summary rules -------------------------------------------------------


def _years(edges, fires=100, base=0.5, up=None, down=None):
    """A tidy table for one signal: one year row per edge, and pooled rows."""
    rows = []
    for y, e in edges.items():
        rows.append(
            {"signal": "x", "family": "pattern", "k": K, "level": "year",
             "regime": "all", "period": "discover", "year": y, "month": N,
             "fires_raw": fires, "fires_declustered": fires,
             "mean_gross": e, "hit_rate": base + e, "base_n": 1000,
             "base_hit": base, "edge": e, "base_mean": 0.0}
        )  # fmt: skip
    wins = sum(fires * (base + e) for e in edges.values())
    n = fires * len(edges)
    pooled = {**rows[0], "level": "all", "year": N, "period": "all",
              "fires_raw": n, "fires_declustered": n, "hit_rate": wins / n,
              "edge": wins / n - base, "mean_gross": wins / n - base}  # fmt: skip
    rows.append(pooled)
    for regime, e in (("up", up), ("down", down)):
        if e is not None:
            rows.append({**pooled, "regime": regime, "edge": e})
    return pd.DataFrame(rows)


def test_an_edge_carried_by_one_year_is_labelled_leaning():
    s = hs.consistency(_years({2012: 0.20, 2013: 0.0, 2014: 0.0, 2015: 0.01}), CFG)
    r = s.iloc[0]
    assert r["best_years"][0][0] == 2012
    assert r["leans"]
    assert (r["years_beat"], r["years_judged"]) == (2, 4)


def test_an_edge_spread_over_the_years_holds_without_its_best():
    s = hs.consistency(_years({2012: 0.05, 2013: 0.04, 2014: 0.05, 2015: 0.04}), CFG)
    assert not s.iloc[0]["leans"]
    assert s.iloc[0]["edge_without_best"] == pytest.approx(0.0433, abs=1e-3)


def test_a_thin_year_is_not_judged():
    t = _years({2012: 0.05, 2013: -0.05})
    t.loc[t["year"] == 2013, "fires_declustered"] = 0
    s = hs.consistency(t, CFG)
    assert (s.iloc[0]["years_judged"], s.iloc[0]["years_beat"]) == (1, 1)


def test_the_regime_gap_is_down_minus_up():
    s = hs.consistency(_years({2012: 0.05}, up=0.01, down=0.08), CFG)
    assert s.iloc[0]["up"][1] == 0.01 and s.iloc[0]["down"][1] == 0.08
    assert s.iloc[0]["regime_gap"] == pytest.approx(0.07)


def test_the_ranking_is_by_consistency_then_edge():
    a = _years({2012: 0.01, 2013: 0.01, 2014: 0.01})
    b = _years({2012: 0.30, 2013: -0.01, 2014: 0.02}).assign(signal="b")
    c = _years({2012: 0.02, 2013: 0.02, 2014: 0.02}).assign(signal="c")
    s = hs.consistency(pd.concat([a, b, c], ignore_index=True), CFG)
    assert list(hs.ranking(s, CFG, K)["signal"]) == ["c", "x", "b"]


def test_the_coin_yardstick_is_the_binomial_tail():
    # >= 10 of 14: (C(14,10)+C(14,11)+C(14,12)+C(14,13)+C(14,14)) / 2^14
    assert hs.coin(14, 10) == pytest.approx((1001 + 364 + 91 + 14 + 1) / 16384)
    assert hs.coin(14, 0) == 1.0


def test_no_positive_edge_is_never_called_holding():
    s = hs.consistency(_years({2012: 0.05, 2013: -0.08, 2014: -0.02}), CFG)
    r = s.iloc[0]
    assert not r["edge"] > 0 and not r["leans"]
    assert "no positive pooled edge" in hs._lean_label(r)
    good = hs.consistency(_years({2012: 0.05, 2013: 0.04, 2014: 0.05}), CFG).iloc[0]
    assert hs._lean_label(good) == " -> holds without them"


def test_a_signal_below_the_minimum_fires_is_not_ranked():
    s = hs.consistency(_years({2012: 0.05, 2013: 0.04}), CFG)
    assert len(hs.ranking(s, CFG, K)) == 1
    few = {**CFG, "summary": {**CFG["summary"], "min_declustered_total": 201}}
    assert hs.ranking(s, few, K).empty


def test_a_2026_row_that_reaches_the_study_is_refused():
    late = {**CFG, "end": "2026-12-31", "periods": {
        **CFG["periods"],
        "holdout_spent": {"start": "2021-01-01", "end": "2026-12-31"},
    }}  # fmt: skip
    rows = [*ROWS, ("2026-03-02", "A", 1, N, 1, 0.01, "2026-03-05", True, False)]
    fails_with(
        ValueError, "2026 is excluded", hs.study, loader(*tables(rows)), late, PROTO
    )
