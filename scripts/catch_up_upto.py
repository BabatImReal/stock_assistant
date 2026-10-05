"""One-off catch-up after an outage: load the sessions the nightly job missed,
from CafeF's cumulative "Upto<date>" files, WITHOUT seaming restated symbols.

    uv run python scripts/catch_up_upto.py DIR            # dry run, rolled back
    uv run python scripts/catch_up_upto.py DIR --apply    # commit if checks pass
    uv run python scripts/catch_up_upto.py DIR --since=2026-09-21 --apply  # repair

Why this exists. CafeF's daily page keeps only ~3 dates, and nightly_update.py
loads one publication per run, so any outage longer than that leaves a permanent
gap. The cumulative files hold every day, but they are also RESTATED: when a
stock dividend or rights issue lands, CafeF re-adjusts the whole past, so a
symbol's adjusted history moves. nightly_update.py cannot see this (its
`restated` flag is hardcoded False: open-questions G2). Appending new days to the
old build for such a symbol would put them on a different price basis from the
stored past and show up as a fake -20% day.

So, per Ben's decision of 2026-10-05 (keep build 5, exclude the restated):

  * bar_raw gets EVERY new bar. It is the permanent record: raw prices are what
    traded and never change.
  * adjustment_factor / bar_adjusted get the new days for UNRESTATED symbols only.
  * A restated symbol gets an excluded_window around its corporate action,
    sized like repair_missed_actions.py sizes one, so no feature or return is
    computed across the seam. It re-enters research when the build is rebuilt.

A symbol is compared on ITS OWN last stored day, not on the database's last day:
thin stocks skip sessions, and one that skipped the last day but was restated since
would otherwise get new-basis bars with no flag and no window (9 such symbols were
found after the first run). Symbols already inside an active restated window are
skipped, so VPB is not re-flagged every night against its old-basis tail.

Never use load_history.py for this: it truncates the derived tables and would
undo the verified repairs layered on since (date-shift deletes, inferred
factors, excluded windows, backfills).
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import cafef, checks, db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_missed_actions import exclusion_window  # noqa: E402

# CafeF rounds adjusted prices, so a restated symbol's factor wobbles by ~1e-5 from
# day to day (TPB: 0.839397, 0.839400, 0.839403). Real corporate actions step by
# percents (smallest seen: NVL 0.7%, flagged restatements >= 2.6%). 0.1% sits
# between the two. A tolerance of 1e-6 read the rounding as the event itself.
TOLERANCE = 1e-3
REASON = "restated by CafeF: corporate action after the last loaded session"


def event_date(
    factor_by_date: pd.Series, base: float, tol: float = TOLERANCE
) -> date | None:
    """First date whose factor leaves `base` (the factor on the last stored day).

    Before a corporate action the restated factor is below 1; on the action date
    it steps. That first step is the event the exclusion window is built around.
    """
    moved = factor_by_date[(factor_by_date / base - 1).abs() > tol].sort_index()
    return None if moved.empty else moved.index[0]


def event_or_next(factor_by_date: pd.Series, base: float) -> date:
    """The action date, or, if no step was observed yet, the day after the last bar.

    A symbol restated on a day it has not traded since still has to be excluded:
    its NEXT bar will be on the new basis. So the window opens the day after the
    last row we hold, never later.
    """
    ev = event_date(factor_by_date, base)
    return ev if ev is not None else max(factor_by_date.index) + timedelta(days=1)


def flag_restated(
    anchors: pd.DataFrame, up: pd.DataFrame, tol: float = TOLERANCE
) -> pd.DataFrame:
    """Symbols whose factor on their OWN last stored day differs in the new file.

    anchors: symbol, anchor_day, stored.  up: symbol, trade_date, factor.
    Returns symbol-indexed rows (anchor_day, stored, new, rel) with rel > tol.
    """
    m = anchors.merge(
        up.rename(columns={"trade_date": "anchor_day", "factor": "new"})[
            ["symbol", "anchor_day", "new"]
        ],
        on=["symbol", "anchor_day"],
    )
    m["rel"] = (m["new"] / m["stored"] - 1).abs()
    return m[m["rel"] > tol].set_index("symbol")


def exclusion_span(event: date) -> tuple[date, date]:
    """(valid_from, valid_to) for a restated symbol's excluded window.

    The days BEFORE the event are valid, old-basis data (see factors_to_insert)
    and are scored live on their own day, so the window starts at the event: a
    hold that crosses it hits the excluded event day, which has no adjusted bar.
    It runs L sessions after (a feature with lookback L reaches back to the
    event), converted to calendar days with margin, and deliberately into the
    FUTURE: tomorrow's nightly run appends days on the new basis, and they are
    exactly the ones that would seam. Starting earlier would blank spent history
    that was never wrong.
    """
    # exclusion_window() returns (lookback L, forward F), despite its docstring.
    after, _ = exclusion_window()
    return event, event + timedelta(days=after * 7 // 5 + 7)


def factors_to_insert(
    new: pd.DataFrame,
    events: dict,
    stored: pd.Series,
    last: pd.Series,
) -> pd.DataFrame:
    """Rows (symbol, trade_date, factor) that may enter adjustment_factor.

    Unrestated symbols: the file's own factor, as the nightly job does.

    Restated symbols: only the days STRICTLY BEFORE the corporate action, on the
    OLD price basis the stored history uses. The new file expresses those days
    as factor_up = (true factor) * n, where n is its factor on the last stored
    day, so the old-basis factor is stored * factor_up / n. These days were
    ordinary data when they happened; a live scan on one of them would have
    seen the symbol, so the record must too. The action day and everything
    after are on the new basis and stay out (excluded_window covers them).
    """
    f = new.dropna(subset=["factor"])
    rows = f[~f["symbol"].isin(events)][["symbol", "trade_date", "factor"]]
    parts = [rows]
    for sym, ev in events.items():
        s = f[(f["symbol"] == sym) & (f["trade_date"] < (ev or date.max))]
        old = s["factor"].astype(float) * float(stored[sym]) / float(last[sym])
        parts.append(s[["symbol", "trade_date"]].assign(factor=old))
    return pd.concat(parts, ignore_index=True)


def main(upto_dir: Path, apply: bool, since: date | None = None) -> int:
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT max(trade_date) FROM bar_raw")
            (have,) = cur.fetchone()
            have = since or have  # --since repairs days an earlier run loaded
            cur.execute(
                "SELECT build_id FROM adjustment_build WHERE status='good' "
                "ORDER BY build_id DESC LIMIT 1"
            )
            (build,) = cur.fetchone()
            # Each symbol's OWN last stored factor, at most ~25 sessions back (older
            # means it was suspended and resumes as a new span, as nightly_update does).
            cur.execute(
                "SELECT DISTINCT ON (symbol) symbol, trade_date, factor "
                "FROM adjustment_factor WHERE build_id = %s AND trade_date <= %s "
                "AND trade_date > %s ORDER BY symbol, trade_date DESC",
                (build, have, have - timedelta(days=35)),
            )
            anchors = pd.DataFrame(
                cur.fetchall(), columns=["symbol", "anchor_day", "stored"]
            )
            anchors["stored"] = anchors["stored"].astype(float)
            cur.execute(
                "SELECT symbol FROM excluded_window "
                "WHERE reason = %s AND event_date <= %s",
                (REASON, have),
            )
            handled = {r[0] for r in cur.fetchall()}
        print(f"database through {have}, build {build}")

        up = cafef.stocks(upto_dir)
        up["trade_date"] = pd.to_datetime(up["trade_date"]).dt.date
        weekday = pd.to_datetime(up["trade_date"]).dt.dayofweek
        up = up[weekday < 5]
        ok = (
            (up[["open", "high", "low", "close"]] > 0).all(axis=1)
            & (up["low"] <= up[["open", "close"]].min(axis=1))
            & (up["high"] >= up[["open", "close"]].max(axis=1))
        )
        up = up[ok].copy()
        up["factor"] = up["adj_close"] / up["close"]

        new = up[up["trade_date"] > have]
        if new.empty:
            print("nothing newer than the database; nothing to do")
            return 0
        dates = sorted(new["trade_date"].unique())
        print(
            f"new sessions: {len(dates)} ({dates[0]} .. {dates[-1]}), {len(new):,} bars"
        )

        todo = anchors[
            anchors["symbol"].isin(set(new["symbol"]))
            & ~anchors["symbol"].isin(handled)
        ]
        flagged = flag_restated(todo, up.dropna(subset=["factor"]))
        print(
            f"restated symbols: {len(flagged)} of {len(todo)} compared "
            f"({len(handled)} already handled, skipped)"
        )

        events = {}
        for sym in flagged.index:
            fs = (
                new[new["symbol"] == sym]
                .dropna(subset=["factor"])
                .set_index("trade_date")["factor"]
            )
            if fs.empty:
                continue
            events[sym] = event_or_next(
                fs.astype(float), float(flagged.loc[sym, "new"])
            )
        for sym, ev in sorted(events.items(), key=lambda kv: kv[1]):
            print(
                f"  restated {sym}: factor {flagged.loc[sym, 'stored']:.4f} -> "
                f"{flagged.loc[sym, 'new']:.4f}, action {ev}"
            )
        stored = flagged["stored"]
        last = flagged["new"]
        raw_rows = new
        adj_rows = factors_to_insert(new, events, stored, last)

        with conn.cursor() as cur:
            for r in raw_rows.itertuples():
                cur.execute(
                    """
                    INSERT INTO bar_raw (symbol, trade_date, open, high, low, close,
                        matched_volume, exchange, source, source_file)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'cafef',%s)
                    ON CONFLICT (symbol, trade_date) DO NOTHING
                    """,
                    (
                        r.symbol,
                        r.trade_date,
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        int(r.volume),
                        r.exchange,
                        r.source_file,
                    ),
                )
            idx = cafef.index_bars(upto_dir)
            idx = idx[idx["trade_date"] > have]
            for r in idx.itertuples():
                cur.execute(
                    "INSERT INTO index_bar (symbol, trade_date, open, high, low, close,"
                    " volume, source) VALUES (%s,%s,%s,%s,%s,%s,%s,'cafef') "
                    "ON CONFLICT DO NOTHING",
                    (
                        r.symbol,
                        r.trade_date,
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        int(r.volume),
                    ),
                )
            for sym in events:  # replace what an earlier run put after the anchor
                anchor = flagged.loc[sym, "anchor_day"]
                for table in ("bar_adjusted", "adjustment_factor"):
                    cur.execute(
                        f"DELETE FROM {table} WHERE build_id = %s AND symbol = %s "
                        "AND trade_date > %s",
                        (build, sym, anchor),
                    )
            for r in adj_rows.itertuples():
                cur.execute(
                    "INSERT INTO adjustment_factor"
                    " (symbol, trade_date, build_id, factor, source)"
                    " VALUES (%s,%s,%s,%s,'cafef')"
                    " ON CONFLICT DO NOTHING",
                    (r.symbol, r.trade_date, build, float(r.factor)),
                )
            cur.execute(
                """
                INSERT INTO bar_adjusted (symbol, trade_date, build_id, open, high, low,
                    close, matched_volume, volume_is_adjustable)
                SELECT r.symbol, r.trade_date, %s, r.open*f.factor, r.high*f.factor,
                       r.low*f.factor, r.close*f.factor, r.matched_volume/f.factor,
                       NOT r.is_adjusted_source
                FROM bar_raw r JOIN adjustment_factor f
                  ON f.symbol=r.symbol AND f.trade_date=r.trade_date AND f.build_id=%s
                WHERE r.trade_date > %s
                ON CONFLICT DO NOTHING
                """,
                (build, build, have),
            )
            cur.execute(
                "INSERT INTO trading_day (trade_date, exchange, symbols_traded) "
                "SELECT trade_date, exchange, count(*) FROM bar_raw "
                "WHERE trade_date > %s GROUP BY trade_date, exchange "
                "ON CONFLICT DO NOTHING",
                (have,),
            )
            for sym, ev in events.items():
                lo, hi = exclusion_span(ev)
                cur.execute(
                    "INSERT INTO excluded_window (symbol, valid_from, valid_to, reason,"
                    " event_date, detail) VALUES (%s,%s,%s,%s,%s,%s::jsonb) "
                    "ON CONFLICT DO NOTHING",
                    (
                        sym,
                        lo,
                        hi,
                        REASON,
                        ev,
                        json.dumps(
                            {
                                "anchor_day": str(flagged.loc[sym, "anchor_day"]),
                                "stored": float(flagged.loc[sym, "stored"]),
                                "new": float(flagged.loc[sym, "new"]),
                            }
                        ),
                    ),
                )

        results = checks.run_all(conn, build)
        blocking = checks.blocking_failures(results)
        for c in results:
            if not c.passed:
                print(f"  [{c.severity.upper()}] {c.name}: {c.observed}")
        print(f"events: {len(events)} windows, blocking failures: {len(blocking)}")

        if blocking or not apply:
            conn.rollback()
            print(
                "ROLLED BACK "
                + ("(blocking failures)" if blocking else "(dry run; use --apply)")
            )
            return 1 if blocking else 0

        checks.store(conn, build, results)  # commits everything above
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO job_run (job, status, message, source_date, trade_date,"
                " rows_added, build_id, finished_at)"
                " VALUES ('catch_up_upto','ok',%s,%s,%s,%s,%s, now())",
                (
                    f"{len(dates)} sessions from {upto_dir.name}; "
                    f"{len(flagged)} restated excluded",
                    dates[-1],
                    dates[-1],
                    len(raw_rows),
                    build,
                ),
            )
        conn.commit()
        print(
            f"COMMITTED: {len(raw_rows):,} bars, "
            f"{len(flagged)} restated symbols excluded"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    since = next(
        (a.split("=", 1)[1] for a in sys.argv if a.startswith("--since=")), None
    )
    raise SystemExit(
        main(
            Path(args[0]),
            "--apply" in sys.argv,
            date.fromisoformat(since) if since else None,
        )
    )
