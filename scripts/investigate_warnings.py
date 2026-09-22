"""Investigate the data-quality warnings from build 2 before building the nightly job.

Three questions from Ben:
  (a) What are the 8,213 moves beyond the price limit with no factor change?
  (b) Why do 68 symbols have a latest factor != 1, and does that break the
      nightly factor-change detection?
  (c) How many of the other warnings fall inside the LIQUID universe since 2012?

Question (c) is the one that decides how much any of this matters. A defect on a
stock nobody could buy is not the same as a defect on one that could be
recommended tomorrow, so every count is reported twice: whole market, and
liquid universe.

Run:  uv run python scripts/investigate_warnings.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
CONFIG = REPO / "config" / "rules" / "universe.yaml"

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


LIQUID_VIEW = """
-- A TABLE, not a VIEW: a view definition cannot carry bind parameters, and
-- the thresholds come from config rather than being inlined into the SQL.
CREATE TEMP TABLE liquid AS
SELECT symbol
FROM (
    SELECT r.symbol,
           avg(r.close * r.matched_volume) AS avg_value,
           count(*) AS days
    FROM bar_raw r
    -- lookback is in SESSIONS; roughly 1.5 calendar days per session covers
    -- weekends and holidays without needing the calendar table here.
    WHERE r.trade_date >= (SELECT max(trade_date) FROM bar_raw)
                          - make_interval(days => %s::int)
      AND r.matched_volume > 0
    GROUP BY r.symbol
) t
WHERE avg_value >= %s AND days >= %s
"""


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text())
    liq = cfg["liquidity"]
    start = cfg["universe"]["research_start"]

    say(f"Warning investigation   {datetime.now():%Y-%m-%d %H:%M}")
    say(
        f"liquid = avg matched value >= {liq['min_avg_matched_value']:,} "
        f"thousand VND over {liq['lookback_days']} sessions"
    )
    say("")

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            LIQUID_VIEW,
            (
                int(liq["lookback_days"] * 1.5),
                liq["min_avg_matched_value"],
                liq["min_trading_days_in_lookback"],
            ),
        )
        # The latest promoted build, not a hard-coded id: this script is meant
        # to be re-run after every load.
        cur.execute(
            "SELECT build_id FROM adjustment_build WHERE status = 'good' "
            "ORDER BY build_id DESC LIMIT 1"
        )
        (build,) = cur.fetchone()
        say(f"build_id = {build}")

        cur.execute("SELECT count(*) FROM liquid")
        (n_liquid,) = cur.fetchone()
        say(f"liquid universe: {n_liquid} symbols of 1,709")
        say("")

        # ------------------------------------------------------------------
        # (a) beyond-limit moves
        # ------------------------------------------------------------------
        say("=" * 70)
        say("(a) MOVES BEYOND THE PRICE LIMIT WITH NO FACTOR CHANGE")
        say("=" * 70)
        # Classify each one by what else was true that day. The classes are
        # mutually exclusive and applied in order, most-explaining first.
        cur.execute(
            """
            CREATE TEMP TABLE beyond AS
            WITH moves AS (
                SELECT r.symbol, r.trade_date, r.exchange, r.close,
                       lag(r.close)      OVER w AS prev_close,
                       lag(r.trade_date) OVER w AS prev_date,
                       r.close / lag(r.close) OVER w - 1 AS move,
                       f.factor,
                       lag(f.factor) OVER w AS prev_factor,
                       row_number()  OVER w AS n
                FROM bar_raw r
                JOIN adjustment_factor f
                  ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                 AND f.build_id = %s
                WHERE r.trade_date >= %s
                WINDOW w AS (PARTITION BY r.symbol ORDER BY r.trade_date)
            )
            SELECT * FROM moves
            WHERE move IS NOT NULL
              AND abs(move) > CASE exchange WHEN 'HOSE' THEN 0.09
                                            WHEN 'HNX'  THEN 0.12
                                            ELSE 0.17 END
              AND abs(factor - prev_factor) < 0.000001
            """,
            (build, start),
        )
        cur.execute("SELECT count(*) FROM beyond")
        (n_beyond,) = cur.fetchone()
        say(f"total since {start}: {n_beyond:,}")

        cur.execute(
            """
            SELECT CASE
                     WHEN n = 2 THEN 'first trading day (second bar)'
                     WHEN prev_date < trade_date - INTERVAL '10 days'
                       THEN 'resumption after a gap > 10 sessions'
                     WHEN abs(move) > 0.5
                       THEN 'likely unadjusted corporate action (move > 50%)'
                     ELSE 'unexplained'
                   END AS class,
                   count(*),
                   count(*) FILTER (WHERE symbol IN (SELECT symbol FROM liquid))
            FROM beyond GROUP BY 1 ORDER BY 2 DESC
            """
        )
        say("")
        say(f"{'class':<50}{'all':>9}{'liquid':>9}")
        for cls, n, nl in cur.fetchall():
            say(f"{cls:<50}{n:>9,}{nl:>9,}")

        cur.execute(
            "SELECT count(*) FROM beyond WHERE symbol IN (SELECT symbol FROM liquid)"
        )
        (n_beyond_liquid,) = cur.fetchone()
        say("")
        say(f"in the liquid universe: {n_beyond_liquid:,} of {n_beyond:,}")

        say("")
        say("5 examples of 'likely unadjusted corporate action':")
        cur.execute(
            """
            SELECT symbol, trade_date, prev_close, close, move,
                   symbol IN (SELECT symbol FROM liquid) AS is_liquid
            FROM beyond
            WHERE abs(move) > 0.5 AND n > 2
              AND prev_date >= trade_date - INTERVAL '10 days'
            ORDER BY abs(move) DESC LIMIT 5
            """
        )
        for sym, d, pc, c, mv, isliq in cur.fetchall():
            say(
                f"  {sym:<5} {d}  {float(pc):>9,.2f} -> {float(c):>9,.2f}"
                f"  {float(mv):+7.1%}  {'liquid' if isliq else ''}"
            )

        # The 'unexplained' class is the biggest, so it gets its own breakdown.
        # The obvious suspect is price level: at a 100 VND tick, a stock trading
        # at 0.6 (600 VND) moves 16.7% on ONE tick, so a percentage limit is
        # simply the wrong test down there.
        say("")
        say("breakdown of the 'unexplained' class by price level:")
        cur.execute(
            """
            SELECT CASE
                     WHEN prev_close < 1   THEN 'under 1,000 VND (1 tick > 10%)'
                     WHEN prev_close < 3   THEN '1,000-3,000 VND'
                     WHEN prev_close < 10  THEN '3,000-10,000 VND'
                     ELSE '10,000 VND and above'
                   END AS band,
                   count(*),
                   count(l.symbol),
                   round(avg(abs(move))::numeric, 3)
            FROM beyond b LEFT JOIN liquid l ON l.symbol = b.symbol
            WHERE NOT (n = 2)
              AND prev_date >= trade_date - INTERVAL '10 days'
              AND abs(move) <= 0.5
            GROUP BY 1 ORDER BY 2 DESC
            """
        )
        say(f"  {'price band':<34}{'all':>8}{'liquid':>8}{'avg move':>10}")
        for band, n, nl, avg in cur.fetchall():
            say(f"  {band:<34}{n:>8,}{nl:>8,}{float(avg):>9.1%}")

        # ------------------------------------------------------------------
        # (b) latest factor != 1
        # ------------------------------------------------------------------
        say("")
        say("=" * 70)
        say("(b) SYMBOLS WHOSE LATEST FACTOR != 1")
        say("=" * 70)
        cur.execute(
            """
            CREATE TEMP TABLE lastfac AS
            SELECT DISTINCT ON (f.symbol) f.symbol, f.trade_date, f.factor
            FROM adjustment_factor f WHERE f.build_id = 2
            ORDER BY f.symbol, f.trade_date DESC
            """
        )
        cur.execute("SELECT count(*) FROM lastfac WHERE abs(factor - 1) > 0.001")
        (n68,) = cur.fetchone()
        say(f"symbols affected: {n68}")

        # Is it the still-trading ones, or ones that stopped?
        cur.execute(
            """
            SELECT
              count(*) FILTER (WHERE s.is_active) AS active,
              count(*) FILTER (WHERE NOT s.is_active) AS inactive,
              count(*) FILTER (WHERE l.symbol IN (SELECT symbol FROM liquid)) AS liquid
            FROM lastfac l JOIN symbol s ON s.symbol = l.symbol
            WHERE abs(l.factor - 1) > 0.001
            """
        )
        a, i, lq = cur.fetchone()
        say(f"  still active: {a}    no longer trading: {i}    liquid: {lq}")

        cur.execute(
            """
            SELECT l.symbol, l.trade_date, l.factor, s.last_trade_date, s.is_active
            FROM lastfac l JOIN symbol s ON s.symbol = l.symbol
            WHERE abs(l.factor - 1) > 0.001
            ORDER BY abs(l.factor - 1) DESC LIMIT 8
            """
        )
        say("")
        say(
            f"  {'sym':<5}{'last factor date':<19}{'factor':>12}"
            f"{'last bar':<14}{'active'}"
        )
        for sym, fd, fac, lb, act in cur.fetchall():
            say(f"  {sym:<5}{str(fd):<19}{float(fac):>12.6f}  {str(lb):<14}{act}")

        # Does it break nightly factor-change detection? That detection compares
        # today's factor series against the stored one and treats any change on a
        # PAST day as a restatement. A latest factor != 1 only matters if it
        # moves; a stable wrong-looking value produces no false alarm.
        cur.execute(
            """
            SELECT count(*) FROM lastfac l
            WHERE abs(l.factor - 1) > 0.001
              AND l.trade_date < (SELECT max(trade_date) FROM bar_raw)
            """
        )
        (stale,) = cur.fetchone()
        say("")
        say(f"  of those, {stale} have their last factor on a date BEFORE the")
        say("  market's last session -- i.e. the symbol stopped trading, so the")
        say("  value is frozen and cannot generate a nightly false alarm.")

        # ------------------------------------------------------------------
        # (c) the other warnings, inside the liquid universe
        # ------------------------------------------------------------------
        say("")
        say("=" * 70)
        say("(c) OTHER WARNINGS, WHOLE MARKET vs LIQUID UNIVERSE (since 2012)")
        say("=" * 70)

        cur.execute(
            """
            WITH cal AS (
                SELECT DISTINCT trade_date FROM trading_day WHERE trade_date >= %s
            ), span AS (
                SELECT symbol, min(trade_date) lo, max(trade_date) hi
                FROM bar_raw WHERE trade_date >= %s
                GROUP BY symbol HAVING count(*) > 250
            ), transfer_gap AS (
                -- Class A stitching. 116 symbols moved exchange and CafeF kept
                -- both spans. The days between leaving one venue and joining
                -- the next are a real non-trading period, not missing data, so
                -- they must not be counted as gaps. Derived from
                -- symbol_exchange rather than stored: the spans already say it.
                SELECT e1.symbol, e1.valid_to AS gap_from, e2.valid_from AS gap_to
                FROM symbol_exchange e1
                JOIN symbol_exchange e2
                  ON e2.symbol = e1.symbol AND e2.valid_from > e1.valid_to
                WHERE NOT EXISTS (
                    SELECT 1 FROM symbol_exchange e3
                    WHERE e3.symbol = e1.symbol
                      AND e3.valid_from > e1.valid_to
                      AND e3.valid_from < e2.valid_from
                )
            ), gaps AS (
                SELECT s.symbol, count(*) AS missing
                FROM span s JOIN cal c ON c.trade_date BETWEEN s.lo AND s.hi
                LEFT JOIN bar_raw b
                       ON b.symbol = s.symbol AND b.trade_date = c.trade_date
                WHERE b.symbol IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM transfer_gap t
                      WHERE t.symbol = s.symbol
                        AND c.trade_date > t.gap_from AND c.trade_date < t.gap_to
                  )
                GROUP BY s.symbol HAVING count(*) > 20
            )
            SELECT count(*),
                   count(*) FILTER
                     (WHERE symbol IN (SELECT symbol FROM liquid)),
                   max(missing)
            FROM gaps
            """,
            (start, start),
        )
        n_gap, n_gap_liq, worst = cur.fetchone()
        say("symbols missing > 20 sessions (transfer gaps excused):")
        say(
            f"                                      {n_gap:>6,} all"
            f"   {n_gap_liq:>5,} liquid   (worst: {worst:,} sessions)"
        )

        cur.execute(
            "SELECT count(*) FROM trading_day WHERE symbols_traded < 20 "
            "AND trade_date >= %s",
            (start,),
        )
        (thin,) = cur.fetchone()
        cur.execute(
            "SELECT count(*) FROM trading_day WHERE symbols_traded < 20",
        )
        (thin_all,) = cur.fetchone()
        say(
            f"thin exchange-days (<20 symbols):     {thin_all:>6,} all"
            f"   {thin:>5,} since {start}"
        )
        cur.execute(
            "SELECT exchange, count(*) FROM trading_day WHERE symbols_traded < 20 "
            "AND trade_date >= %s GROUP BY exchange ORDER BY 2 DESC",
            (start,),
        )
        say(
            f"  by exchange since {start}: "
            + ", ".join(f"{e} {n:,}" for e, n in cur.fetchall())
        )

        # Bars rejected at load for a close outside high-low are not in the
        # database at all, so they are counted from the source in the report.
        # LEFT JOIN rather than a correlated subselect: the subselect form
        # tripped a parallel-worker planner error on this table.
        cur.execute(
            """
            SELECT count(*), count(l.symbol)
            FROM bar_raw b LEFT JOIN liquid l ON l.symbol = b.symbol
            WHERE b.date_shifted
            """
        )
        ds, ds_liq = cur.fetchone()
        say(f"date-shifted bars:                    {ds:>6,} all   {ds_liq:>5,} liquid")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"warning-investigation-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
