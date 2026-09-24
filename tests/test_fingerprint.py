"""Tests for the fingerprint (patterns/fingerprint.py, doc §3.6): assembly,
the generated schema, storage with its staleness checks, and query(). The
gate (validated) is tested in test_evidence.py. One test per rule; each
fails if its rule is removed.

Two synthetic stocks over 300 sessions (2020-01 to 2021-02, so two year
files), with measures from all three registries. The sector labels are
borrowed for the first 150 sessions, so the sector values are flagged there.
"""

import numpy as np
import pandas as pd
import pytest

from vnstock_research.features import REGISTRY, compute, load_config
from vnstock_research.features.base import (
    FLAG,
    MARKET_REGISTRY,
    SECTOR_REGISTRY,
    FeatureSet,
)
from vnstock_research.patterns import fingerprint as fpm
from vnstock_research.patterns.fingerprint import (
    Fingerprint,
    assemble,
    load,
    query,
    schema,
    write,
)

from ._helpers import fails_with, frame
from .test_features_market import market_frame
from .test_sector import labels, sector_frame, sector_input
from .test_universe import calendar

N = 300
BORROWED_UNTIL = 150
NAMES = [
    "rvol",
    "body_to_range",
    "hammer_shape",
    "bullish_engulfing",
    "index_above_ma_50",
    "sector_change_20d",
    "stock_vs_sector_20d",
]


def config(**override):
    full = load_config()
    cfg = {n: dict(full[n]) for n in NAMES}
    cfg["rvol"]["lookback_days"] = 10  # not the default: the schema must use THIS
    cfg["doji"] = {**full["doji"], "enabled": False}
    for name, params in override.items():
        cfg[name] = {**cfg[name], **params}
    return cfg


def stock(symbol, seed, gaps=None):
    rng = np.random.default_rng(seed)
    close = 20 * np.cumprod(1 + rng.normal(0, 0.02, N))
    df = frame(n=N, close=close, volume=rng.uniform(500, 1500, N), gaps=gaps)
    df["symbol"] = symbol
    op = close * (1 + rng.normal(0, 0.01, N))
    df["open"] = op
    df["high"] = np.maximum(op, close) * (1 + rng.uniform(0, 0.02, N))
    df["low"] = np.minimum(op, close) * (1 - rng.uniform(0, 0.02, N))
    for c in ("open", "high", "low", "close"):
        df["raw_" + c] = df[c]
    return df


def inputs():
    cal = calendar(N)
    market = {"index": market_frame(n=N, close=np.linspace(100, 130, N))}
    sector = sector_input(
        sector_frame(n=N, current_until=BORROWED_UNTIL),
        labels([("AAA", "8300", cal[0]), ("BBB", "8300", cal[0])]),
    )
    return market, sector


STOCKS = [stock("AAA", 1), stock("BBB", 2, gaps=[200])]


def stacked(cfg=None):
    market, sector = inputs()
    return assemble(STOCKS, cfg or config(), market, sector)


def stored(tmp_path, cfg=None, build_id=5):
    values, fs = stacked(cfg)
    write(values, fs, build_id, tmp_path)
    return values, fs


# --- assembly ------------------------------------------------------------


def test_each_stock_block_is_exactly_what_compute_returned():
    values, _ = stacked()
    market, sector = inputs()
    for bars in STOCKS:
        own, _ = compute(bars, config(), market=market, sector=sector)
        block = values[values["symbol"] == bars["symbol"].iloc[0]].reset_index(
            drop=True
        )
        assert list(block["trade_date"]) == list(bars["trade_date"])
        pd.testing.assert_frame_equal(block[list(own.columns)], own)


def test_every_enabled_measure_and_flag_is_a_column_and_nothing_else():
    values, fs = stacked()
    assert list(values.columns) == (
        ["symbol", "trade_date"]
        + list(fs.measures)
        + [FLAG + "sector_change_20d", FLAG + "stock_vs_sector_20d"]
    )
    assert set(fs.measures) == set(NAMES) and "doji" not in values


def test_a_row_never_sees_a_later_row():
    """Assembling history cut at session t gives the same rows up to t: no
    fill or normalisation over the stacked table (the full-history z-score is
    the classic look-ahead)."""
    full, _ = stacked()
    market, sector = inputs()
    cut, _ = assemble([s.iloc[:200] for s in STOCKS], config(), market, sector)
    early = full[full["trade_date"] < STOCKS[0]["trade_date"].iloc[200]]
    pd.testing.assert_frame_equal(early.reset_index(drop=True), cut)


# --- the schema: generated from the registries ------------------------------


