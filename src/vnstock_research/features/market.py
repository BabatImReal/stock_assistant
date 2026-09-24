"""Market regime from the index (doc §5.3).

Doc §5.3's point: in Vietnam most stocks move together, so a perfect bullish
setup during a market-wide sell-off usually fails. The regime is recorded
alongside every signal so hit rates can be reported separately for good and bad
market conditions -- which is a reporting dimension first and a filter only if
the data says it should be (blocker G7).

Two things make this different from a per-symbol measure, and both are handled
in `base.py` rather than here:

1. It is computed ONCE per run and joined onto each symbol by trade_date.
   ~3,700 sessions against ~1,700 symbols; computing it inside the per-symbol
   loop would repeat identical work seventeen hundred times.
2. A gap in `index_bar` is a DATA DEFECT, not a suspension. The index trades
   every session the market is open, so a missing row means our data is wrong,
   not that the market paused. It is fatal to any window containing it and is
   reported separately by the data-quality gate.

Breadth (advancers vs decliners) is deliberately NOT here. It needs a
point-in-time universe -- counting only the symbols actually trading on each
date -- which is foundational enough to deserve its own slice, and it must use
ADJUSTED closes so an ex-dividend day is not counted as a fake decline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import db
from .base import boolean_from, market_measure

INDEX_COLUMNS = [
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "gap_before",
]

_SQL = """
WITH cal AS (
    SELECT DISTINCT trade_date FROM trading_day WHERE trade_date >= %(start)s
),
sessions AS (
    SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS n FROM cal
),
i AS (
    SELECT b.symbol, b.trade_date, b.open, b.high, b.low, b.close, b.volume,
           s.n AS session_no
    FROM index_bar b
    JOIN sessions s ON s.trade_date = b.trade_date
    WHERE b.symbol = %(symbol)s AND b.trade_date >= %(start)s
)
SELECT i.symbol, i.trade_date, i.open, i.high, i.low, i.close, i.volume,
       -- Sessions the market was open and the index has no row for. Should
       -- always be 0; anything else is a defect in our data.
       i.session_no - lag(i.session_no) OVER (ORDER BY i.trade_date) - 1
           AS gap_before
FROM i ORDER BY i.trade_date
"""


def load(conn, symbol: str = "VNINDEX", start: str = "2012-01-01") -> pd.DataFrame:
    """The index series, aligned to the trading calendar."""
    with conn.cursor() as cur:
        cur.execute(_SQL, {"symbol": symbol.upper(), "start": start})
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=INDEX_COLUMNS)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype("float64")
    df["gap_before"] = df["gap_before"].fillna(0).astype("int64")
    return df.reset_index(drop=True)


def missing_sessions(conn, symbol: str = "VNINDEX", start: str = "2012-01-01"):
    """Sessions the market traded and the index does not cover.

    Surfaced as its own number because routing around a defect without
    reporting it is how a defect becomes permanent.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM (
                SELECT DISTINCT trade_date FROM trading_day
                WHERE trade_date >= %s
            ) c
            LEFT JOIN index_bar b
                   ON b.trade_date = c.trade_date AND b.symbol = %s
            WHERE b.trade_date IS NULL
            """,
            (start, symbol.upper()),
        )
        return cur.fetchone()[0]


def _ma(market: pd.DataFrame, window: int) -> pd.Series:
    return market["close"].astype("float64").rolling(window, min_periods=window).mean()


@market_measure(
    name="index_above_ma_50",
    doc_ref="doc §5.3",
    kind="boolean",
    needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def index_above_ma_50(market: pd.DataFrame, p: dict) -> pd.Series:
    """Is the index above its 50-session average -- doc §5.3's regime question."""
    ma = _ma(market, int(p["window_days"]))
    close = market["close"].astype("float64")
    return boolean_from(close > ma, ma)


@market_measure(
    name="index_ma_50_slope",
    doc_ref="doc §5.3",
    kind="numeric",
    needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1 + int(p["slope_days"]),
)
def index_ma_50_slope(market: pd.DataFrame, p: dict) -> pd.Series:
    """Whether the average itself is rising -- above a falling average is a
    different regime from above a rising one."""
    ma = _ma(market, int(p["window_days"]))
    return ma / ma.shift(int(p["slope_days"])) - 1.0


@market_measure(
    name="index_change_20d",
    doc_ref="doc §5.3",
    kind="numeric",
    needs=("close",),
    lookback=lambda p: int(p["window_days"]),
)
def index_change_20d(market: pd.DataFrame, p: dict) -> pd.Series:
    """How far the market has moved recently."""
    close = market["close"].astype("float64")
    return close / close.shift(int(p["window_days"])) - 1.0


@market_measure(
    name="index_drawdown_from_high",
    doc_ref="doc §5.3",
    kind="numeric",
    needs=("close",),
    lookback=lambda p: int(p["window_days"]) - 1,
)
def index_drawdown_from_high(market: pd.DataFrame, p: dict) -> pd.Series:
    """How far below its recent peak the market sits.

    Distinguishes "drifting sideways below the average" from "falling hard",
    which the moving-average tests on their own do not.
    """
    close = market["close"].astype("float64")
    peak = close.rolling(int(p["window_days"]), min_periods=int(p["window_days"])).max()
    return close / peak.replace(0.0, np.nan) - 1.0


def load_default(conn, start: str = "2012-01-01") -> pd.DataFrame:
    """The index the regime measures read, per config."""
    import yaml

    cfg = yaml.safe_load((db.REPO / "config" / "rules" / "features.yaml").read_text())
    symbol = cfg.get("market", {}).get("index_symbol", "VNINDEX")
    return load(conn, symbol, start)
