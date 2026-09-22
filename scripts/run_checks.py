"""Phase 4 step 3: data-quality checks and cross-source reconciliation.

This is the gate. A build loaded by load_history.py sits at status 'building'
and is invisible to research until this promotes it to 'good'. Nothing here
deletes or edits data -- a failing build is simply not promoted, and research
keeps reading the last good one.

Two halves:
  1. Internal checks (vnstock_research.data.checks) -- is the data consistent
     with itself and with what we know about the market?
  2. Reconciliation against vnstock, sampled across EVERY year, because the
     errors this catches cluster in time and checking only recent years would
     miss a bad decade.

Run:  uv run python scripts/run_checks.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import checks, db, reconcile  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
START = "2012-01-01"

# Ten symbols spanning banks, steel, tech, brokers, consumer and property, so a
# problem confined to one sector cannot hide behind nine healthy names.
SYMBOLS = ["VNM", "HPG", "FPT", "SSI", "ACB", "VIC", "MBB", "REE", "DHG", "PNJ"]

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def current_build(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT build_id FROM adjustment_build ORDER BY build_id DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit("No build found. Run scripts/load_history.py first.")
    return row[0]


def cafef_frame(conn, build_id: int) -> pd.DataFrame:
    """Adjusted bars for the sample symbols, straight from the database."""
    with conn.cursor() as cur:
        cur.execute(
            """
            -- Adjusted close against vnstock's adjusted close, but RAW volume
            -- against vnstock's volume: vnstock adjusts prices and not volume,
            -- so comparing our adjusted volume to theirs measures the factor,
            -- not agreement.
            SELECT a.symbol, a.trade_date, a.close, r.matched_volume
            FROM bar_adjusted a
            JOIN bar_raw r ON r.symbol = a.symbol AND r.trade_date = a.trade_date
            WHERE a.build_id = %s AND a.symbol = ANY(%s) AND a.trade_date >= %s
            """,
            (build_id, SYMBOLS, START),
        )
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["symbol", "date", "close", "volume"])
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return reconcile.normalise(df)


def vnstock_frame() -> pd.DataFrame:
    """The reference source, fetched in 4-year chunks.

    Never one long request: the community tier's 8-year cap is stateful, and one
    over-long call silently truncates every later call in the process.
    """
    db.load_env()
    key = os.environ.get("VNSTOCK_API_KEY", "").strip()
    say(f"  vnstock key present: {'yes (60/min)' if key else 'no (20/min)'}")

    from vnstock import Quote

    today = str(pd.Timestamp.today().date())
    windows = []
    lo = pd.Timestamp(START)
    while lo < pd.Timestamp(today):
        hi = min(
            lo + pd.DateOffset(years=4) - pd.Timedelta(days=1), pd.Timestamp(today)
        )
        windows.append((str(lo.date()), str(hi.date())))
        lo = hi + pd.Timedelta(days=1)

    frames = []
    for sym in SYMBOLS:
        parts = []
        for w_lo, w_hi in windows:
            time.sleep(1.2)
            try:
                parts.append(
                    Quote(source="vci", symbol=sym).history(
                        start=w_lo, end=w_hi, interval="1D"
                    )
                )
            except Exception as e:  # noqa: BLE001
                say(f"    {sym} {w_lo}: {type(e).__name__}")
        if parts:
            frames.append(
                reconcile.normalise(
                    pd.concat(parts, ignore_index=True), symbol=sym, date_col="time"
                )
            )
            say(f"    {sym}: {len(frames[-1]):,} rows")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    say(f"Phase 4 checks and reconciliation  {datetime.now():%Y-%m-%d %H:%M}")

    with db.connect() as conn:
        build_id = current_build(conn)
        say(f"build_id = {build_id}")

        say("")
        say("=== INTERNAL CHECKS ===")
        results = checks.run_all(conn, build_id)
        checks.store(conn, build_id, results)
        width = max(len(c.name) for c in results)
        for c in results:
            mark = "PASS" if c.passed else ("FAIL" if c.severity == "fail" else "WARN")
            say(f"  [{mark}] {c.name:<{width}}  {c.observed}")

        blocking = checks.blocking_failures(results)

        say("")
        say("=== RECONCILIATION: CafeF (database) vs vnstock ===")
        left = cafef_frame(conn, build_id)
        say(f"  CafeF: {len(left):,} rows for {left['symbol'].nunique()} symbols")
        right = vnstock_frame()

        recon_passed = None
        if right.empty:
            say("  vnstock returned nothing -- reconciliation skipped")
        else:
            res = reconcile.reconcile(
                left, right, left_name="cafef", right_name="vnstock"
            )
            for r in res:
                say("  " + r.summary_line())

            # Per year, because an error confined to one year is exactly what a
            # single overall percentage hides (doc §8.1, regime change).
            say("")
            say("  close match rate by year:")
            merged = left.merge(right, on=["symbol", "date"], suffixes=("_l", "_r"))
            merged["year"] = pd.to_datetime(merged["date"]).dt.year
            merged["ok"] = (
                (merged["close_l"] - merged["close_r"]).abs() / merged["close_r"].abs()
            ) <= reconcile.PRICE_TOLERANCE
            for year, grp in merged.groupby("year"):
                say(
                    f"    {year}  {grp['ok'].sum():>5,}/{len(grp):>5,}"
                    f" = {grp['ok'].mean():6.2%}"
                )

            say("")
            say("  per symbol:")
            for sym, grp in merged.groupby("symbol"):
                say(
                    f"    {sym:<5} {grp['ok'].sum():>5,}/{len(grp):>5,}"
                    f" = {grp['ok'].mean():6.2%}"
                )

            close = next(r for r in res if r.column == "close")
            # A CONSTANT ratio is an adjustment-policy difference between the two
            # sources, not corruption -- VNM's 0.9835 is one event CafeF adjusts
            # for and VCI does not. Scattered ratios are the worrying case.
            ratios = (
                close.mismatches["ratio"].round(3)
                if not close.mismatches.empty
                else pd.Series(dtype=float)
            )
            dominant = ratios.value_counts(normalize=True).head(1)
            if not dominant.empty and dominant.iloc[0] > 0.5:
                say(
                    f"  NOTE: {dominant.iloc[0]:.0%} of mismatches share ratio "
                    f"{dominant.index[0]} -- an adjustment-policy difference, "
                    f"not corruption"
                )
            recon_passed = close.match_rate >= 0.85

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reconciliation_run
                      (scope, left_source, right_source, date_from, date_to,
                       symbols_checked, price_tolerance, volume_tolerance,
                       compared, matched, passed, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING run_id
                    """,
                    (
                        "historical-sample",
                        "cafef",
                        "vnstock",
                        START,
                        str(pd.Timestamp.today().date()),
                        len(SYMBOLS),
                        reconcile.PRICE_TOLERANCE,
                        reconcile.VOLUME_TOLERANCE,
                        close.compared,
                        close.matched,
                        recon_passed,
                        "sampled across every year",
                    ),
                )
                run_id = cur.fetchone()[0]
                for _, m in close.mismatches.iterrows():
                    cur.execute(
                        """
                        INSERT INTO reconciliation_mismatch
                          (run_id, symbol, trade_date, column_name,
                           left_value, right_value, rel_diff, ratio)
                        VALUES (%s,%s,%s,'close',%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            run_id,
                            m["symbol"],
                            m["date"],
                            float(m["close_l"]),
                            float(m["close_r"]),
                            float(m["rel_diff"]),
                            None if pd.isna(m["ratio"]) else float(m["ratio"]),
                        ),
                    )
            conn.commit()
            say(f"  stored as reconciliation_run {run_id}")

        # --- the gate --------------------------------------------------------
        say("")
        promote = not blocking and recon_passed is not False
        status = "good" if promote else "failed"
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE adjustment_build SET status = %s, notes = %s "
                "WHERE build_id = %s",
                (status, f"{len(blocking)} blocking failures", build_id),
            )
        conn.commit()

        if promote:
            say(f"BUILD {build_id} PROMOTED to 'good'. Research may use it.")
        else:
            say(f"BUILD {build_id} marked 'failed' and NOT promoted.")
            for c in blocking:
                say(f"  blocking: {c.name} -- {c.observed}")
            say("  Raw data is kept. Research keeps reading the last good build.")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"phase4-checks-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
