"""Structural measures: relative strength and the long trend (doc §5.1, §5.3).

Two research loops searched candle shapes; the only new region the second one
found was conditioned on the market regime. These measures ask the structural
question directly: how does a stock behave RELATIVE TO THE MARKET, and where
does it sit in its long trend?

  rs_index_Nd      stock return minus VN-Index return over the last N sessions
  down_day_rs_20d  the mean of (stock - index) daily return on the sessions the
                   index FELL: does the stock resist a weak market?
  price_vs_ma_200  how far above or below its 200-session average
  ma_200_slope     the 200-session average's change over slope_days
  trend_stage      1 basing / 2 advancing / 3 topping / 4 declining

Every one is a per-symbol measure in the ordinary REGISTRY, with the full
features/base.py discipline: a declared lookback covering every row it reads,
so `_window_ok` blanks any window across a trading gap or an excluded day; NaN
where an input is unknown; nothing after T.

WHY THIS MODULE SITS OUTSIDE features/: the stored fingerprint and the stored
returns refuse to load when any code under data/, features/ or patterns/
changes (their code hash; the trading_day lesson). The registered featureset,
which the holdout, the neighbours and the daily scan depend on, must stay
loadable and reproducible, so none of that code is touched. The structural
featureset closes the same drift hole its own way: the hash of THIS file goes
into every structural measure's parameters, so it is in the FeatureSet
fingerprint, and a changed rule is a different featureset.

The index: the per-symbol frame gets the VN-Index close as `index_close`,
joined on trade_date and never filled (`with_index`). A day the index lacks is
NaN, so any value that reads it is unknown, not a guess.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .features.base import boolean_from, featureset, measure
from .features.base import load_config as registered_config

CONFIG = Path(__file__).resolve().parents[2] / "config" / "rules" / "structural.yaml"
NEEDS_RS = ("close", "index_close")


def code_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


def _close(bars: pd.DataFrame, column: str = "close") -> pd.Series:
    return bars[column].astype("float64")


def _change(s: pd.Series, n: int) -> pd.Series:
    return s / s.shift(n) - 1.0


# --- relative strength vs the index -------------------------------------------


def _rs(bars: pd.DataFrame, p: dict) -> pd.Series:
    n = int(p["window_days"])
    # A NaN index close at either end leaves the difference NaN: unknown.
    return _change(_close(bars), n) - _change(_close(bars, "index_close"), n)


def _rs_measure(name: str):
    @measure(
        name=name,
        doc_ref="doc §5.3",
        kind="numeric",
        needs=NEEDS_RS,
        lookback=lambda p: int(p["window_days"]),
    )
    def rs(bars: pd.DataFrame, p: dict) -> pd.Series:
        """The stock's return minus the VN-Index's over the last window_days
        sessions: positive = stronger than the market."""
        return _rs(bars, p)

    return rs


rs_index_20d = _rs_measure("rs_index_20d")
rs_index_60d = _rs_measure("rs_index_60d")
rs_index_120d = _rs_measure("rs_index_120d")


@measure(
    name="down_day_rs_20d",
    doc_ref="doc §5.3",
    kind="numeric",
    needs=NEEDS_RS,
    lookback=lambda p: int(p["window_days"]),
)
def down_day_rs_20d(bars: pd.DataFrame, p: dict) -> pd.Series:
    """On the sessions the index fell in the last window_days, the mean of the
    stock's return minus the index's: does it resist a weak market?

    Every daily index return in the window must be known (a missing index day
    could have been a down day), and at least min_down_days must be down."""
    w, least = int(p["window_days"]), int(p["min_down_days"])
    stock = _change(_close(bars), 1)
    index = _change(_close(bars, "index_close"), 1)
    down = index < 0
    diff = (stock - index).where(down)
    total = diff.rolling(w, min_periods=1).sum()
    count = down.astype("float64").rolling(w, min_periods=w).sum()
    known = index.notna().astype("float64").rolling(w, min_periods=w).sum() == w
    stock_known = stock.notna().astype("float64").rolling(w, min_periods=w).sum() == w
    mean = total / count.where(count >= least)
    return mean.where(known & stock_known)


# --- the long trend -----------------------------------------------------------


def _ma(bars: pd.DataFrame, window: int) -> pd.Series:
    return _close(bars).rolling(window, min_periods=window).mean()


@measure(
    name="price_vs_ma_200",
    doc_ref="doc §5.1",
    kind="numeric",
    needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def price_vs_ma_200(bars: pd.DataFrame, p: dict) -> pd.Series:
    """How far above or below its 200-session average the close sits."""
    ma = _ma(bars, int(p["window_days"]))
    return _close(bars) / ma.replace(0.0, np.nan) - 1.0


@measure(
    name="ma_200_slope",
    doc_ref="doc §5.1",
    kind="numeric",
    needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1 + int(p["slope_days"]),
)
def ma_200_slope(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The 200-session average's change over slope_days: is the long trend
    rising or falling."""
    return _change(_ma(bars, int(p["window_days"])), int(p["slope_days"]))


