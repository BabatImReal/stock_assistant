"""Backfill the pre-transfer history CafeF dropped, for liquid symbols only.

Blocker G4: when a company moves exchange, CafeF keeps only the history on its
current venue. ACB appears in the HOSE file from 2020-12-14 and its nine years on
HNX are in no bulk file at all. 251 symbols are affected; 47 of them are liquid.

Only the liquid ones are backfilled (Ben, 2026-09-22): an illiquid symbol cannot
be recommended, so its missing years cost nothing and would cost hours of a free
service's rate limit.

The flags matter more than the data. vnstock returns ADJUSTED prices only, so for
a backfilled span:

  - there is no unadjusted price, so no factor can be derived,
  - so the volume cannot be adjusted (blocker G1),
  - so the span is usable for PRICE-based patterns and trend, and
    volume-based signals must skip it.

That is carried by bar_raw.is_adjusted_source and bar_adjusted.volume_is_adjustable
rather than written down somewhere and remembered.

The factor for these rows is stored as exactly 1 with source 'vnstock': the price
is already adjusted, so no further adjustment applies, and the row still joins
cleanly when bar_adjusted is built.

Run:  uv run python scripts/backfill_transfers.py
"""

from __future__ import annotations

import io
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
UNIVERSE = REPO / "config" / "rules" / "universe.yaml"
DELAY = 1.2
# Wide on purpose: the transfer probe asked a 3-year window, so its gap sizes are
# lower bounds. Starting at 2000 measures the real gap instead of re-clamping it.
BACKFILL_START = "2000-01-01"
CHUNK_YEARS = 4  # never one long request: the 8-year cap is stateful

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def windows(start: str, end: str) -> list[tuple[str, str]]:
    lo, stop, res = pd.Timestamp(start), pd.Timestamp(end), []
    while lo < stop:
        hi = min(lo + pd.DateOffset(years=CHUNK_YEARS) - pd.Timedelta(days=1), stop)
        res.append((str(lo.date()), str(hi.date())))
        lo = hi + pd.Timedelta(days=1)
    return res


