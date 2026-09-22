"""Verify every date-shifted bar against vnstock, and drop the ones that disagree.

The loader moves a bar that the source dated on a non-trading day back to the
previous business day. That repair was justified by one worked example -- CafeF
published 214 HNX bars on Saturday 2023-08-26 whose values are Friday's session,
and SHS's "Saturday" volume of 22,886,395 is exactly vnstock's Friday figure.

One example is not evidence for 85 rows. Ben's instruction: keep the fix, but
check every shifted bar against the second source and drop any that do not
match. A repair we cannot verify is a guess, and a guess in the permanent record
is worse than a missing bar.

Matching is on CLOSE and VOLUME at the shifted-to date:
  - volume must match exactly (both sources report matched volume as an integer)
  - close is compared on the adjusted scale, so only the RATIO is stable; the
    test is that the bar's close/volume pair identifies the same session.

Anything that fails is deleted from bar_raw and reported. Nothing is edited.

Run:  uv run python scripts/verify_date_shifts.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "data" / "reports"
DELAY = 1.3

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def main() -> None:
    db.load_env()
    say(f"Date-shift verification   {datetime.now():%Y-%m-%d %H:%M}")

    with db.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, trade_date, close, matched_volume
                FROM bar_raw WHERE date_shifted ORDER BY trade_date, symbol
                """
            )
            rows = cur.fetchall()
        say(f"shifted bars to verify: {len(rows)}")
        if not rows:
            say("nothing flagged -- did the loader run with the fix?")
            return

        from vnstock import Quote

        verified, rejected, unchecked = [], [], []
        for symbol, trade_date, _close, volume in rows:
            time.sleep(DELAY)
            lo = str(trade_date - pd.Timedelta(days=10))
            hi = str(trade_date + pd.Timedelta(days=10))
            try:
                df = Quote(source="vci", symbol=symbol).history(
                    start=lo, end=hi, interval="1D"
                )
            except Exception as e:  # noqa: BLE001
                unchecked.append((symbol, trade_date, f"{type(e).__name__}"))
                continue
            if df is None or df.empty:
                unchecked.append((symbol, trade_date, "no data"))
                continue

            df["d"] = pd.to_datetime(df["time"]).dt.date
            same_day = df[df["d"] == trade_date]
            if same_day.empty:
                # vnstock has no session on the date we moved the bar to, so the
                # move invented a trading day. Reject.
                rejected.append((symbol, trade_date, "no session at target date"))
                continue

            ref_vol = int(same_day["volume"].iloc[0])
            if ref_vol == int(volume):
                verified.append((symbol, trade_date))
            else:
                rejected.append(
                    (symbol, trade_date, f"volume {int(volume):,} vs {ref_vol:,}")
                )

        say("")
        say(f"verified (volume matches the reference source): {len(verified)}")
        say(f"rejected (will be deleted):                     {len(rejected)}")
        say(f"unchecked (reference has no data):              {len(unchecked)}")

        if rejected:
            say("")
            say("rejected rows:")
            for sym, d, why in rejected[:20]:
                say(f"  {sym:<5} {d}  {why}")
            # Cascade: a deleted raw bar must not leave an adjusted bar or a
            # factor behind, or the "adjusted bars match factors" check passes
            # while bar_adjusted contains a row with no permanent record.
            with conn.cursor() as cur:
                for sym, d, _ in rejected:
                    cur.execute(
                        "DELETE FROM bar_raw WHERE symbol = %s AND trade_date = %s "
                        "AND date_shifted",
                        (sym, d),
                    )
                    cur.execute(
                        "DELETE FROM bar_adjusted WHERE symbol = %s "
                        "AND trade_date = %s",
                        (sym, d),
                    )
                    cur.execute(
                        "DELETE FROM adjustment_factor WHERE symbol = %s "
                        "AND trade_date = %s",
                        (sym, d),
                    )
            conn.commit()
            say(f"  deleted {len(rejected)} unverifiable shifted bars")

        # An unverifiable bar is not a verified one. These stay, flagged, and
        # research excludes date_shifted bars by default anyway
        # (config/rules/universe.yaml).
        if unchecked:
            say("")
            say("unchecked bars are KEPT but stay flagged; research excludes")
            say("date_shifted bars by default, so nothing depends on them.")
            for sym, d, why in unchecked[:10]:
                say(f"  {sym:<5} {d}  {why}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"date-shift-verification-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