@measure(
    name="trend_stage",
    doc_ref="doc §5.1",
    kind="numeric",
    needs=("close",),
    lookback=lambda p: int(p["slow_days"]) - 1 + int(p["slope_days"]),
)
def trend_stage(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The stage of the long trend: 2 advancing (close > MA50 > MA200, MA200
    rising), 4 declining (close < MA50 < MA200, MA200 falling), 3 topping
    (MA200 rising, not 2), 1 basing (MA200 not rising, not 4)."""
    close = _close(bars)
    fast, slow = _ma(bars, int(p["fast_days"])), _ma(bars, int(p["slow_days"]))
    slope = _change(slow, int(p["slope_days"]))
    rising = slope > 0
    advancing = (close > fast) & (fast > slow) & rising
    declining = (close < fast) & (fast < slow) & (slope < 0)
    stage = np.select([advancing, declining, rising], [2.0, 4.0, 3.0], default=1.0)
    return boolean_from(pd.Series(stage, index=bars.index), close, fast, slow, slope)


# --- the structural featureset ------------------------------------------------


def load_config(path: Path = CONFIG) -> dict:
    """The structural measures, each carrying this module's code hash."""
    measures = yaml.safe_load(Path(path).read_text())["measures"]
    return {n: {**s, "code": code_hash()} for n, s in measures.items()}


def full_config() -> dict:
    """The registered featureset plus the structural measures."""
    return {**registered_config(), **load_config()}


def with_index(bars: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """The symbol's bars with the index close of the SAME date; never
    forward-filled, so a day the index lacks is NaN."""
    idx = index[["trade_date", "close"]].rename(columns={"close": "index_close"})
    out = bars.merge(idx, on="trade_date", how="left")
    out.index = bars.index
    return out


def expected(conn):
    """(build, FeatureSet) the structural fingerprint must have been built
    from to be current now."""
    from .data import sectors
    from .features import bars, sector

    basis = sector.basis(sectors.load_labels(conn))
    return bars.current_build(conn), featureset(full_config(), basis)


def build(conn, start: str = "2012-01-01"):
    """The structural fingerprint (registered measures + structural ones) for
    the current build, through patterns.fingerprint's own assemble/write."""
    from .features import bars, breadth, market, sector
    from .patterns import fingerprint as fpm

    build_id = bars.current_build(conn)
    index = market.load_default(conn, start)
    frames = {"index": index, "breadth": breadth.load(conn, start, build=build_id)}
    sec = sector.load(conn, start, build=build_id)
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
            "AND trade_date >= %s ORDER BY 1",
            (build_id, start),
        ).fetchall()
    ]
    values, fs = fpm.assemble(
        (
            with_index(f, index)
            for _, f in bars.load_many(conn, symbols, start=start, build=build_id)
        ),
        full_config(),
        frames,
        sec,
    )
    return fpm.write(values, fs, build_id)


if __name__ == "__main__":
    # Through the PACKAGE module: run as a script this file is `__main__`, and
    # the measures would be registered under that name, which the schema
    # (patterns.fingerprint.schema: group = the registering module) cannot use.
    from vnstock_research import structural
    from vnstock_research.data import db

    with db.connect() as conn:
        print(structural.build(conn))
