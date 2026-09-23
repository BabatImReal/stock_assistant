"""Fill the index sessions CafeF lost, from vnstock, where it is safe to.

A session in trading_day with no index row NaNs every regime window crossing
it (features/market.py), so one lost day costs ~50 sessions of regime data for
every symbol. scripts/investigate_index_gaps.py tells the causes apart; this
fills only the INDEX-GAP kind, and decides it per date with two guards:

1. vnstock volume > 0 that day. A halt shows up in vnstock as a row at the
   previous close with volume 0 (HOSE, 2018-01-23/24). That is not a session
   to fill, it is a session that did not happen on that exchange.
2. vnstock agrees with CafeF on close for the NEIGHBOUR_SESSIONS either side,
   within the reconciliation PRICE_TOLERANCE. A source that disagrees next door
   is not trusted for the day in between.

Rows go in with source='vnstock' (migration 006). Idempotent: an existing row
is never overwritten.

Run:  uv run python scripts/backfill_index_gaps.py [--dry-run]
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd  # noqa: E402

from vnstock_research.data import db  # noqa: E402
from vnstock_research.data.reconcile import PRICE_TOLERANCE  # noqa: E402

OURS, THEIRS = "VNINDEX", "VNINDEX"  # the index the regime measures read
NEIGHBOUR_SESSIONS = 5  # either side; a diagnostic guard, not a research parameter


def main() -> None:
    dry = "--dry-run" in sys.argv
    db.load_env()
    from vnstock import Quote

    with db.connect() as conn:
        # Same definition as the index_covers_every_trading_session check.
        missing = [
            r[0]
            for r in conn.execute(
                """
            SELECT DISTINCT c.trade_date FROM trading_day c
            WHERE c.trade_date >= DATE '2012-01-01' AND NOT EXISTS (
                SELECT 1 FROM index_bar b
                WHERE b.symbol = %s AND b.trade_date = c.trade_date)
            ORDER BY 1
            """,
                (OURS,),
            ).fetchall()
        ]
        print(f"{OURS} sessions missing since 2012: {len(missing)}")
        if not missing:
            return
        ours = (
            pd.DataFrame(
                conn.execute(
                    "SELECT trade_date, close FROM index_bar WHERE symbol = %s "
                    "ORDER BY trade_date",
                    (OURS,),
                ).fetchall(),
                columns=["trade_date", "close"],
            )
            .set_index("trade_date")["close"]
            .astype(float)
        )

        filled = 0
        for d in missing:
            # One small window per date: vnstock caps a request's span (8 years,
            # knowledge/data-sources.md), so a 2012-to-now request comes back
            # silently truncated.
            v = Quote(source="vci", symbol=THEIRS).history(
                start=str(d - timedelta(days=30)),
                end=str(d + timedelta(days=30)),
                interval="1D",
            )
            v["trade_date"] = pd.to_datetime(v["time"]).dt.date
            v = v.set_index("trade_date")
            if d not in v.index or v.at[d, "volume"] <= 0:
                print(f"  {d}  SKIP: vnstock has no traded session (halt?)")
                continue
            before = ours[ours.index < d].tail(NEIGHBOUR_SESSIONS)
            after = ours[ours.index > d].head(NEIGHBOUR_SESSIONS)
            both = pd.concat([before, after])
            both = both[both.index.isin(v.index)]
            diff = (both / v.loc[both.index, "close"] - 1).abs()
            if len(both) < 2 * NEIGHBOUR_SESSIONS or diff.max() > PRICE_TOLERANCE:
                print(
                    f"  {d}  SKIP: neighbours do not reconcile "
                    f"(n={len(both)}, max diff {diff.max():.4%})"
                )
                continue
            r = v.loc[d]
            print(
                f"  {d}  FILL close {r['close']} (neighbours n={len(both)}, "
                f"max diff {diff.max():.4%})"
            )
            if not dry:
                conn.execute(
                    "INSERT INTO index_bar (symbol, trade_date, open, high, low, "
                    "close, volume, source) VALUES (%s,%s,%s,%s,%s,%s,%s,'vnstock') "
                    "ON CONFLICT DO NOTHING",
                    (
                        OURS,
                        d,
                        r["open"],
                        r["high"],
                        r["low"],
                        r["close"],
                        int(r["volume"]),
                    ),
                )
                filled += 1
        conn.commit()
        print(f"filled {filled}" + (" (dry run)" if dry else ""))


if __name__ == "__main__":
    main()
