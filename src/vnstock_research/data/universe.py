"""The point-in-time universe: which symbols were tradeable, and liquid, on each date.

Why point-in-time (decision 2026-09-22): filtering history by TODAY's liquid
list silently keeps only the stocks that turned out well. VIX was thin in 2012
and liquid now; counting its 2012 days because it is liquid today would flatter
every statistic. So every date gets its own universe, built only from data
known at that date's close.

Two sets, both recomputed on demand from `bar_raw` and never stored. A stored
copy is derived data that can drift from its source, which is exactly what
happened to `trading_day` (2025-05-02 phantom). `bar_raw` is not build-scoped,
so neither set depends on which adjustment build is promoted.

  TRADEABLE on D: a bar_raw row that day with matched volume > 0, not moved off
    a weekend (date_shifted), and not inside an excluded window.
    - A missing row means suspended, not yet listed, or delisted. Each of those
      is correctly outside.
    - A zero-volume row is a placeholder at the previous close (98.5% of the
      4,399 since 2012), not a day anyone could trade.
    - A delisted stock is tradeable on every day it actually traded. That is
      the universe-membership half of G11 (survivorship).
    - Whole market: `exchange` is today's listing, not the one in force on the
      date, so no per-exchange split is possible.

  LIQUID on D: tradeable on D, traded on >= min_trading_days_in_lookback of the
    last lookback_days SESSIONS (D included), and its average traded value on
    the days it traded >= min_avg_matched_value (config/rules/universe.yaml).
    - Sessions, not calendar days: a Tet week is not four missing trading days.
    - Traded value = close x matched volume from bar_raw. On CafeF rows that is
      the VND actually traded. On backfilled vnstock rows the price is already
      adjusted (lower than the real price going back), so the value is
      UNDERSTATED. Clearing the floor on it is a true pass: it can only exclude
      wrongly, never include wrongly. `bar_adjusted` must NOT be used here: the
      seam rescale (G17) can lift those spans above the real price.

All the rules live in the pure functions below, not in the SQL, so each one is
unit-tested without a database (tests/test_universe.py).
"""

from __future__ import annotations

import pandas as pd
import yaml

from . import db

UNIVERSE_CONFIG = db.REPO / "config" / "rules" / "universe.yaml"

ROW_COLUMNS = [
    "trade_date",
    "symbol",
    "close",
    "matched_volume",
    "date_shifted",
    "excluded",
    "adj_close",
]

# adj_close is only for breadth (direction must survive an ex-dividend day). The
# universe itself never reads it.
_SQL = """
SELECT r.trade_date, r.symbol, r.close, r.matched_volume, r.date_shifted,
       EXISTS (
           SELECT 1 FROM excluded_window w
           WHERE w.symbol = r.symbol
             AND r.trade_date BETWEEN w.valid_from AND w.valid_to
       ) AS excluded,
       {adj} AS adj_close
FROM bar_raw r
{join}
WHERE r.trade_date BETWEEN %(start)s AND %(end)s
"""
_JOIN_ADJ = (
    "LEFT JOIN bar_adjusted a ON a.symbol = r.symbol "
    "AND a.trade_date = r.trade_date AND a.build_id = %(build)s"
)


def liquidity_config() -> dict:
    return yaml.safe_load(UNIVERSE_CONFIG.read_text())["liquidity"]


