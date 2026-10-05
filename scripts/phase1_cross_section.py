"""Phase 1 DEVELOPMENT run for Amendment 1 (docs section 12.4). One run per period.

    uv run python scripts/phase1_cross_section.py

Frozen before any result existed (commit da7881d). It computes the two documented
features, ranks the point-in-time liquid stocks each day, and reports the top decile's
excess 5-session net return over the same day's liquid cross-section, with a Newey-West
error. Nothing here is tuned; a different window, weight or threshold is a new
registration, not an edit. All periods are spent history: DEVELOPMENT, not proof.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research import cross_section as cs  # noqa: E402
from vnstock_research.backtest import forward_returns as fr  # noqa: E402
from vnstock_research.data import db, universe  # noqa: E402
from vnstock_research.features import bars  # noqa: E402

PERIODS = (
    ("development", "2012-01-01", "2019-12-31"),
    ("validation", "2020-01-01", "2023-12-31"),
    ("inspected_2024_on", "2024-01-01", "2026-09-21"),
)
K = 5


def main() -> int:
    out: list[str] = []

    def say(line: str = "") -> None:
        out.append(line)
        print(line, flush=True)

    conn = db.connect()
    build = bars.current_build(conn)
    say(
        f"PHASE 1 CORRECTED RERUN (docs 12.4a) | build {build} | k={K} | run {datetime.now():%F %T}"
    )
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s ORDER BY 1",
            (build,),
        ).fetchall()
    ]
    parts = []
    for _, frame in bars.load_many(conn, symbols, start="2010-06-01", build=build):
        if len(frame) >= cs.LONG:
            parts.append(cs.features(frame))
    feat = pd.concat(parts, ignore_index=True)
    feat["trade_date"] = pd.to_datetime(feat["trade_date"])
    say(f"feature rows {len(feat):,}; with both features {feat.dropna().shape[0]:,}")

    tiers = universe.tiers(conn, "2012-01-01", "2026-09-21")
    tiers["trade_date"] = pd.to_datetime(tiers["trade_date"])
    panel = feat.merge(tiers[["symbol", "trade_date"]], on=["symbol", "trade_date"])
    sel = cs.daily_selection(panel)
    say(
        f"liquid ranked stock-days {len(sel):,} over {sel['trade_date'].nunique()} days; "
        f"median stocks ranked per day {int(sel.groupby('trade_date').size().median())}"
    )

    rt = fr.load(build)
    r = rt.values
    r = r[
        ["symbol", "trade_date", f"net_{K}", f"known_on_{K}", f"flag__fill_{K}"]
    ].copy()
    r["trade_date"] = pd.to_datetime(r["trade_date"])
    r["known_on"] = pd.to_datetime(r[f"known_on_{K}"])
    r["flag"] = r[f"flag__fill_{K}"].fillna(False).astype(bool)
    r = r.rename(columns={f"net_{K}": "net_5"})[
        ["symbol", "trade_date", "net_5", "known_on", "flag"]
    ]
    sel = sel.merge(r, on=["symbol", "trade_date"], how="left")
    sel.loc[sel["flag"].fillna(False).astype(bool), "net_5"] = float("nan")

    results = {}
    for name, a, b in PERIODS:
        s = sel[(sel.trade_date >= a) & (sel.trade_date <= b)].copy()
        # purge: an outcome only counts if it was known by the end of the slice
        s.loc[s["known_on"] > pd.Timestamp(b), "net_5"] = float("nan")
        ex = cs.excess_series(s)
        if ex.empty:
            say(f"\n{name} {a}..{b}: no days")
            continue
        top = cs.newey_west_mean(ex["excess_top"], 5)
        t3 = cs.newey_west_mean(ex["excess_top3"], 5)
        t1 = cs.newey_west_mean(ex["excess_top1"], 5)
        hg = cs.newey_west_mean(ex["hit_gap"], 5)
        results[name] = top
        say(
            f"\n{name.upper()} {a}..{b} | {len(ex)} days | universe/day {ex['n_universe'].median():.0f}"
            f" | top decile/day {ex['n_top'].median():.0f}"
        )
        say(
            f"  top decile excess net_5 per stock: mean {top['mean']:+.4%}  NW se {top['se']:.4%}  "
            f"t {top['t']:+.2f}  | positive days {(ex['excess_top'] > 0).mean():.1%}"
        )
        say(f"  hit-rate gap (top - universe): {hg['mean']:+.2%} (t {hg['t']:+.2f})")
        say(
            f"  DESCRIPTIVE top-3 stocks: {t3['mean']:+.4%} (t {t3['t']:+.2f}) | "
            f"top-1 stock: {t1['mean']:+.4%} (t {t1['t']:+.2f})  [one pick a day is noisy]"
        )
        by_year = (
            ex.assign(y=pd.to_datetime(ex["trade_date"]).dt.year)
            .groupby("y")["excess_top"]
            .agg(["mean", "size"])
        )
        say(
            "  by year (mean top-decile excess): "
            + ", ".join(f"{y} {v['mean']:+.2%}" for y, v in by_year.iterrows())
        )
    d, v = results.get("development"), results.get("validation")
    if d and v:
        ok = d["mean"] > 0 and v["mean"] > 0
        say(
            f"\nPHASE 1 RULE (12.4): development excess {d['mean']:+.4%} and validation "
            f"{v['mean']:+.4%} -> "
            + (
                "both positive: PASS to Phase 2"
                if ok
                else "NOT both positive: the score is DROPPED, not tuned"
            )
        )
    say("These are spent-history DEVELOPMENT numbers, not evidence of a forward edge.")
    rep = Path(__file__).resolve().parent.parent / "research" / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / f"phase1-cross-section-{datetime.now():%Y%m%d}-corrected.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8"
    )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
