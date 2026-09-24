"""How often do the G3 fillability rules actually bite?

The definition rejects an entry when day t+1 opens at the ceiling, and defers an
exit when the exit day closes at the floor. Both are obviously right in
principle; what matters is whether they remove a rounding error or a meaningful
slice of the sample. This measures it before any statistic is built on top.

Ceiling and floor are judged on RAW prices by `checks.limits_sql`, the same
definition as the gate and the backtest (B1): the limit in force for the
exchange in force that day, rounded to the tick, the first-day band on a
resumption counted in sessions; "at the ceiling" = within half a tick.

Run:  uv run python scripts/measure_fillability.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.backtest import forward_returns as fr  # noqa: E402
from vnstock_research.data import checks, db, exchanges  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
UNIVERSE = REPO / "config" / "rules" / "universe.yaml"

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def main() -> None:
    cfg = yaml.safe_load(UNIVERSE.read_text())["liquidity"]
    say(f"G3 fillability measurement   {datetime.now():%Y-%m-%d %H:%M}")
    say("ceiling/floor: checks.limits_sql (tick-rounded; within half a tick)")
    say("")

    with db.connect() as conn, conn.cursor() as cur:
        # The recreated container's /dev/shm is small; a parallel hash join
        # over the whole market can exhaust it.
        cur.execute("SET max_parallel_workers_per_gather = 0")
        cur.execute(
            """
            CREATE TEMP TABLE liquid AS
            SELECT symbol FROM (
                SELECT r.symbol, avg(r.close * r.matched_volume) v, count(*) d
                FROM bar_raw r
                WHERE r.trade_date >= (SELECT max(trade_date) FROM bar_raw)
                                      - make_interval(days => %s::int)
                  AND r.matched_volume > 0
                GROUP BY 1
            ) x WHERE v >= %s AND d >= %s
            """,
            (int(cfg["lookback_days"] * 1.5), cfg["min_avg_matched_value"],
             cfg["min_trading_days_in_lookback"]),
        )

        # One pass over the research window, flagging each bar.
        cur.execute(
            f"""
            CREATE TEMP TABLE flagged AS
            WITH sessions AS (
                SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS s
                FROM (SELECT DISTINCT trade_date FROM trading_day) cal
            ),
            b AS (
                SELECT r.symbol, r.trade_date,
                       coalesce(xm.exchange, r.exchange) AS exchange,
                       r.open, r.close,
                       lag(r.close) OVER w AS prev_close,
                       s.s - lag(s.s) OVER w - 1 AS skipped
                FROM bar_raw r
                LEFT JOIN sessions s ON s.trade_date = r.trade_date
                {exchanges.RESOLVE_JOIN_SQL}
                WHERE r.trade_date >= DATE '2012-01-01'
                  AND NOT r.is_adjusted_source AND NOT r.date_shifted
                WINDOW w AS (PARTITION BY r.symbol ORDER BY r.trade_date)
            )
            SELECT symbol, trade_date, prev_close, rate AS lim,
                   -- checks.at_ceiling / at_floor: within half a tick
                   open >= ceiling - ceiling_tick / 2 AS opens_at_ceiling,
                   close <= floor + floor_tick / 2 AS closes_at_floor
            FROM ({checks.limits_sql("SELECT * FROM b WHERE prev_close > 0")}) m
            """
        )

        cur.execute("SELECT count(*) FROM flagged")
        (total,) = cur.fetchone()
        cur.execute(
            """
            SELECT
              count(*) FILTER (WHERE opens_at_ceiling),
              count(*) FILTER (WHERE closes_at_floor),
              count(*) FILTER (WHERE opens_at_ceiling
                               AND symbol IN (SELECT symbol FROM liquid)),
              count(*) FILTER (WHERE closes_at_floor
                               AND symbol IN (SELECT symbol FROM liquid)),
              count(*) FILTER (WHERE symbol IN (SELECT symbol FROM liquid))
            FROM flagged
            """
        )
        ceil_all, floor_all, ceil_liq, floor_liq, total_liq = cur.fetchone()

        say(f"bars examined since 2012: {total:,}  (liquid universe {total_liq:,})")
        say("")
        say("ENTRY rule -- reject when day t+1 opens at the ceiling")
        say(f"  whole market : {ceil_all:,} bars = {ceil_all / total:.3%}")
        say(f"  liquid       : {ceil_liq:,} bars = {ceil_liq / total_liq:.3%}")
        say("")
        say("EXIT rule -- defer when the exit day closes at the floor")
        say(f"  whole market : {floor_all:,} bars = {floor_all / total:.3%}")
        say(f"  liquid       : {floor_liq:,} bars = {floor_liq / total_liq:.3%}")

        # How long would a deferral last? Count consecutive floor closes, which
        # is what decides whether the cap of 5 sessions ever binds.
        cur.execute(
            """
            WITH runs AS (
                SELECT symbol, trade_date, closes_at_floor,
                       row_number() OVER w
                         - row_number() OVER (PARTITION BY symbol, closes_at_floor
                                              ORDER BY trade_date) AS grp
                FROM flagged
                WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
            )
            SELECT len, count(*) FROM (
                SELECT symbol, grp, count(*) AS len
                FROM runs WHERE closes_at_floor GROUP BY symbol, grp
            ) t GROUP BY len ORDER BY len
            """
        )
        runs = cur.fetchall()
        say("")
        say("consecutive floor-close runs (how far an exit would be pushed):")
        capped = 0
        for length, n in runs:
            note = ""
            if length > fr.MAX_EXIT_DEFERRAL:
                capped += n
                note = "  <- exceeds the cap, setup dropped"
            say(f"  {length:>3} session(s): {n:>7,}{note}")
        say("")
        say(f"runs exceeding the {fr.MAX_EXIT_DEFERRAL}-session cap: {capped:,}")

        costs = fr.load_costs()
        say("")
        say(f"costs: round trip {costs.round_trip:.2%}"
            f"{' (broker fee PROVISIONAL)' if costs.provisional else ''}")
        say(f"  a +2.0% gross move nets {fr.net_return(0.02, costs):.2%}")
        say(f"  break-even gross move is {fr.net_return(0, costs) * -1:.2%}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"fillability-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
