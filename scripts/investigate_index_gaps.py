"""Which sessions does the calendar have that the VN-Index does not -- and why.

READ-ONLY. It prints evidence and a hint; it changes nothing. The data-quality
check `index_covers_every_trading_session` counts these sessions (5 since 2012
when last run on 2026-09-22) but does not say which they are or why. The two
possible causes need OPPOSITE fixes, so fixing one blind is worse than leaving
it:

1. PHANTOM SESSION -- `trading_day` holds a date the market was closed. It is
   built as "any date with at least one stock row" (scripts/load_history.py),
   and the only calendar check rejects WEEKENDS, not weekday holidays (Tet,
   30/4, 2/9 ...). One stray row on a holiday -- a mis-dated CafeF bar, or one
   the date-shift repair moved onto a free date -- creates a session that
   nearly every symbol "missed". That inflates `gap_before` for every symbol
   whose window crosses it and needlessly NaNs those windows.
   Signature: very few symbols that day, often date-shifted or backfilled rows.
   Fix: the CALENDAR.

2. INDEX INGEST GAP -- the market traded normally and our index file lost the
   day. One known way this can happen: CafeF dates some whole sessions a day
   late (G14 found Saturday-dated stock sessions), and weekend INDEX rows are
   rejected at parse rather than shifted -- so a mis-dated Friday index row is
   dropped and Friday goes missing.
   Signature: a normal number of symbols that day.
   Fix: BACKFILL the index.

Run:  uv run python scripts/investigate_index_gaps.py [index_symbol] [start]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Diagnostic thresholds, NOT research parameters: they only choose which hint
# to print next to evidence a human reads anyway. A real session on a thin
# exchange-day still has hundreds of symbols across the market; a phantom one
# has a handful.
PHANTOM_SHARE = 0.20  # below 20% of the neighbouring sessions' symbol count
NORMAL_SHARE = 0.80  # at or above 80% reads as an ordinary session

_SQL = """
WITH cal AS (
    SELECT trade_date,
           sum(symbols_traded) AS n_all,
           string_agg(exchange || ' ' || symbols_traded, ', ' ORDER BY exchange)
               AS per_exchange
    FROM trading_day
    WHERE trade_date >= %(start)s
    GROUP BY trade_date
),
missing AS (
    SELECT c.*
    FROM cal c
    LEFT JOIN index_bar b
           ON b.trade_date = c.trade_date AND b.symbol = %(symbol)s
    WHERE b.trade_date IS NULL
)
SELECT
    m.trade_date,
    to_char(m.trade_date, 'Dy') AS weekday,
    m.n_all,
    m.per_exchange,
    -- The typical session around this date, so "few symbols" is judged
    -- against its own era rather than against today's market size.
    (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY c2.n_all)
       FROM cal c2
      WHERE c2.trade_date BETWEEN m.trade_date - 21 AND m.trade_date + 21
        AND c2.trade_date <> m.trade_date) AS neighbour_median,
    (SELECT count(*) FROM bar_raw r
      WHERE r.trade_date = m.trade_date AND r.date_shifted) AS n_date_shifted,
    (SELECT count(*) FROM bar_raw r
      WHERE r.trade_date = m.trade_date AND r.source <> 'cafef') AS n_backfilled,
    (SELECT count(*) FROM bar_raw r
      WHERE r.trade_date = m.trade_date AND r.matched_volume = 0) AS n_zero_volume,
    (SELECT string_agg(DISTINCT i.symbol, ',') FROM index_bar i
      WHERE i.trade_date = m.trade_date) AS other_indices,
    (SELECT max(i.trade_date) FROM index_bar i
      WHERE i.symbol = %(symbol)s AND i.trade_date < m.trade_date) AS prev_index,
    (SELECT min(i.trade_date) FROM index_bar i
      WHERE i.symbol = %(symbol)s AND i.trade_date > m.trade_date) AS next_index,
    -- Name the symbols when there are few: a phantom session is usually a
    -- handful of identifiable stray rows.
    (SELECT CASE WHEN count(*) <= 15
                 THEN string_agg(r.symbol || ':' || coalesce(r.source_file, '?'),
                                 ' ' ORDER BY r.symbol)
            END
       FROM bar_raw r WHERE r.trade_date = m.trade_date) AS rows_if_few
FROM missing m
ORDER BY m.trade_date
"""

COLUMNS = [
    "trade_date", "weekday", "n_all", "per_exchange", "neighbour_median",
    "n_date_shifted", "n_backfilled", "n_zero_volume", "other_indices",
    "prev_index", "next_index", "rows_if_few",
]


def classify(
    n_all: int, neighbour_median: float | None, n_date_shifted: int, n_backfilled: int
) -> str:
    """A HINT for one missing session. A human confirms it from the evidence.

    Order matters: a date whose every row was moved or backfilled onto it is a
    phantom however many rows there are, because none of them was reported by
    the exchange on that date in the first place.
    """
    if n_all > 0 and n_all - n_date_shifted - n_backfilled <= 0:
        return "PHANTOM: every row was date-shifted or backfilled onto it"
    if not neighbour_median:
        return "UNCLEAR: no neighbouring sessions to compare with"
    share = n_all / neighbour_median
    if share < PHANTOM_SHARE:
        return f"PHANTOM-LIKELY: {share:.0%} of a normal session's symbols"
    if share >= NORMAL_SHARE:
        return f"INDEX-GAP-LIKELY: normal session ({share:.0%}), index lacks it"
    return f"UNCLEAR: {share:.0%} of a normal session's symbols"


def main() -> None:
    from vnstock_research.data import db

    symbol = (sys.argv[1] if len(sys.argv) > 1 else "VNINDEX").upper()
    start = sys.argv[2] if len(sys.argv) > 2 else "2012-01-01"
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(_SQL, {"symbol": symbol, "start": start})
        rows = [dict(zip(COLUMNS, r, strict=True)) for r in cur.fetchall()]

    print(f"Sessions in trading_day since {start} with no {symbol} row: {len(rows)}")
    for r in rows:
        hint = classify(
            r["n_all"], r["neighbour_median"], r["n_date_shifted"], r["n_backfilled"]
        )
        print()
        print(f"{r['trade_date']} ({r['weekday']})  {hint}")
        print(f"  symbols: {r['n_all']:,} ({r['per_exchange']}); "
              f"neighbour median {r['neighbour_median']}")
        print(f"  date-shifted {r['n_date_shifted']}, backfilled {r['n_backfilled']}, "
              f"zero volume {r['n_zero_volume']}")
        print(f"  other index rows that day: {r['other_indices'] or 'none'}; "
              f"{symbol} before {r['prev_index']}, after {r['next_index']}")
        if r["rows_if_few"]:
            print(f"  rows: {r['rows_if_few']}")


if __name__ == "__main__":
    main()