def load_rows(conn, start, end=None, warmup: int = 0, build: int | None = None):
    """bar_raw rows from `warmup` sessions before `start` through `end`.

    Returns (rows, calendar). The calendar is every session in that range, so a
    rolling window over it counts sessions. Pass `build` to attach that build's
    adjusted close (breadth needs it; the universe does not).
    """
    with conn.cursor() as cur:
        if end is None:
            cur.execute("SELECT max(trade_date) FROM trading_day")
            (end,) = cur.fetchone()
        if warmup:
            cur.execute(
                "SELECT min(trade_date) FROM (SELECT DISTINCT trade_date "
                "FROM trading_day WHERE trade_date < %s "
                "ORDER BY trade_date DESC LIMIT %s) x",
                (start, warmup),
            )
            (first,) = cur.fetchone()
            start = first or start
        cur.execute(
            "SELECT DISTINCT trade_date FROM trading_day "
            "WHERE trade_date BETWEEN %s AND %s ORDER BY 1",
            (start, end),
        )
        calendar = [r[0] for r in cur.fetchall()]
        sql = _SQL.format(
            adj="a.close" if build is not None else "NULL::numeric",
            join=_JOIN_ADJ if build is not None else "",
        )
        cur.execute(sql, {"start": start, "end": end, "build": build})
        rows = pd.DataFrame(cur.fetchall(), columns=ROW_COLUMNS)
    for col in ("close", "matched_volume", "adj_close"):
        rows[col] = rows[col].astype("float64")
    return rows, calendar


def tradeable(rows: pd.DataFrame) -> pd.Series:
    """The TRADEABLE rule, one boolean per row (see the module docstring)."""
    return (
        (rows["matched_volume"] > 0)
        & ~rows["date_shifted"].astype(bool)
        & ~rows["excluded"].astype(bool)
    )


def panel(rows: pd.DataFrame, calendar, column: str) -> pd.DataFrame:
    """Sessions x symbols: `column` where the row is tradeable, NaN elsewhere.

    Reindexed onto the full calendar, so row i-1 is always the session before
    row i. That is what makes "the previous session" and "the last 60
    sessions" plain shifts and rolling windows.
    """
    t = rows[tradeable(rows)]
    wide = t.pivot(index="trade_date", columns="symbol", values=column)
    return wide.reindex(pd.Index(calendar, name="trade_date"))


def tradeable_panel(rows: pd.DataFrame, calendar) -> pd.DataFrame:
    """Sessions x symbols, True where the symbol was tradeable that session."""
    return panel(rows, calendar, "matched_volume").notna()


def liquid_panel(rows: pd.DataFrame, calendar, cfg: dict | None = None):
    """(liquid, avg_value): sessions x symbols. Trailing windows only.

    NaN-safe on purpose: pandas' rolling mean counts only non-NaN values toward
    min_periods, so it would silently accept a window with 40 traded days as
    "full". Summing and dividing keeps the 60 a count of SESSIONS.
    """
    cfg = cfg or liquidity_config()
    span = int(cfg["lookback_days"])
    rows = rows.assign(value=rows["close"] * rows["matched_volume"])
    value = panel(rows, calendar, "value")
    traded = value.notna()
    days = traded.astype("float64").rolling(span, min_periods=span).sum()
    avg = value.fillna(0.0).rolling(span, min_periods=span).sum() / days
    liquid = (
        traded
        & (days >= int(cfg["min_trading_days_in_lookback"]))
        & (avg >= float(cfg["min_avg_matched_value"]))
    )
    return liquid, avg.where(liquid)


def liquid(conn, start, end=None) -> pd.DataFrame:
    """Sessions x symbols, True where liquid ON THAT DATE. The research filter."""
    cfg = liquidity_config()
    rows, calendar = load_rows(conn, start, end, warmup=int(cfg["lookback_days"]) - 1)
    out, _ = liquid_panel(rows, calendar, cfg)
    return out.loc[out.index >= pd.to_datetime(start).date()]


def liquid_on_latest(conn) -> pd.Series:
    """Average traded value of the symbols liquid on the latest session, largest
    first. For reporting (`features.bars.liquid_symbols`)."""
    cfg = liquidity_config()
    with conn.cursor() as cur:
        cur.execute("SELECT max(trade_date) FROM trading_day")
        (last,) = cur.fetchone()
    rows, calendar = load_rows(conn, last, last, warmup=int(cfg["lookback_days"]) - 1)
    liq, avg = liquid_panel(rows, calendar, cfg)
    return avg.iloc[-1][liq.iloc[-1]].sort_values(ascending=False)