def test_the_schema_is_read_from_the_registries_with_this_feature_sets_params():
    _, fs = stacked()
    sch = schema(fs).set_index("column")
    for name in fs.measures:
        m = REGISTRY.get(name) or MARKET_REGISTRY.get(name) or SECTOR_REGISTRY[name]
        row = sch.loc[name]
        assert row["group"] == m.fn.__module__.rsplit(".", 1)[1]
        assert (row["kind"], row["doc_ref"]) == (m.kind, m.doc_ref)
        assert row["lookback"] == m.lookback(fs.params[name])
    assert sch.loc["rvol", "lookback"] == 10
    assert sch.loc["index_above_ma_50", "registry"] == "market"
    assert sch.loc[FLAG + "sector_change_20d", "kind"] == "flag"


def test_every_registered_measure_has_a_description():
    """The description is the docstring: a measure without one would leave a
    blank line in the report."""
    fs = FeatureSet(
        measures=tuple(n for n, v in load_config().items() if v["enabled"]),
        params={
            n: {k: x for k, x in v.items() if k != "enabled"}
            for n, v in load_config().items()
        },
    )
    sch = schema(fs)
    assert len(sch) == len(fs.measures)
    assert (sch["description"].str.len() > 20).all(), sch.loc[
        sch["description"].str.len() <= 20, "column"
    ].tolist()


def test_direction_is_a_report_label_never_a_value():
    values, fs = stacked()
    sch = schema(fs).set_index("column")
    assert sch.loc["bullish_engulfing", "direction"] == "bullish"
    assert pd.isna(sch.loc["hammer_shape", "direction"])  # depends on the trend (P1)
    assert "direction" not in values.columns
    fails_with(
        KeyError, "direction", query, Fingerprint(values, None, {}), {"direction": 1}
    )


# --- storage -------------------------------------------------------------


def test_storage_round_trips_exactly_unknown_included(tmp_path):
    values, fs = stored(tmp_path)
    fp = load(5, fs, root=tmp_path)
    pd.testing.assert_frame_equal(
        fp.values.drop(columns="trade_date"), values.drop(columns="trade_date")
    )
    assert list(pd.to_datetime(fp.values["trade_date"]).dt.date) == list(
        values["trade_date"]
    )
    assert fp.values["rvol"].isna().sum() == values["rvol"].isna().sum() > 0
    m = fp.manifest
    assert (m["build_id"], m["featureset"], m["rows"]) == (
        5,
        fs.fingerprint,
        len(values),
    )


def test_one_file_per_year_and_load_reads_only_the_range_asked(tmp_path):
    _, fs = stored(tmp_path)
    d = tmp_path / f"5_{fs.fingerprint}"
    assert sorted(p.name for p in d.glob("*.parquet")) == [
        "2020.parquet",
        "2021.parquet",
    ]
    fp = load(5, fs, root=tmp_path, start="2020-06-01", end="2020-12-31")
    dates = pd.to_datetime(fp.values["trade_date"])
    assert dates.min() >= pd.Timestamp("2020-06-01")
    assert dates.max() <= pd.Timestamp("2020-12-31")


def test_another_build_is_refused(tmp_path):
    _, fs = stored(tmp_path, build_id=5)
    fails_with(
        FileNotFoundError,
        r"no fingerprint for build 6.*stored: 5_",
        load,
        6,
        fs,
        root=tmp_path,
    )


def test_a_changed_feature_set_is_refused(tmp_path):
    stored(tmp_path)
    _, newer = stacked(config(rvol={"lookback_days": 20}))
    fails_with(
        FileNotFoundError,
        f"feature set {newer.fingerprint}",
        load,
        5,
        newer,
        root=tmp_path,
    )


def test_a_manifest_that_disagrees_with_its_folder_is_refused(tmp_path):
    """A folder copied or renamed to look current is still judged by what its
    manifest says it was built from."""
    _, fs = stored(tmp_path, build_id=5)
    (tmp_path / f"5_{fs.fingerprint}").rename(tmp_path / f"6_{fs.fingerprint}")
    fails_with(
        ValueError, "stale.*build_id stored 5 != current 6", load, 6, fs, root=tmp_path
    )


def test_changed_measure_code_is_refused(tmp_path, monkeypatch):
    _, fs = stored(tmp_path)
    monkeypatch.setattr(fpm, "code_hash", lambda: "a-newer-code")
    fails_with(ValueError, "stale.*code", load, 5, fs, root=tmp_path)


