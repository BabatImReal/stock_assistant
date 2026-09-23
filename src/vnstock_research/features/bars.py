"""Loading one symbol's bars into the frame measures read.

Every measure is a pure function of this frame, so everything they need to obey
the rules has to be IN the frame: not just prices and volume, but whether the
row sits after a trading gap, whether it falls inside an excluded window, and
whether its volume is comparable with its neighbours'.

Three decisions worth stating, because each is a correctness matter rather than
a convenience:

1. **One build only.** `bar_adjusted` is build-scoped, and a build is a
   consistent set of adjustment factors. Reading across builds would splice two
   different adjustment policies into one series -- the exact defect the build
   mechanism exists to prevent. The loader takes the current PROMOTED good
   build and nothing else.

2. **Adjusted volume, not raw.** A 20-session relative-volume window that spans
   a stock dividend needs a consistent share basis on both sides of it. That is
   what the inverse-factor adjustment provides (blocker G1): price x factor,
   volume ÷ factor. Raw volume would make every window containing an event
   wrong in a way no threshold can repair.

3. **`gap_before` counts SESSIONS, not days.** A weekend is not a gap; a
   three-week suspension is. The trading calendar (built from stock rows, never
   from the index -- blocker G14) is what tells the two apart.
"""

from __future__ import annotations

import pandas as pd

COLUMNS = [
    "symbol", "trade_date", "open", "high", "low", "close",
    "matched_volume", "volume_is_adjustable", "gap_before", "excluded",
]


def current_build(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT build_id FROM adjustment_build WHERE status = 'good' "
            "ORDER BY build_id DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError("no promoted build; run scripts/run_checks.py")
    return row[0]


_SQL = """
WITH cal AS (
    SELECT DISTINCT trade_date FROM trading_day WHERE trade_date >= %(start)s
),
sessions AS (
    SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS n FROM cal
),
b AS (
    SELECT a.symbol, a.trade_date, a.open, a.high, a.low, a.close,
           a.matched_volume, a.volume_is_adjustable, s.n AS session_no
    FROM bar_adjusted a
    JOIN sessions s ON s.trade_date = a.trade_date
    WHERE a.build_id = %(build)s
      AND a.symbol = %(symbol)s
      AND a.trade_date >= %(start)s
)
SELECT b.symbol, b.trade_date, b.open, b.high, b.low, b.close,
       b.matched_volume, b.volume_is_adjustable,
       -- Sessions skipped since the previous row: 0 on consecutive sessions,
       -- positive after a suspension or a halt.
       b.session_no - lag(b.session_no) OVER (ORDER BY b.trade_date) - 1
           AS gap_before,
       EXISTS (
           SELECT 1 FROM excluded_window w
           WHERE w.symbol = b.symbol
             AND b.trade_date BETWEEN w.valid_from AND w.valid_to
       ) AS excluded
FROM b
ORDER BY b.trade_date
"""


def load(conn, symbol: str, start: str = "2012-01-01", build: int | None = None):
    """One symbol's bars, ready for measures. Oldest first."""
    build_id = build if build is not None else current_build(conn)
    with conn.cursor() as cur:
        cur.execute(_SQL, {"build": build_id, "symbol": symbol.upper(), "start": start})
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=COLUMNS)
    for col in ("open", "high", "low", "close", "matched_volume"):
        df[col] = df[col].astype("float64")
    # The first row has no predecessor, so there is no gap before it -- not an
    # unknown one. Leaving it NaN would make every first window unusable.
    df["gap_before"] = df["gap_before"].fillna(0).astype("int64")
    return df.reset_index(drop=True)


def load_many(conn, symbols, start: str = "2012-01-01", build: int | None = None):
    build_id = build if build is not None else current_build(conn)
    for symbol in symbols:
        yield symbol, load(conn, symbol, start=start, build=build_id)


def liquid_symbols(conn, limit: int | None = None) -> list[str]:
    """The symbols liquid on the LATEST session, most traded first. For reporting.

    NOT a research filter: research uses the liquid set on EACH historical date
    (`data.universe.liquid`), because today's list silently selects the stocks
    that turned out well (decision 2026-09-22). One definition serves both;
    it lives in data/universe.py.
    """
    from ..data import universe

    symbols = list(universe.liquid_on_latest(conn).index)
    return symbols[:limit] if limit else symbols
