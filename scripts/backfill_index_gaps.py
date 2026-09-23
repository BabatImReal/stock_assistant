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

--stale: REPAIR stale copies instead (found 2026-09-23). CafeF sometimes
publishes a session with the OHLC of the session next to it: 2026-07-31
carried 07-30's prices for both indices; HNX-INDEX 2023-05-08 carried 05-09's.
The pair's rows are identical, so which one is wrong needs outside evidence.
Each row of every repeated pair since 2012 is replaced ONLY when all of these
hold:
  - vnstock VCI and KBS (two independent feeds) both have a traded session
    that day and agree with each other within PRICE_TOLERANCE;
  - our open/high/low/close differs from VCI by more than PRICE_TOLERANCE
    (all four prices: a stale close can sit inside tolerance while the open
    is 1.5% off, as 2023-05-08 did);
  - our neighbours reconcile with VCI (the same guard as the gap fill).
The replacement is VCI's row, marked source='vnstock'.

Run:  uv run python scripts/backfill_index_gaps.py [--stale] [--dry-run]
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
# --stale repairs both indices: a stale row is wrong wherever it sits.
INDICES = {"VNINDEX": "VNINDEX", "HNX-INDEX": "HNXINDEX"}
PRICES = ["open", "high", "low", "close"]
NEIGHBOUR_SESSIONS = 5  # either side; a diagnostic guard, not a research parameter


def vnstock_window(source: str, symbol: str, d) -> pd.DataFrame:
    """One small window around `d`: vnstock caps a request's span (8 years,
    knowledge/data-sources.md), so a 2012-to-now request comes back truncated."""
    from vnstock import Quote

    v = Quote(source=source, symbol=symbol).history(
        start=str(d - timedelta(days=30)), end=str(d + timedelta(days=30)),
        interval="1D",
    )
    v["trade_date"] = pd.to_datetime(v["time"]).dt.date
    return v.set_index("trade_date")


def repair_stale(conn, dry: bool) -> None:
    """See the module docstring, --stale."""
    rows = conn.execute(
        """
        SELECT symbol, trade_date FROM (
            SELECT symbol, trade_date, open, high, low, close,
                   lag(open) OVER w po, lag(high) OVER w ph,
                   lag(low) OVER w pl, lag(close) OVER w pc,
                   lag(trade_date) OVER w prev_date
            FROM index_bar WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
        ) i
        WHERE trade_date >= DATE '2012-01-01'
          AND open = po AND high = ph AND low = pl AND close = pc
        """
    ).fetchall()
    # Both rows of each pair are candidates; the evidence decides which is wrong.
    cands = set()
    for sym, d in rows:
        (prev,) = conn.execute(
            "SELECT max(trade_date) FROM index_bar WHERE symbol=%s AND trade_date<%s",
            (sym, d),
        ).fetchone()
        cands |= {(sym, prev), (sym, d)}
    print(f"repeated index sessions since 2012: {len(rows)}; "
          f"rows to judge: {len(cands)}")
    fixed = 0
    for sym, d in sorted(cands, key=lambda x: (x[1], x[0])):
        ours = pd.DataFrame(
            conn.execute(
                "SELECT trade_date, open, high, low, close FROM index_bar "
                "WHERE symbol = %s AND trade_date BETWEEN %s AND %s "
                "ORDER BY trade_date",
                (sym, d - timedelta(days=30), d + timedelta(days=30)),
            ).fetchall(),
            columns=["trade_date", *PRICES],
        ).set_index("trade_date").astype(float)
        vci = vnstock_window("vci", INDICES[sym], d)
        kbs = vnstock_window("kbs", INDICES[sym], d)
        if d not in vci.index or d not in kbs.index or vci.at[d, "volume"] <= 0:
            print(f"  {sym} {d}  SKIP: not a traded session in both feeds")
            continue
        feeds_agree = abs(vci.at[d, "close"] / kbs.at[d, "close"] - 1)
        ours_off = (ours.loc[d, PRICES] / vci.loc[d, PRICES] - 1).abs().max()
        pair = {x for s2, x in cands if s2 == sym and abs((x - d).days) <= 5}
        nb = ours[~ours.index.isin(pair)]
        nb = pd.concat([nb[nb.index < d].tail(NEIGHBOUR_SESSIONS),
                        nb[nb.index > d].head(NEIGHBOUR_SESSIONS)])
        nb = nb[nb.index.isin(vci.index)]
        nb_off = (nb["close"] / vci.loc[nb.index, "close"] - 1).abs().max()
        verdict = (
            "KEEP: matches VCI" if ours_off <= PRICE_TOLERANCE
            else "SKIP: VCI and KBS disagree" if feeds_agree > PRICE_TOLERANCE
            else "SKIP: neighbours do not reconcile" if nb_off > PRICE_TOLERANCE
            else "REPLACE"
        )
        print(f"  {sym} {d}  ours off VCI by {ours_off:.2%} (OHLC max); "
              f"VCI vs KBS close {feeds_agree:.3%}; neighbours {nb_off:.3%} "
              f"-> {verdict}")
        if verdict == "REPLACE" and not dry:
            r = vci.loc[d]
            conn.execute(
                "UPDATE index_bar SET open=%s, high=%s, low=%s, close=%s, "
                "volume=%s, source='vnstock' WHERE symbol=%s AND trade_date=%s",
                (r["open"], r["high"], r["low"], r["close"], int(r["volume"]),
                 sym, d),
            )
            fixed += 1
    conn.commit()
    print(f"replaced {fixed}" + (" (dry run)" if dry else ""))


def main() -> None:
    dry = "--dry-run" in sys.argv
    db.load_env()
    if "--stale" in sys.argv:
        with db.connect() as conn:
            repair_stale(conn, dry)
        return
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
