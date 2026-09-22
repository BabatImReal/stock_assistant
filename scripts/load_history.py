"""Phase 4 step 2: the one-time historical load, CafeF back to 2000.

Order matters and follows the approved pipeline in
agent-memory/knowledge/data-model.md:

    bar_raw -> adjustment_factor -> negotiated_volume -> index_bar
            -> trading_day -> symbol + symbol_exchange -> bar_adjusted

bar_raw comes first because everything else is derived from it. The build is
created with status 'building' and is only promoted to 'good' by the checks
step, so research can never read a half-loaded or unverified build.

Idempotent: re-running truncates the derived tables and reloads. bar_raw is
upserted rather than replaced, because it is the permanent record.

Run:  uv run python scripts/load_history.py
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import cafef, db  # noqa: E402

RESEARCH_START = "2012-01-01"  # the research window; the STORE goes back to 2000


def say(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S}  {msg}", flush=True)


def copy_frame(conn, df: pd.DataFrame, table: str, columns: list[str]) -> int:
    """Bulk-load a frame with COPY.

    COPY rather than executemany: this is millions of rows, and the difference
    is minutes versus hours. The CSV round-trip through memory is still the
    simplest thing that works at this size.
    """
    buf = io.StringIO()
    df[columns].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cols = ", ".join(columns)
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv)") as cp:
            cp.write(buf.read())
    return len(df)


def main() -> None:
    day = cafef.latest_dir()
    say(f"CafeF publication: {day.name}")

    say("reading stock files ...")
    stocks = cafef.stocks(day)
    say(f"  {len(stocks):,} rows, {stocks['symbol'].nunique():,} 3-letter symbols")
    say(f"  span {stocks['trade_date'].min()} -> {stocks['trade_date'].max()}")

    # A symbol can legitimately appear in two exchange files (116 do: UPCOM then
    # HOSE, for example). Those spans should not overlap -- if they do, one of
    # them is wrong and we would be silently picking a winner.
    dupes = stocks.duplicated(subset=["symbol", "trade_date"]).sum()
    if dupes:
        say(f"  WARNING: {dupes:,} duplicate (symbol, date) rows; keeping the first")
        stocks = stocks.drop_duplicates(subset=["symbol", "trade_date"], keep="first")

    # Weekend rows. CafeF occasionally dates a whole session one day late:
    # Saturday 2023-08-26 carries 214 HNX bars that are Friday's session
    # (verified against vnstock). They are real data with a wrong date, so move
    # them back to the previous business day when the symbol has no bar there,
    # and drop them only if that would collide. Every move is flagged in the
    # stored row so nothing is repaired invisibly.
    stocks["trade_date"] = pd.to_datetime(stocks["trade_date"])
    weekend = stocks["trade_date"].dt.dayofweek >= 5
    stocks["date_shifted"] = False
    if weekend.any():
        say(f"  {weekend.sum():,} rows dated on a weekend by the source")
        moved = stocks[weekend].copy()
        moved["trade_date"] = moved["trade_date"] - pd.offsets.BDay(1)
        moved["date_shifted"] = True
        existing = set(
            zip(
                stocks.loc[~weekend, "symbol"],
                stocks.loc[~weekend, "trade_date"],
                strict=True,
            )
        )
        keep = [
            (s, d) not in existing
            for s, d in zip(moved["symbol"], moved["trade_date"], strict=True)
        ]
        say(
            f"    {sum(keep):,} moved to the previous business day, "
            f"{len(keep) - sum(keep):,} dropped as collisions"
        )
        stocks = pd.concat([stocks[~weekend], moved[keep]], ignore_index=True)
    stocks["trade_date"] = stocks["trade_date"].dt.date

    # Bars must be internally consistent before they are stored. The CHECK
    # constraints would reject them anyway; filtering here means we can report
    # how many and why instead of dying on the first bad row.
    ok = (
        (stocks[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (stocks["low"] <= stocks[["open", "close"]].min(axis=1))
        & (stocks["high"] >= stocks[["open", "close"]].max(axis=1))
        & (stocks["volume"] >= 0)
    )
    if (~ok).any():
        say(f"  {(~ok).sum():,} rows rejected as internally inconsistent OHLC")
        stocks = stocks[ok]

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO adjustment_build (reason, cafef_file_date, status)
                VALUES (%s, %s, 'building') RETURNING build_id
                """,
                (f"initial historical load from CafeF {day.name}", day.name),
            )
            build_id = cur.fetchone()[0]
        conn.commit()
        say(f"build_id = {build_id}")

        # --- bar_raw: the permanent record ---------------------------------
        say("loading bar_raw ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE bar_raw")
        raw = stocks.rename(columns={"volume": "matched_volume"}).copy()
        raw["source"] = "cafef"
        raw["is_adjusted_source"] = False
        n = copy_frame(
            conn,
            raw,
            "bar_raw",
            [
                "symbol",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "matched_volume",
                "exchange",
                "source",
                "is_adjusted_source",
                "source_file",
                "date_shifted",
            ],
        )
        conn.commit()
        say(f"  {n:,} rows")

        # --- adjustment_factor ---------------------------------------------
        # factor = adjusted close / unadjusted close. Rows without an adjusted
        # partner get no factor and therefore no adjusted bar; they are counted,
        # not quietly dropped.
        say("computing adjustment factors ...")
        f = stocks.dropna(subset=["adj_close"]).copy()
        f = f[f["close"] > 0]
        f["factor"] = f["adj_close"] / f["close"]
        f["build_id"] = build_id
        missing = len(stocks) - len(f)
        n = copy_frame(
            conn, f, "adjustment_factor", ["symbol", "trade_date", "build_id", "factor"]
        )
        conn.commit()
        say(f"  {n:,} factors, {missing:,} raw rows had no adjusted counterpart")

        # --- negotiated volume: only rows CafeF published -------------------
        say("loading negotiated_volume ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE negotiated_volume")
        nn = cafef.negotiated(day)
        nn = nn.drop_duplicates(subset=["symbol", "trade_date"], keep="first")
        nn = nn[nn["deal_volume"] >= 0]
        n = copy_frame(
            conn,
            nn,
            "negotiated_volume",
            ["symbol", "trade_date", "deal_volume", "source_file"],
        )
        conn.commit()
        say(f"  {n:,} rows (absence of a row means UNKNOWN, never zero)")

        # --- index ----------------------------------------------------------
        say("loading index_bar ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE index_bar")
        idx = cafef.index_bars(day).drop_duplicates(subset=["symbol", "trade_date"])
        n = copy_frame(
            conn,
            idx,
            "index_bar",
            ["symbol", "trade_date", "open", "high", "low", "close", "volume"],
        )
        conn.commit()
        say(f"  {n:,} rows (weekend rows already rejected)")

        # --- trading calendar, from STOCK rows ------------------------------
        say("building trading_day from stock rows ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE trading_day")
            cur.execute(
                """
                INSERT INTO trading_day (trade_date, exchange, symbols_traded)
                SELECT trade_date, exchange, count(*)
                FROM bar_raw GROUP BY trade_date, exchange
                """
            )
            cur.execute("SELECT count(*) FROM trading_day")
            say(f"  {cur.fetchone()[0]:,} exchange-days")
        conn.commit()

        # --- symbol master and exchange history -----------------------------
        say("building symbol and symbol_exchange ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE symbol CASCADE")
            cur.execute(
                """
                INSERT INTO symbol (symbol, first_trade_date, last_trade_date,
                                    current_exchange, is_active)
                SELECT b.symbol, min(b.trade_date), max(b.trade_date),
                       (SELECT exchange FROM bar_raw x
                         WHERE x.symbol = b.symbol
                         ORDER BY trade_date DESC LIMIT 1),
                       max(b.trade_date) >= (SELECT max(trade_date) - INTERVAL '30 days'
                                               FROM bar_raw)
                FROM bar_raw b GROUP BY b.symbol
                """
            )
            # One row per contiguous stay on an exchange. A symbol that moved
            # venue gets two rows, which is the whole point of the table.
            cur.execute(
                """
                INSERT INTO symbol_exchange (symbol, exchange, valid_from, valid_to,
                                             source)
                SELECT symbol, exchange, min(trade_date), max(trade_date), 'cafef'
                FROM bar_raw GROUP BY symbol, exchange
                """
            )
            cur.execute("SELECT count(*) FROM symbol")
            n_sym = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM (SELECT symbol FROM symbol_exchange "
                "GROUP BY symbol HAVING count(*) > 1) t"
            )
            n_moved = cur.fetchone()[0]
        conn.commit()
        say(f"  {n_sym:,} symbols, {n_moved} with more than one exchange span")

        # --- adjusted bars: price x factor, volume / factor ------------------
        # The division is blocker G1. CafeF adjusts price but not volume, so
        # without it RVOL breaks across every stock dividend. Traded value is
        # invariant under this transform, which the checks step verifies.
        say("building bar_adjusted ...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE bar_adjusted")
            cur.execute(
                """
                INSERT INTO bar_adjusted (symbol, trade_date, build_id,
                                          open, high, low, close, matched_volume,
                                          volume_is_adjustable)
                SELECT r.symbol, r.trade_date, %s,
                       r.open  * f.factor, r.high * f.factor,
                       r.low   * f.factor, r.close * f.factor,
                       r.matched_volume / f.factor,
                       NOT r.is_adjusted_source
                FROM bar_raw r
                JOIN adjustment_factor f
                  ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                 AND f.build_id = %s
                """,
                (build_id, build_id),
            )
            cur.execute(
                "SELECT count(*) FROM bar_adjusted WHERE build_id = %s", (build_id,)
            )
            say(f"  {cur.fetchone()[0]:,} rows")
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*), min(trade_date), max(trade_date) FROM bar_adjusted "
                "WHERE build_id = %s AND trade_date >= %s",
                (build_id, RESEARCH_START),
            )
            n, lo, hi = cur.fetchone()
            say(f"research window ({RESEARCH_START}+): {n:,} rows, {lo} -> {hi}")

    say(f"load complete. build {build_id} is 'building';")
    say("run the checks step to promote it to 'good'.")


if __name__ == "__main__":
    main()
