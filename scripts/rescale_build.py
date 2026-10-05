"""Build a new adjustment build that rescales the symbols CafeF restated, so they
return to the research pool. Staged so every step can be undone.

    uv run python scripts/rescale_build.py build UPTO_DIR  # write build N+1
    uv run python scripts/rescale_build.py verify UPTO_DIR  # re-run the gates
    uv run python scripts/rescale_build.py promote            # good + drop the windows
    uv run python scripts/rescale_build.py rollback  # demote + restore the windows

Why. catch_up_upto.py keeps a restated symbol on build 5 by excluding it from its
action date for ~60 sessions. That is honest but costs the pool every name that has a
corporate action (VPB, TPB, GAS ...). The project's rule for a restatement is "rebuild
under a new build_id, never patch in place" (nightly_update.py docstring), and
repair_missed_actions.py shows how: copy the factors forward, restate the days BEFORE
the event, regenerate bar_adjusted.

What makes it safe. A corporate action multiplies every earlier factor by one constant.
So for each windowed symbol this script checks, on EVERY stored day before the action,
that CafeF's current factor equals the stored one times a single ratio (within 0.1%).
A symbol that does not (a second action, an `inferred` repair, a missing day) is NOT
rescaled and stays excluded; it is listed by name. A constant rescale leaves every
return ratio unchanged, which gives exact gates:

  * the adjusted bars of every NON-rescaled symbol are identical in both builds;
  * for the rescaled ones, close(build N+1) / close(build N) is that one ratio;
  * every outcome resolved on build N is identical on build N+1.

Never run it without a fresh pg_dump. `promote` removes the windows of the rescaled
symbols (excluded_window is global, not per build) and saves them to a file so
`rollback` can put them back.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catch_up_upto import REASON  # noqa: E402
from vnstock_research.data import cafef, checks, db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SAVED = REPO / "data" / "reports" / "rescale-windows-removed.json"
TOLERANCE = 1e-3  # CafeF rounds adjusted prices (~1e-5); real actions are percents


def plan_symbol(
    stored: pd.Series, current: pd.Series, event: date, tol: float = TOLERANCE
) -> dict:
    """Can this symbol's history before `event` be rescaled by one constant?

    stored: build-N factor by date.  current: CafeF's factor now, by date.
    Returns {ok, ratio, max_dev, reason}. ok only if every stored day before the
    event exists in CafeF's file and current/stored is the same ratio on all of them.
    """
    pre = stored[[d for d in stored.index if d < event]]
    if pre.empty:
        return {"ok": False, "ratio": np.nan, "max_dev": np.nan, "reason": "no history"}
    missing = [d for d in pre.index if d not in current.index]
    if missing:
        return {
            "ok": False,
            "ratio": np.nan,
            "max_dev": np.nan,
            "reason": f"{len(missing)} stored day(s) absent from CafeF's file",
        }
    r = (current[pre.index] / pre).astype(float)
    ratio = float(r.median())
    dev = float((r / ratio - 1).abs().max())
    if not np.isfinite(ratio) or ratio <= 0:
        return {"ok": False, "ratio": ratio, "max_dev": dev, "reason": "bad ratio"}
    ok = dev <= tol
    return {
        "ok": ok,
        "ratio": ratio,
        "max_dev": dev,
        "reason": "" if ok else f"ratio not constant (max deviation {dev:.4f})",
    }


# adjusted prices are stored to 6 decimals, so two roundings (old and new bar) can
# differ by ~1e-6 even when the rescale is exact (measured: max 8.1e-7). A wrong
# ratio is off by >= 1e-3 of the price, orders of magnitude above this.
STORAGE_ABS_TOL = 2e-6


def make_plans(cur, old: int, events: dict, upto_dir: Path):
    """(plans, passed, failed, current-factor frame) for the windowed symbols."""
    up = cafef.stocks(upto_dir).dropna(subset=["adj_close"])
    up = up[(up["close"] > 0) & up["symbol"].isin(events)].copy()
    up["trade_date"] = pd.to_datetime(up["trade_date"]).dt.date
    up["factor"] = up["adj_close"] / up["close"]
    cur.execute(
        "SELECT symbol, trade_date, factor FROM adjustment_factor "
        "WHERE build_id = %s AND symbol = ANY(%s)",
        (old, list(events)),
    )
    f_old = pd.DataFrame(cur.fetchall(), columns=["symbol", "trade_date", "factor"])
    f_old["factor"] = f_old["factor"].astype(float)
    plans, passed, failed = {}, [], []
    for sym, ev in sorted(events.items()):
        st = f_old[f_old.symbol == sym].set_index("trade_date")["factor"]
        cu = up[up.symbol == sym].set_index("trade_date")["factor"].astype(float)
        p = plan_symbol(st, cu, ev)
        plans[sym] = p
        (passed if p["ok"] else failed).append(sym)
        print(
            f"  {sym:<5} action {ev}  ratio {p['ratio']:.6f}  "
            f"max dev {p['max_dev']:.5f}"
            f"  {'RESCALE' if p['ok'] else 'KEEP EXCLUDED: ' + p['reason']}"
        )
    return plans, passed, failed, up


def gates(conn, old: int, new: int, passed: list, plans: dict, events: dict) -> bool:
    """Every gate must hold before promotion. Returns True if all do."""
    cur = conn.cursor()
    cur.execute(
        "SELECT count(*) FROM bar_adjusted a JOIN bar_adjusted b "
        "USING (symbol, trade_date) WHERE a.build_id=%s AND b.build_id=%s "
        "AND NOT (a.symbol = ANY(%s)) AND (a.open<>b.open OR a.high<>b.high OR "
        "a.low<>b.low OR a.close<>b.close OR "
        "a.matched_volume IS DISTINCT FROM b.matched_volume)",
        (old, new, passed),
    )
    (diff,) = cur.fetchone()
    cur.execute(
        "SELECT (SELECT count(*) FROM bar_adjusted WHERE build_id=%s "
        "AND NOT (symbol = ANY(%s))),"
        " (SELECT count(*) FROM bar_adjusted WHERE build_id=%s "
        "AND NOT (symbol = ANY(%s)))",
        (old, passed, new, passed),
    )
    n_old, n_new = cur.fetchone()
    print(
        f"GATE non-rescaled symbols: rows {n_old:,} -> {n_new:,}, "
        f"differing bars: {diff} (must be 0)"
    )
    bad = 0
    for sym in passed:
        cur.execute(
            "SELECT max(greatest(abs(b.close - a.close * %s::numeric),"
            " abs(b.open - a.open * %s::numeric), abs(b.high - a.high * %s::numeric),"
            " abs(b.low - a.low * %s::numeric))) FROM bar_adjusted a JOIN "
            "bar_adjusted b USING (symbol, trade_date) WHERE a.symbol=%s AND "
            "a.build_id=%s AND b.build_id=%s AND a.trade_date < %s",
            (*([repr(plans[sym]["ratio"])] * 4), sym, old, new, events[sym]),
        )
        (dev,) = cur.fetchone()
        if dev is None or float(dev) > STORAGE_ABS_TOL:
            bad += 1
            print(f"  {sym}: new bar differs from old * ratio by {dev}")
    print(
        "GATE rescaled symbols: new OHLC == old OHLC * ratio on every earlier day "
        f"(within storage rounding {STORAGE_ABS_TOL}); violations: {bad} (must be 0)"
    )
    results = checks.run_all(conn, new)
    blocking = checks.blocking_failures(results)
    for c in results:
        if not c.passed:
            print(f"  [{c.severity.upper()}] {c.name}: {c.observed}")
    print(f"blocking check failures: {len(blocking)} (must be 0)")
    ok = diff == 0 and bad == 0 and not blocking and n_old == n_new
    print("READY to promote" if ok else "NOT READY: do not promote; run rollback")
    return ok


def cmd_verify(upto_dir: Path) -> int:
    """Re-run the gates on the build the last `build` wrote."""
    plan = json.loads(SAVED.with_suffix(".plan.json").read_text())
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT symbol, event_date FROM excluded_window WHERE reason = %s", (REASON,)
    )
    events = {s: e for s, e in cur.fetchall()}
    plans, passed, _, _ = make_plans(cur, plan["old"], events, upto_dir)
    if sorted(passed) != sorted(plan["passed"]):
        print("the rescalable set changed since the build; rebuild instead")
        return 1
    ok = gates(conn, plan["old"], plan["new"], passed, plans, events)
    return 0 if ok else 1


def cmd_build(upto_dir: Path) -> int:
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT build_id FROM adjustment_build WHERE status='good' "
        "ORDER BY build_id DESC LIMIT 1"
    )
    (old,) = cur.fetchone()
    cur.execute(
        "SELECT symbol, event_date FROM excluded_window WHERE reason = %s", (REASON,)
    )
    events = {s: e for s, e in cur.fetchall()}
    print(f"current build {old}; {len(events)} restated symbols with a window")

    plans, passed, failed, up = make_plans(cur, old, events, upto_dir)
    print(f"rescale {len(passed)} | keep excluded {len(failed)}: {failed or 'none'}")
    if not passed:
        print("nothing to rescale")
        return 1

    cur.execute(
        "INSERT INTO adjustment_build (reason, status, symbols_changed) "
        "VALUES (%s, 'building', %s) RETURNING build_id",
        (
            f"rescale {len(passed)} CafeF-restated symbols (from build {old})",
            len(passed),
        ),
    )
    (new,) = cur.fetchone()
    cur.execute(
        "INSERT INTO adjustment_factor (symbol, trade_date, build_id, factor, source) "
        "SELECT symbol, trade_date, %s, factor, source FROM adjustment_factor "
        "WHERE build_id = %s",
        (new, old),
    )
    for sym in passed:
        ev = events[sym]
        cur.execute(
            "UPDATE adjustment_factor SET factor = factor * %s::numeric "
            "WHERE build_id = %s AND symbol = %s AND trade_date < %s",
            (repr(plans[sym]["ratio"]), new, sym, ev),
        )
        post = up[(up.symbol == sym) & (up.trade_date >= ev)]
        for r in post.itertuples():
            cur.execute(
                "INSERT INTO adjustment_factor (symbol, trade_date, build_id, factor,"
                " source) VALUES (%s,%s,%s,%s,'cafef') ON CONFLICT DO NOTHING",
                (sym, r.trade_date, new, float(r.factor)),
            )
    cur.execute(
        "INSERT INTO bar_adjusted (symbol, trade_date, build_id, open, high, low,"
        " close,"
        " matched_volume, volume_is_adjustable) "
        "SELECT r.symbol, r.trade_date, %s, r.open*f.factor, r.high*f.factor,"
        " r.low*f.factor, r.close*f.factor, r.matched_volume/f.factor,"
        " NOT r.is_adjusted_source "
        "FROM bar_raw r JOIN adjustment_factor f ON f.symbol=r.symbol AND "
        "f.trade_date=r.trade_date AND f.build_id=%s",
        (new, new),
    )
    conn.commit()
    print(f"build {new} written ('building'), {cur.rowcount:,} adjusted rows")

    ok = gates(conn, old, new, passed, plans, events)
    SAVED.parent.mkdir(parents=True, exist_ok=True)
    SAVED.with_suffix(".plan.json").write_text(
        json.dumps(
            {
                "old": old,
                "new": new,
                "passed": passed,
                "failed": failed,
                "events": {s: str(e) for s, e in events.items()},
            },
            indent=1,
        )
    )
    print("READY to promote" if ok else "NOT READY: do not promote; run rollback")
    return 0 if ok else 1


def cmd_promote() -> int:
    plan = json.loads(SAVED.with_suffix(".plan.json").read_text())
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT symbol, valid_from, valid_to, reason, event_date, detail::text "
        "FROM excluded_window WHERE reason = %s AND symbol = ANY(%s)",
        (REASON, plan["passed"]),
    )
    rows = [[str(x) for x in r] for r in cur.fetchall()]
    SAVED.write_text(json.dumps(rows, indent=1))
    cur.execute(
        "DELETE FROM excluded_window WHERE reason = %s AND symbol = ANY(%s)",
        (REASON, plan["passed"]),
    )
    cur.execute(
        "UPDATE adjustment_build SET status='good' WHERE build_id = %s", (plan["new"],)
    )
    conn.commit()
    print(
        f"build {plan['new']} promoted; {len(rows)} windows removed "
        f"(saved to {SAVED.name})"
    )
    return 0


def cmd_rollback() -> int:
    plan = json.loads(SAVED.with_suffix(".plan.json").read_text())
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE adjustment_build SET status='failed' WHERE build_id = %s",
        (plan["new"],),
    )
    n = 0
    if SAVED.exists():
        for s, a, b, reason, ev, detail in json.loads(SAVED.read_text()):
            cur.execute(
                "INSERT INTO excluded_window (symbol, valid_from, valid_to, reason,"
                " event_date,"
                " detail) VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (s, a, b, reason, ev if ev != "None" else None, detail),
            )
            n += 1
    conn.commit()
    print(f"build {plan['new']} demoted to 'failed'; {n} windows restored")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build" and len(sys.argv) == 3:
        raise SystemExit(cmd_build(Path(sys.argv[2])))
    if cmd == "verify" and len(sys.argv) == 3:
        raise SystemExit(cmd_verify(Path(sys.argv[2])))
    if cmd == "promote":
        raise SystemExit(cmd_promote())
    if cmd == "rollback":
        raise SystemExit(cmd_rollback())
    raise SystemExit(__doc__)