def main() -> None:
    db.load_env()
    say(f"Class B backfill   {datetime.now():%Y-%m-%d %H:%M}")

    transfers = pd.read_csv(REPORTS / "g4-transfer-check.csv")
    transfers = transfers[transfers["rows"] > 0]
    ucfg = yaml.safe_load(UNIVERSE.read_text())["liquidity"]

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                    int(ucfg["lookback_days"] * 1.5),
                    ucfg["min_avg_matched_value"],
                    ucfg["min_trading_days_in_lookback"],
                ),
            )
            liquid = {r[0] for r in cur.fetchall()}
            cur.execute(
                "SELECT symbol, min(trade_date), min(exchange) FROM bar_raw "
                "GROUP BY symbol"
            )
            first = {s: (d, e) for s, d, e in cur.fetchall()}
            cur.execute(
                "SELECT build_id FROM adjustment_build WHERE status='good' "
                "ORDER BY build_id DESC LIMIT 1"
            )
            (build,) = cur.fetchone()

        todo = sorted(set(transfers["symbol"]) & liquid)
        say(f"liquid Class B symbols to backfill: {len(todo)}  (build {build})")
        say("")

        from vnstock import Quote

        loaded, skipped, gaps = 0, [], []
        bad_ohlc = 0
        for i, symbol in enumerate(todo, 1):
            cafef_first, exchange = first[symbol]
            parts = []
            for lo, hi in windows(BACKFILL_START, str(cafef_first)):
                time.sleep(DELAY)
                try:
                    parts.append(
                        Quote(source="vci", symbol=symbol).history(
                            start=lo, end=hi, interval="1D"
                        )
                    )
                except Exception:  # noqa: BLE001 - empty window, not a failure
                    pass
            if not parts:
                skipped.append((symbol, "no data"))
                continue

            df = pd.concat(parts, ignore_index=True)
            df["trade_date"] = pd.to_datetime(df["time"]).dt.date
            # Only what CafeF does NOT have. Never overwrite the primary source.
            df = df[df["trade_date"] < cafef_first].drop_duplicates("trade_date")
            # The reference source has the same defect CafeF does: bars whose
            # close sits outside their own high-low range. The database CHECK
            # rejects them, and rightly so -- such a bar cannot be drawn, let
            # alone matched against a pattern. Filtered and counted here.
            ok = (
                (df[["open", "high", "low", "close"]] > 0).all(axis=1)
                & (df["low"] <= df[["open", "close"]].min(axis=1))
                & (df["high"] >= df[["open", "close"]].max(axis=1))
                & (df["volume"] >= 0)
            )
            bad_ohlc += int((~ok).sum())
            df = df[ok]
            if df.empty:
                skipped.append((symbol, "nothing before the CafeF start"))
                continue

            df["symbol"] = symbol
            df["exchange"] = exchange  # the venue it trades on now; see note below
            df["source"] = "vnstock"
            df["is_adjusted_source"] = True
            df["source_file"] = "vnstock:vci"
            df["date_shifted"] = False
            df["matched_volume"] = df["volume"].astype("int64")

            buf = io.StringIO()
            cols = ["symbol", "trade_date", "open", "high", "low", "close",
                    "matched_volume", "exchange", "source", "is_adjusted_source",
                    "source_file", "date_shifted"]
            df[cols].to_csv(buf, index=False, header=False)
            buf.seek(0)
            with conn.cursor() as cur:
                with cur.copy(
                    f"COPY bar_raw ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv)"
                ) as cp:
                    cp.write(buf.read())
                # factor = 1: the price is already adjusted, so nothing further
                # applies, and the row still joins when bar_adjusted is built.
                cur.execute(
                    """
                    INSERT INTO adjustment_factor
                        (symbol, trade_date, build_id, factor, source)
                    SELECT symbol, trade_date, %s, 1.0, 'vnstock'
                    FROM bar_raw WHERE symbol = %s AND source = 'vnstock'
                    ON CONFLICT DO NOTHING
                    """,
                    (build, symbol),
                )
                cur.execute(
                    "UPDATE symbol SET has_backfill = true WHERE symbol = %s",
                    (symbol,),
                )
                cur.execute(
                    """
                    INSERT INTO symbol_exchange
                        (symbol, exchange, valid_from, valid_to, source)
                    VALUES (%s, %s, %s, %s, 'vnstock')
                    ON CONFLICT DO NOTHING
                    """,
                    (symbol, exchange, df["trade_date"].min(),
                     df["trade_date"].max()),
                )
            conn.commit()
            loaded += 1
            gaps.append((symbol, df["trade_date"].min(), cafef_first, len(df)))
            if i % 10 == 0:
                say(f"  {i}/{len(todo)} done")

        # Rebuild the adjusted bars for the backfilled symbols only.
        if loaded:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bar_adjusted (symbol, trade_date, build_id,
                        open, high, low, close, matched_volume,
                        volume_is_adjustable)
                    SELECT r.symbol, r.trade_date, %s,
                           r.open * f.factor, r.high * f.factor,
                           r.low * f.factor, r.close * f.factor,
                           r.matched_volume / f.factor,
                           NOT r.is_adjusted_source
                    FROM bar_raw r
                    JOIN adjustment_factor f
                      ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                     AND f.build_id = %s
                    WHERE r.source = 'vnstock'
                    ON CONFLICT DO NOTHING
                    """,
                    (build, build),
                )
            conn.commit()
            # New bar_raw rows change the calendar's per-exchange counts.
            db.rebuild_trading_day(conn)

    say("")
    say(f"backfilled: {loaded} symbols, skipped: {len(skipped)}")
    say(f"bars rejected as internally inconsistent OHLC: {bad_ohlc:,}")
    if gaps:
        g = pd.DataFrame(gaps, columns=["symbol", "recovered_from",
                                        "cafef_first", "bars"])
        g["years"] = (
            pd.to_datetime(g["cafef_first"]) - pd.to_datetime(g["recovered_from"])
        ).dt.days / 365
        say(f"bars added: {g['bars'].sum():,}   "
            f"median gap recovered: {g['years'].median():.1f} years")
        say("")
        say("TRUE gap sizes (the 3-year probe window under-reported these):")
        say(f"  {'sym':<6}{'recovered from':<16}{'cafef starts':<15}{'years':>7}"
            f"{'bars':>8}")
        for r in g.nlargest(10, "years").itertuples():
            say(f"  {r.symbol:<6}{str(r.recovered_from):<16}"
                f"{str(r.cafef_first):<15}{r.years:>7.1f}{r.bars:>8,}")
        g.to_csv(REPORTS / "backfill-gaps.csv", index=False)
    if skipped:
        say("")
        say(f"skipped: {', '.join(s for s, _ in skipped[:15])}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"backfill-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