def test_the_code_hash_covers_the_measure_code_and_only_it(tmp_path, monkeypatch):
    import shutil

    pkg = tmp_path / "pkg"
    shutil.copytree(fpm.PKG, pkg, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(fpm, "PKG", pkg)
    before = fpm.code_hash()
    with open(pkg / "backtest" / "__init__.py", "a") as f:
        f.write("\n# not measure code\n")
    assert fpm.code_hash() == before
    for rule in ("features/volume.py", "data/checks.py", "patterns/candles.py"):
        with open(pkg / rule, "a") as f:
            f.write("\n# a changed rule\n")
        assert fpm.code_hash() != before, rule
        before = fpm.code_hash()


def test_a_file_changed_after_writing_is_refused(tmp_path):
    values, fs = stored(tmp_path)
    path = tmp_path / f"5_{fs.fingerprint}" / "2021.parquet"
    other = values[pd.to_datetime(values["trade_date"]).dt.year == 2021].copy()
    other["rvol"] = 1.0
    other.to_parquet(path, index=False)
    fails_with(ValueError, "2021.parquet changed", load, 5, fs, root=tmp_path)


def test_a_rewrite_that_dies_half_way_leaves_nothing_loadable(tmp_path, monkeypatch):
    values, fs = stored(tmp_path)
    real, calls = pd.DataFrame.to_parquet, []

    def dies_on_second_year(self, *a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(self, *a, **k)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", dies_on_second_year)
    with pytest.raises(OSError):
        write(values, fs, 5, tmp_path)
    fails_with(
        FileNotFoundError, "no fingerprint for build 5", load, 5, fs, root=tmp_path
    )


def test_a_flagged_measure_is_always_loaded_with_its_flag(tmp_path):
    _, fs = stored(tmp_path)
    fp = load(5, fs, root=tmp_path, columns=["sector_change_20d", "rvol"])
    assert list(fp.values.columns) == [
        "symbol",
        "trade_date",
        "sector_change_20d",
        "rvol",
        FLAG + "sector_change_20d",
    ]


# --- query(): exact combinations ------------------------------------------


def grid():
    """symbol, a boolean pattern and a numeric, with one unknown each."""
    values = pd.DataFrame(
        {
            "symbol": ["A", "A", "A", "B", "B", "B"],
            "trade_date": calendar(6),
            "hammer_shape": [1.0, 1.0, 0.0, 1.0, np.nan, 1.0],
            "rvol": [2.0, 1.5, 3.0, 1.0, 2.0, np.nan],
        }
    )
    return Fingerprint(values, None, {})


def test_query_counts_rows_where_every_condition_holds():
    m = query(grid(), {"hammer_shape": 1, "rvol": ">=1.5"})
    assert m.hit.tolist()[:4] == [1.0, 1.0, 0.0, 0.0]
    assert (m.occurrences, m.judged) == (2, 4)
    assert m.per_symbol.to_dict() == {"A": 2, "B": 0}


def test_unknown_is_never_counted_as_false():
    m = query(grid(), {"hammer_shape": 1, "rvol": ">=1.5"})
    assert np.isnan(m.hit.iloc[4]) and np.isnan(m.hit.iloc[5])


def test_a_comparison_includes_its_boundary_only_when_asked():
    assert query(grid(), {"rvol": ">=1.5"}).hit.iloc[1] == 1.0
    assert query(grid(), {"rvol": ">1.5"}).hit.iloc[1] == 0.0


def test_a_threshold_must_be_a_fixed_number():
    """A threshold taken from the data (a full-history percentile) would be
    look-ahead."""
    fails_with(ValueError, "fixed number", query, grid(), {"rvol": ">= p90"})


# --- real data (skipped without the database or a stored fingerprint) -----


def test_the_stored_fingerprint_matches_a_fresh_compute():
    """Spot check: one liquid stock recomputed now equals its stored rows."""
    from vnstock_research.data import db
    from vnstock_research.features import bars, breadth, market, sector

    try:
        conn = db.connect()
    except Exception as e:  # noqa: BLE001 - any connection problem means skip
        pytest.skip(f"no database: {type(e).__name__}")
    with conn:
        build_id, fs = fpm.expected(conn)
        if not (fpm.ROOT / f"{build_id}_{fs.fingerprint}" / fpm.MANIFEST).exists():
            pytest.skip("no stored fingerprint for the current build and feature set")
        fp = load(build_id, fs)
        symbol = bars.liquid_symbols(conn, limit=1)[0]
        own = bars.load(conn, symbol, build=build_id)
        frames = {
            "index": market.load_default(conn),
            "breadth": breadth.load(conn, build=build_id),
        }
        fresh, _ = assemble(
            [own], load_config(), frames, sector.load(conn, build=build_id)
        )
    mine = fp.values[fp.values["symbol"] == symbol].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        mine.drop(columns="trade_date"), fresh.drop(columns="trade_date")
    )
