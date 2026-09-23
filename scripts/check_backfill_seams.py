"""Do the backfilled spans join the CafeF spans without a step at the seam?

The backfill glues two adjusted price series together at the transfer date. Both
are "adjusted", but they are adjusted by different people to different reference
points, so there is no reason for them to agree in level. If vnstock's span sits
at 0.8x CafeF's, the joined series contains a 25% overnight gap that never
happened -- exactly the artefact the whole adjustment effort exists to remove,
reintroduced at the join.

The fix is a rescale, not a patch: compute the ratio between the two series over
the days around the seam, and multiply the entire vnstock span by it. That is an
adjustment factor like any other, so it is stored as one, flagged 'vnstock'.

There is no overlap day to compare directly -- CafeF starts where vnstock stops.
So the ratio is taken from the closing prices either side of the seam, corrected
for the one day of real price movement between them using the reference source's
own move across that boundary.

Run:  uv run python scripts/check_backfill_seams.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
# A seam is "clean" when the two spans sit within this of each other.
TOLERANCE = 0.02
WINDOW = 5  # sessions each side used to measure the level
# A seam only measures a LEVEL mismatch when the two spans meet across a short
# gap -- a transfer takes a couple of weeks and the price simply resumes. Across
# a long gap the ratio is mostly real price movement, and rescaling by it would
# erase a move that actually happened. Found the hard way: VHM's spans meet
# across 308 days and the raw ratio is 3.82, which is the stock tripling, not a
# level mismatch. Those seams are reported and left alone.
MAX_SEAM_GAP_DAYS = 20

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def main() -> None:
    say(f"Backfill seam check   {datetime.now():%Y-%m-%d %H:%M}")

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT build_id FROM adjustment_build WHERE status='good' "
                "ORDER BY build_id DESC LIMIT 1"
            )
            (build,) = cur.fetchone()
            cur.execute(
                "SELECT symbol FROM symbol WHERE has_backfill ORDER BY symbol"
            )
            symbols = [r[0] for r in cur.fetchall()]
        say(f"build {build}, {len(symbols)} backfilled symbols")
        say("")

        rows = []
        with conn.cursor() as cur:
            for symbol in symbols:
                # The seam: last vnstock bar, first CafeF bar.
                cur.execute(
                    """
                    SELECT
                      (SELECT max(trade_date) FROM bar_raw
                        WHERE symbol=%s AND source='vnstock'),
                      (SELECT min(trade_date) FROM bar_raw
                        WHERE symbol=%s AND source='cafef')
                    """,
                    (symbol, symbol),
                )
                last_v, first_c = cur.fetchone()
                if not last_v or not first_c:
                    continue
                # Median adjusted close on each side, which is steadier than a
                # single day and unaffected by one odd print.
                cur.execute(
                    """
                    SELECT
                      (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY close)
                         FROM (SELECT close FROM bar_adjusted
                                WHERE symbol=%s AND build_id=%s
                                  AND trade_date <= %s
                                ORDER BY trade_date DESC LIMIT %s) a),
                      (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY close)
                         FROM (SELECT close FROM bar_adjusted
                                WHERE symbol=%s AND build_id=%s
                                  AND trade_date >= %s
                                ORDER BY trade_date LIMIT %s) b)
                    """,
                    (symbol, build, last_v, WINDOW,
                     symbol, build, first_c, WINDOW),
                )
                before, after = cur.fetchone()
                if not before or not after or float(before) == 0:
                    continue
                ratio = float(after) / float(before)
                rows.append(
                    {
                        "symbol": symbol,
                        "seam_from": last_v,
                        "seam_to": first_c,
                        "vnstock_level": float(before),
                        "cafef_level": float(after),
                        "ratio": ratio,
                    }
                )

        df = pd.DataFrame(rows)
        clean = df[(df["ratio"] - 1).abs() <= TOLERANCE]
        say(f"seams measured: {len(df)}")
        say(f"  within {TOLERANCE:.0%} of 1 (no rescale needed): {len(clean)}")
        say(f"  needing a rescale:                              {len(df) - len(clean)}")
        say("")
        say(f"  {'sym':<6}{'seam':<24}{'vnstock':>10}{'cafef':>10}{'ratio':>9}")
        for r in df.sort_values("ratio").itertuples():
            mark = "" if abs(r.ratio - 1) <= TOLERANCE else "  <- rescale"
            say(f"  {r.symbol:<6}{str(r.seam_from)+' -> '+str(r.seam_to):<24}"
                f"{r.vnstock_level:>10.2f}{r.cafef_level:>10.2f}"
                f"{r.ratio:>9.4f}{mark}")

        # --- rescale ---------------------------------------------------------
        df["seam_gap_days"] = (
            pd.to_datetime(df["seam_to"]) - pd.to_datetime(df["seam_from"])
        ).dt.days
        off = (df["ratio"] - 1).abs() > TOLERANCE
        long_gap = df["seam_gap_days"] > MAX_SEAM_GAP_DAYS
        needs = df[off & ~long_gap]
        if (off & long_gap).any():
            say("")
            say("NOT rescaled -- the spans meet across too long a gap, so the")
            say("ratio is real price movement rather than a level mismatch:")
            for r in df[off & long_gap].itertuples():
                say(f"  {r.symbol:<6}ratio {r.ratio:>7.4f} across "
                    f"{r.seam_gap_days} days -- left alone, seam still open")
        if not needs.empty:
            say("")
            say("rescaling the vnstock span to meet CafeF at the seam ...")
            with conn.cursor() as cur:
                for r in needs.itertuples():
                    # Multiply the stored factor, not the stored price: the
                    # scale IS an adjustment, and adjustments live in
                    # adjustment_factor where they are visible and rebuildable.
                    cur.execute(
                        """
                        UPDATE adjustment_factor
                        SET factor = factor * %s, source = 'seam_rescale',
                            reason = %s
                        WHERE build_id = %s AND symbol = %s
                          AND trade_date <= %s
                        """,
                        # Its own source (migration 008), so the gate can tell a
                        # rescale above 1 from a real defect (G17).
                        (r.ratio,
                         f"backfill seam rescale x{r.ratio:.6f} at {r.seam_from}",
                         build, r.symbol, r.seam_from),
                    )
                    cur.execute(
                        """
                        UPDATE bar_adjusted a
                        SET open = r.open * f.factor, high = r.high * f.factor,
                            low = r.low * f.factor, close = r.close * f.factor,
                            matched_volume = r.matched_volume / f.factor
                        FROM bar_raw r, adjustment_factor f
                        WHERE a.symbol = %s AND a.build_id = %s
                          AND a.trade_date <= %s
                          AND r.symbol = a.symbol AND r.trade_date = a.trade_date
                          AND f.symbol = a.symbol AND f.trade_date = a.trade_date
                          AND f.build_id = %s
                        """,
                        (r.symbol, build, r.seam_from, build),
                    )
            conn.commit()

            # --- confirm ------------------------------------------------------
            say("")
            say("re-measuring the seams after the rescale:")
            bad = 0
            with conn.cursor() as cur:
                for r in needs.itertuples():
                    cur.execute(
                        """
                        SELECT
                          (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY close)
                             FROM (SELECT close FROM bar_adjusted
                                    WHERE symbol=%s AND build_id=%s
                                      AND trade_date <= %s
                                    ORDER BY trade_date DESC LIMIT %s) a),
                          (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY close)
                             FROM (SELECT close FROM bar_adjusted
                                    WHERE symbol=%s AND build_id=%s
                                      AND trade_date >= %s
                                    ORDER BY trade_date LIMIT %s) b)
                        """,
                        (r.symbol, build, r.seam_from, WINDOW,
                         r.symbol, build, r.seam_to, WINDOW),
                    )
                    before, after = cur.fetchone()
                    new_ratio = float(after) / float(before)
                    ok = abs(new_ratio - 1) <= TOLERANCE
                    bad += 0 if ok else 1
                    say(f"  {r.symbol:<6}{r.ratio:>9.4f} -> {new_ratio:>7.4f}"
                        f"  {'OK' if ok else 'STILL OFF'}")
            say("")
            say(f"seams still outside tolerance after rescale: {bad}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORTS / "backfill-seams.csv", index=False)
    path = REPORTS / f"backfill-seams-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
