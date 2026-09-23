"""Sector behaviour (doc §5.4): is this stock's sector strengthening, and is the
stock doing better or worse than its sector?

Doc §5.4: banks, real estate, securities firms and steel move as groups; a
signal on one bank while the whole banking sector strengthens is more credible
than one against it.

THE SECTOR FRAME is its own frame, keyed by (trade_date, sector). It is NOT
the market frame, which has one row per date. It is built once per run from
the universe rows plus the dated membership (data/sectors.py):

    trade_date | sector | counted | median_return | labels_current | gap_before

- counted: members that traded today AND the previous session (the breadth
  rule; a stock back from a suspension has no comparable previous close).
- median_return: the EQUAL-WEIGHTED median of those members' daily returns on
  the ADJUSTED close. Equal-weighted because we hold no share counts;
  a median because one thin stock limit-up should not move a sector.
- Members are ALL TRADEABLE stocks, not the liquid universe (Ben, 2026-09-23;
  the same reasoning as breadth).
- labels_current: True if any member counted that day carried a BORROWED
  (pre-snapshot) label. Every value built on such a row is flagged
  (features/base.py).
- Every calendar session x every sector is present, with counted = 0 where
  nothing was counted, so a rolling window over one sector counts sessions.

THE JOIN, done in features/base.py `compute`:
    symbol --(its label on that date)--> sector --(trade_date, sector)--> value

Measures:
- sector_change_20d (SECTOR_REGISTRY): compounded median return over 20
  sessions, NaN if any day in the window is thin for that sector.
- stock_vs_sector_20d (per-symbol REGISTRY): the stock's own 20-session change
  minus its sector's. It needs the stock's window free of gaps and excluded
  days (the per-symbol guard) AND a valid sector value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..data import sectors, universe
from .base import measure, sector_measure
from .breadth import count_ok, guard_lookback

# Warm-up sessions before `start`, so the first research date has a full
# trailing count baseline and a full 20-session window.
WARMUP = 60


@dataclass(frozen=True)
class SectorInput:
    """What `compute` needs for sector measures.

    frame:  one row per (trade_date, sector) (`build_frame`).
    labels: the dated snapshots (data.sectors.load_labels), to put each symbol
            in its sector on each date.
    basis:  where the labels came from and which dates are borrowed. It is
            recorded in the FeatureSet, so it is part of the fingerprint.
    """

    frame: pd.DataFrame
    labels: pd.DataFrame
    basis: str


def build_frame(rows: pd.DataFrame, calendar, labels: pd.DataFrame) -> pd.DataFrame:
    """The (trade_date, sector) aggregate. See the module docstring."""
    # Tradeable-only panel on the full calendar: the daily change is NaN unless
    # the stock traded today AND the previous session (as in breadth).
    adj = universe.panel(rows, calendar, "adj_close")
    change = adj / adj.shift(1) - 1.0
    sector, current = sectors.panel(labels, calendar)
    sector = sector.reindex(columns=change.columns)
    current = current.reindex(columns=change.columns, fill_value=True)

    long = pd.DataFrame(
        {
            "change": change.stack(),
            "sector": sector.stack(),
            "current": current.stack(),
        }
    ).dropna(subset=["change", "sector"])
    g = long.groupby(["trade_date", "sector"])
    agg = pd.DataFrame(
        {
            "counted": g["change"].size(),
            "median_return": g["change"].median(),
            "labels_current": g["current"].any(),
        }
    )
    grid = pd.MultiIndex.from_product(
        [pd.Index(calendar), sorted(labels["sector"].unique())],
        names=["trade_date", "sector"],
    )
    agg = agg.reindex(grid)
    agg["counted"] = agg["counted"].fillna(0).astype("int64")
    # Nothing counted means nothing known, including whether the label was
    # dated: fail safe to flagged.
    agg["labels_current"] = agg["labels_current"].fillna(True).astype(bool)
    agg["gap_before"] = 0  # calendar-complete by construction
    return agg.reset_index()


def load(conn, start: str = "2012-01-01", build: int | None = None) -> SectorInput:
    from .bars import current_build

    build_id = build if build is not None else current_build(conn)
    labels = sectors.load_labels(conn)
    rows, calendar = universe.load_rows(conn, start, warmup=WARMUP, build=build_id)
    first, last = labels["snapshot_date"].min(), labels["snapshot_date"].max()
    basis = (
        f"{sectors.SOURCE} ICB L2, steel split out at L4; snapshots {first}..{last}; "
        f"dates before {first} borrow current labels (flagged)"
    )
    return SectorInput(build_frame(rows, calendar, labels), labels, basis)


def _lookback(p: dict) -> int:
    # window_days daily returns, each reading its previous session, each
    # judged against count_median_sessions earlier counts.
    return int(p["window_days"]) - 1 + guard_lookback(p)


@sector_measure(
    name="sector_change_20d",
    doc_ref="doc §5.4",
    kind="numeric",
    needs=("median_return", "counted"),
    lookback=_lookback,
)
def sector_change_20d(s: pd.DataFrame, p: dict) -> pd.Series:
    """One sector's compounded median return over window_days sessions."""
    w = int(p["window_days"])
    daily = s["median_return"].where(count_ok(s["counted"], p))
    return np.expm1(np.log1p(daily).rolling(w, min_periods=w).sum())


@measure(
    name="stock_vs_sector_20d",
    doc_ref="doc §5.4",
    kind="numeric",
    needs=("close", "sector_change_20d"),
    lookback=lambda p: int(p["window_days"]),
)
def stock_vs_sector_20d(bars: pd.DataFrame, p: dict) -> pd.Series:
    """The stock's window_days change minus its sector's over the same
    sessions. Positive = stronger than its sector. `sector_change_20d` is the
    joined column (features/base.py), so both use the same window."""
    w = int(p["window_days"])
    close = bars["close"].astype("float64")
    return (close / close.shift(w) - 1.0) - bars["sector_change_20d"]
