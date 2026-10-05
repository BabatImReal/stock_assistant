"""The chart-formation forward-only shadow track (v3).

Registration: docs/preregistration/chart-forward-v3.md, frozen values in
config/rules/chart_forward_v3.yaml (committed before any event was recorded).

What it does, every trading day:
  * runs the frozen v2 detector UNCHANGED on every stock, each symbol loaded from the
    census start (segments, pivots and episode ids depend on where a segment starts);
  * appends every confirmed first break whose signal day is AFTER `frozen_on` to the
    append-only research/chart_forward_log.csv, and a "nothing" row for a quiet day, so
    a missed day is distinguishable from a quiet one;
  * `evaluate` compares each resolved event's 10-session net return with the SAME
    signal day's liquid cross-section (market moves cancel) and reports H1/H2 with a
    signal-day-clustered standard error. It never declares a result before the
    registered looks.

This module adds no geometry, no threshold and no trial. It lives at the package
root, outside the hashed features/ patterns/ data/ trees, so the registered scan's
fingerprint and returns hashes are unaffected.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "rules" / "chart_forward_v3.yaml"
LOG = ROOT / "research" / "chart_forward_log.csv"
REPORTS = ROOT / "research" / "reports"

COLUMNS = [
    "day",
    "symbol",
    "variant",
    "label",
    "side",
    "episode_id",
    "signal_on",
    "boundary_at_signal",
    "prior_trend",
    "tier",
    "registration",
    "recorded_at",
]


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def registration_hash(path: Path = CONFIG) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def read(path: Path = LOG) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def check_frozen(log: pd.DataFrame, reg: str | None = None) -> None:
    """Refuse to extend a log written under a different registration."""
    reg = reg or registration_hash()
    seen = set(log["registration"]) if len(log) else set()
    if seen and seen != {reg}:
        raise ValueError(
            f"the registered chart forward rules changed (log {sorted(seen)}, now "
            f"{reg}): a change starts a new version with a new forward clock"
        )


def check_detector(cfg: dict | None = None) -> None:
    """The pinned detector must be the one that is actually running."""
    from . import chart_research as v1
    from . import chart_research_v2 as v2

    cfg = cfg or config()
    want = cfg["detector"]
    have = {
        "chart_rules_hash": v2.rules_hash(),
        "chart_code_hash": v2.code_hash(),
    }
    base = cfg["detector"]["geometry_base"]
    have_base = {"rules_hash": v1.rules_hash(), "code_hash": v1.code_hash()}
    if any(want[k] != have[k] for k in have) or base != have_base:
        raise ValueError(
            "the chart detector no longer matches the frozen registration "
            f"({have} / {have_base}); the forward track refuses to run"
        )


def is_forward(day, cfg: dict | None = None) -> bool:
    cfg = cfg or config()
    return pd.Timestamp(day) > pd.Timestamp(cfg["frozen_on"])


def event_rows(
    events: pd.DataFrame, day, tiers: dict, cfg: dict, reg: str
) -> list[dict]:
    """The confirmed first breaks signalled on `day`, as log rows (pure)."""
    labels = cfg["labels"]
    day = pd.Timestamp(day).date()
    rows = []
    if len(events):
        conf = events[events["state"].isin(["confirmed_up", "confirmed_down"])]
        conf = conf[pd.to_datetime(conf["signal_on"]).dt.date == day]
        for e in conf.sort_values(["symbol", "variant"]).itertuples():
            rows.append(
                {
                    "day": str(day),
                    "symbol": e.symbol,
                    "variant": e.variant,
                    "label": labels[e.variant],
                    "side": e.side,
                    "episode_id": e.episode_id,
                    "signal_on": str(pd.Timestamp(e.signal_on).date()),
                    "boundary_at_signal": f"{float(e.boundary_at_signal):.6f}",
                    "prior_trend": str(e.prior_trend),
                    "tier": str(tiers.get(e.symbol, "")),
                    "registration": reg,
                }
            )
    return rows


def append_day(
    day,
    rows: list[dict],
    path: Path = LOG,
    cfg: dict | None = None,
    reg: str | None = None,
) -> str:
    """Append one day, once. 'new' | 'same'. A different answer for a day is refused."""
    cfg = cfg or config()
    reg = reg or registration_hash()
    day = str(pd.Timestamp(day).date())
    if not is_forward(day, cfg):
        raise ValueError(f"{day} is not a forward day (frozen_on {cfg['frozen_on']})")
    log = read(path)
    check_frozen(log, reg)
    key = lambda df: sorted(  # noqa: E731 - tiny local helper
        zip(df["symbol"], df["episode_id"], df["side"], strict=True)
    )
    old = log[log["day"] == day]
    if len(old):
        old_events = old[old["symbol"] != ""]
        new_events = pd.DataFrame(rows, columns=COLUMNS)
        if key(old_events) != key(new_events):
            raise ValueError(
                f"{day} is already recorded with a different set of events; the log "
                "is append-only and is not rewritten"
            )
        return "same"
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    out = rows or [{"day": day, "symbol": "", "registration": reg}]
    frame = pd.DataFrame(out).reindex(columns=COLUMNS).fillna("")
    frame["recorded_at"] = stamp
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, mode="a", header=not Path(path).exists(), index=False)
    return "new"


def missing_days(
    all_days: list, log: pd.DataFrame, cfg: dict | None = None
) -> list[str]:
    """Forward trading days not yet in the log (pure): a missed day is recorded late."""
    cfg = cfg or config()
    done = set(log["day"]) if len(log) else set()
    days = sorted(str(pd.Timestamp(d).date()) for d in all_days)
    return [d for d in days if is_forward(d, cfg) and d not in done]


# --- detection (needs the database) ----------------------------------------------


def detect_all(conn, last_day, start: str | None = None):
    """Events for every stock, each symbol loaded from the census start to last_day."""
    from . import chart_research_v2 as v2
    from .features import bars

    cfg = config()
    start = start or cfg["history_start"]
    build = bars.current_build(conn)
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
            "AND trade_date >= %s ORDER BY 1",
            (build, start),
        ).fetchall()
    ]
    parts = []
    for _, frame in bars.load_many(conn, symbols, start=start, build=build):
        frame = frame[pd.to_datetime(frame["trade_date"]) <= pd.Timestamp(last_day)]
        if len(frame):
            parts.append(v2.detect(frame))
    cols = parts[0].columns if parts else []
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


def record_days(conn, days: list, path: Path = LOG) -> dict:
    """Detect once, then append each forward day in date order. {day: n_events}."""
    from .data import universe

    check_detector()
    cfg = config()
    days = sorted(str(pd.Timestamp(d).date()) for d in days)
    days = [d for d in days if is_forward(d, cfg)]
    if not days:
        return {}
    events = detect_all(conn, days[-1])
    tiers = universe.tiers(conn, days[0], days[-1])
    tiers["trade_date"] = pd.to_datetime(tiers["trade_date"]).dt.date.astype(str)
    reg = registration_hash()
    out = {}
    for d in days:
        t = tiers[tiers["trade_date"] == d].set_index("symbol")["tier"].to_dict()
        rows = event_rows(events, d, t, cfg, reg)
        append_day(d, rows, path, cfg, reg)
        out[d] = len(rows)
    return out


# --- evaluation --------------------------------------------------------------------


def p_display(p: float, n: int, looks: list) -> str:
    """No p-value is shown before the first registered look (pure).

    With a handful of events on a handful of days the clustered p is optimistic (8
    events printed p = 0.000). The registration only lets p count at 60/120/240.
    """
    if n < looks[0]:
        return f"not shown below the first registered look (n={looks[0]})"
    return f"{p:.3f}"


def cluster_stats(excess: pd.Series, clusters: pd.Series) -> dict:
    """Mean excess with a signal-day-clustered SE (pure).

    Events signalled on the same day share the market, so they are not independent.
    se = sqrt(sum over clusters of (sum of deviations)^2) / n, the standard
    cluster-robust variance of a mean. One-sided p from the normal; with few clusters
    it is optimistic, which is why the registered looks need 60+ events.
    """
    x = excess.dropna()
    c = clusters.loc[x.index]
    n = len(x)
    if n == 0:
        return {
            "n": 0,
            "clusters": 0,
            "mean": np.nan,
            "se": np.nan,
            "z": np.nan,
            "p_greater": np.nan,
            "p_less": np.nan,
        }
    m = float(x.mean())
    g = (x - m).groupby(c).sum()
    se = math.sqrt(float((g**2).sum())) / n if n > 1 else float("nan")
    z = m / se if se and se > 0 else float("nan")
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2))) if np.isfinite(z) else float("nan")
    return {
        "n": n,
        "clusters": int(c.nunique()),
        "mean": m,
        "se": se,
        "z": z,
        "p_greater": 1 - cdf if np.isfinite(cdf) else float("nan"),
        "p_less": cdf,
    }


def excess_table(
    events: pd.DataFrame, comparator: pd.DataFrame, k: int = 10
) -> pd.DataFrame:
    """Each resolved event's net_k minus that signal day's comparator mean (pure).

    events: symbol, side, signal_on, net.  comparator: trade_date, net (all liquid,
    resolved, unflagged stock-days). Days with no comparator are dropped.
    """
    base = comparator.groupby("trade_date")["net"].agg(
        base_mean="mean", base_n="size", base_hit=lambda s: (s > 0).mean()
    )
    e = events.merge(base, left_on="signal_on", right_index=True, how="inner")
    e["excess"] = e["net"] - e["base_mean"]
    e["hit_excess"] = (e["net"] > 0).astype(float) - e["base_hit"]
    return e


def evaluate(conn, today=None, path: Path = LOG) -> list[str]:
    """The weekly report: running estimates for H1/H2, never a verdict before a look."""
    from . import chart_research as v1
    from .data import universe
    from .features import bars

    cfg = config()
    k = int(cfg["outcome"]["primary_horizon"])
    today = pd.Timestamp(today or datetime.now().date())
    log = read(path)
    check_frozen(log)
    ev = log[log["symbol"] != ""].copy()
    lines = [
        f"CHART FORWARD TRACK v3 | registration {registration_hash()} | "
        f"report {today.date()} | forward days after {cfg['frozen_on']}",
        f"days recorded {log['day'].nunique() if len(log) else 0}, "
        f"events logged {len(ev)}",
    ]
    if ev.empty:
        lines.append("no forward events yet; nothing to evaluate")
        return lines
    first = pd.Timestamp(ev["signal_on"].min()) - pd.Timedelta(days=60)
    calendar = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT trade_date FROM trading_day "
            "WHERE trade_date >= %s ORDER BY 1",
            (str(first.date()),),
        ).fetchall()
    ]
    build = bars.current_build(conn)
    tiers = universe.tiers(conn, str(first.date()), str(today.date()))
    tiers["trade_date"] = pd.to_datetime(tiers["trade_date"])
    liquid_syms = sorted(tiers["symbol"].unique())
    rows = []
    for _, frame in bars.load_many(
        conn, liquid_syms, start=str(first.date()), build=build
    ):
        if not len(frame):
            continue
        out = v1.outcomes(frame, calendar)
        keep = ["symbol", "trade_date", f"net_{k}", f"known_on_{k}", f"flag__fill_{k}"]
        rows.append(out[keep])
    ret = pd.concat(rows, ignore_index=True)
    ret["trade_date"] = pd.to_datetime(ret["trade_date"])
    ret = ret.rename(
        columns={
            f"net_{k}": "net",
            f"known_on_{k}": "known_on",
            f"flag__fill_{k}": "flag",
        }
    )
    ok = (
        ret["net"].notna()
        & ~ret["flag"].fillna(False).astype(bool)
        & (pd.to_datetime(ret["known_on"]) <= today)
    )
    ret = ret[ok].merge(tiers[["symbol", "trade_date"]], on=["symbol", "trade_date"])
    ev["signal_on"] = pd.to_datetime(ev["signal_on"])
    ev = ev[ev["tier"] != ""].merge(
        ret.rename(columns={"trade_date": "signal_on"})[["symbol", "signal_on", "net"]],
        on=["symbol", "signal_on"],
    )
    tab = excess_table(ev, ret.rename(columns={"trade_date": "trade_date"}), k)
    lines.append(
        f"resolved decision-sample events (liquid, {k}-session outcome known): "
        f"{len(tab)}; comparator stock-days {len(ret):,}"
    )
    looks = cfg["inference"]["looks_at_resolved_events"]
    a = cfg["inference"]["alpha_per_look"]
    for name, h in cfg["hypotheses"].items():
        side = h["sides"][0]
        sub = tab[tab["side"] == side]
        st = cluster_stats(sub["excess"], sub["signal_on"].astype(str))
        p = st["p_greater"] if h["direction"] == "greater" else st["p_less"]
        reached = [x for x in looks if st["n"] >= x]
        nxt = next((x for x in looks if st["n"] < x), None)
        lo = st["mean"] - 1.96 * st["se"] if st["n"] > 1 else float("nan")
        hi = st["mean"] + 1.96 * st["se"] if st["n"] > 1 else float("nan")
        lines.append(
            f"  {name} ({side}, want excess "
            f"{'>' if h['direction'] == 'greater' else '<'} 0): "
            f"n {st['n']} on {st['clusters']} days | mean excess {st['mean']:+.4f} "
            f"(95% CI {lo:+.4f}..{hi:+.4f}) | one-sided p "
            f"{p_display(p, st['n'], looks)}"
        )
        if reached and p < a:
            lines.append(
                f"    >>> p < {a} at the n={reached[-1]} look: the registered rule "
                "says this hypothesis may be called supported"
            )
        else:
            lines.append(
                f"    no claim: next registered look at n={nxt}"
                if nxt
                else "    final look reached; no claim"
            )
    lines.append(
        "This is accumulating evidence with intervals, not a result, until a look "
        "is crossed."
    )
    return lines


if __name__ == "__main__":
    import sys

    from .data import db

    with db.connect() as conn:
        if len(sys.argv) > 1 and sys.argv[1] == "evaluate":
            report = evaluate(conn)
            REPORTS.mkdir(parents=True, exist_ok=True)
            (REPORTS / f"chart-forward-{datetime.now():%Y%m%d}.txt").write_text(
                "\n".join(report) + "\n", encoding="utf-8"
            )
            print("\n".join(report))
        elif len(sys.argv) > 2 and sys.argv[1] == "record":
            print(record_days(conn, sys.argv[2:]))
        else:
            raise SystemExit("usage: chart_forward evaluate | record DAY...")
