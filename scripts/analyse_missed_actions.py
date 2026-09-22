"""Did CafeF miss a corporate action, or is the move real?

A price move beyond the daily limit with no change in the adjustment factor has
two possible explanations:

  - the move is real (a resumption, a first day, a reference-price reset), or
  - a corporate action happened and CafeF did not adjust for it.

The second kind is dangerous in a way the first is not: it puts a gap in the
adjusted series that never happened in the market, and a pattern will fire on it.

The second source settles it. vnstock returns ADJUSTED prices, so if vnstock's
series is continuous across the same date while ours gaps, the event was real and
CafeF missed it. If BOTH gap, the move actually happened.

Scope: the liquid universe, prices at or above 10,000 VND, excluding first days
and resumptions -- the cases where the answer changes what we would recommend.

Run:  uv run python scripts/analyse_missed_actions.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import checks, db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
CONFIG = REPO / "config" / "rules" / "universe.yaml"
DELAY = 1.3

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def main() -> None:
    db.load_env()
    cfg = yaml.safe_load(CONFIG.read_text())["liquidity"]
    say(f"Missed-corporate-action analysis   {datetime.now():%Y-%m-%d %H:%M}")

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT build_id FROM adjustment_build WHERE status='good' "
            "ORDER BY build_id DESC LIMIT 1"
        )
        (build,) = cur.fetchone()

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
            (
                int(cfg["lookback_days"] * 1.5),
                cfg["min_avg_matched_value"],
                cfg["min_trading_days_in_lookback"],
            ),
        )

        # Candidates, plus the move measured on the ADJUSTED series, which is
        # what the comparison is actually about.
        cur.execute(
            f"""
            WITH moves AS (
                SELECT r.symbol, r.trade_date, r.exchange,
                       lag(r.close) OVER w AS prev_close,
                       r.close / lag(r.close) OVER w - 1 AS raw_move,
                       a.close / lag(a.close) OVER w - 1 AS adj_move,
                       lag(r.trade_date) OVER w AS prev_date,
                       f.factor, lag(f.factor) OVER w AS prev_factor,
                       row_number() OVER w AS n
                FROM bar_raw r
                JOIN adjustment_factor f
                  ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                 AND f.build_id = %s
                JOIN bar_adjusted a
                  ON a.symbol = r.symbol AND a.trade_date = r.trade_date
                 AND a.build_id = %s
                WHERE r.trade_date >= DATE '2012-01-01'
                WINDOW w AS (PARTITION BY r.symbol ORDER BY r.trade_date)
            )
            SELECT m.symbol, m.trade_date, m.prev_close, m.raw_move, m.adj_move,
                   ({checks.limit_sql()}) AS limit_in_force
            FROM moves m JOIN liquid l USING (symbol)
            WHERE m.raw_move IS NOT NULL AND m.prev_close >= 10
              AND abs(m.raw_move) > ({checks.limit_sql()})
                  + ({checks.tick_sql("prev_close")}) / m.prev_close
              AND abs(m.factor - m.prev_factor) < 0.000001
              AND m.n > 2
              AND m.prev_date >= m.trade_date - INTERVAL '10 days'
            ORDER BY m.symbol, m.trade_date
            """,
            (build, build),
        )
        rows = cur.fetchall()

    say(f"candidates (liquid, >=10,000 VND, not first-day/resumption): {len(rows)}")
    say("")

    from vnstock import Quote

    missed, real, unchecked = [], [], []
    cache: dict[tuple, pd.DataFrame] = {}
    for symbol, d, _prev_close, _raw_move, adj_move, limit in rows:
        key = (symbol, d.year)
        if key not in cache:
            time.sleep(DELAY)
            try:
                cache[key] = Quote(source="vci", symbol=symbol).history(
                    start=str(d - pd.Timedelta(days=20)),
                    end=str(d + pd.Timedelta(days=20)),
                    interval="1D",
                )
            except Exception:  # noqa: BLE001
                cache[key] = pd.DataFrame()
        ref = cache[key]
        if ref.empty:
            unchecked.append((symbol, d, "no reference data"))
            continue
        ref = ref.copy()
        ref["d"] = pd.to_datetime(ref["time"]).dt.date
        ref = ref.sort_values("d").reset_index(drop=True)
        idx = ref.index[ref["d"] == d]
        if len(idx) == 0 or idx[0] == 0:
            unchecked.append((symbol, d, "reference has no bar on that date"))
            continue
        i = idx[0]
        ref_move = ref.loc[i, "close"] / ref.loc[i - 1, "close"] - 1

        # If the reference's ADJUSTED series is continuous across the date while
        # ours gaps, CafeF did not adjust for an event that happened.
        if abs(ref_move) <= float(limit) + 0.005 < abs(float(adj_move)):
            missed.append((symbol, d, float(adj_move), float(ref_move)))
        else:
            real.append((symbol, d, float(adj_move), float(ref_move)))

    say(f"CafeF missed a corporate action : {len(missed)}")
    say(f"move is real (both sources gap) : {len(real)}")
    say(f"unchecked                       : {len(unchecked)}")

    if missed:
        say("")
        say("5 examples of 'CafeF missed a corporate action':")
        say(f"  {'sym':<5}{'date':<12}{'our adj move':>14}{'vnstock adj move':>18}")
        for sym, d, ours, theirs in sorted(missed, key=lambda r: -abs(r[2]))[:5]:
            say(f"  {sym:<5}{str(d):<12}{ours:>13.1%}{theirs:>17.1%}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    cols = ["symbol", "trade_date", "our_move", "ref_move"]
    pd.DataFrame(missed, columns=cols).to_csv(
        REPORTS / "missed-corporate-actions.csv", index=False
    )
    path = REPORTS / f"missed-actions-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
