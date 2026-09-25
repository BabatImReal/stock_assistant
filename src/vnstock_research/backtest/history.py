"""Pattern history: a DESCRIPTIVE study, INFORMATION ONLY (doc §8.1, §8.3).

The question: how did each pattern behave historically, year by year and
month by month, 2012-2025? For every one of the 21 registered patterns and
the 8 structural strength signals (relative strength, trend stage), per
month / year / period, and split by the market regime on the signal day:
  - how often it fired (raw, and de-clustered);
  - the GROSS forward return at k = 3 and 5 sessions: mean, median, and the
    share that went up (hit rate: gross > 0);
  - the base rate for context: the same numbers over EVERY liquid stock-day
    where the signal could be judged, so "did it beat just being in the
    market?" is visible (edge = hit rate - base hit rate).

WHAT THIS IS NOT. It is not a hypothesis test and establishes no edge.
Across 29 signals x 2 horizons x 168 months x 3 regimes, chance alone makes
some cells look excellent. So, by construction:
  - nothing is written to any hypothesis log, no p-value is computed, and
    nothing here enters N;
  - there is no holdout path: the protocol's holdout loader is never called.
    2024-2025 is the already-SPENT holdout window, shown for understanding
    and labelled so, never for forming new tests;
  - 2026 is excluded entirely (incomplete, single-regime): `load_config`
    refuses a study end in 2026 or later.

POINT IN TIME. Every row goes through THE GATE (backtest.evidence.validated),
one period at a time, with `before` = the next period's start: the same
build for features and outcomes, flagged values blanked, only stock-days
liquid on t, fill-flagged outcomes blanked, and an outcome counted only if it
was KNOWN (known_on) before the period ended. Nothing resolved in 2026 enters.

Why de-clustered: a repeat fire on the same stock within k sessions of a
counted one shares its outcome window, so it is not new evidence. Every
forward-return statistic is on the de-clustered fires (the engine's rule);
the raw count is shown beside it. The base rate is over every eligible
stock-day (not de-clustered), as in the engine.

Run on Ben's machine (needs the database and the stored structural
fingerprint): `python -m vnstock_research.backtest.history`. It writes
research/reports/pattern-history.txt and research/reports/pattern-history.csv
and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..patterns.fingerprint import query
from .batch import gross
from .evidence import Validated, declustered, validated
from .forward_returns import CONFIG
from .protocol import REPORTS, load_protocol

HISTORY = CONFIG / "history.yaml"
# 2026 is excluded entirely (Ben, 2026-09-25).
FIRST_EXCLUDED = pd.Timestamp("2026-01-01")
BASE = "ALL_LIQUID"  # the market itself: every eligible liquid stock-day
REGIMES = ("all", "up", "down")
_TAGS = ("signal", "family", "k")  # added per signal after _describe
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
          "Nov", "Dec")  # fmt: skip
COLUMNS = [
    "signal",
    "family",
    "k",
    "level",  # month | year | period | all
    "regime",  # all | up | down (the index vs its MA50 on the signal day)
    "period",  # discover | validate | holdout_spent | all
    "year",
    "month",
    "fires_raw",
    "fires_declustered",
    "mean_gross",
    "median_gross",
    "hit_rate",  # share of de-clustered fires with gross > 0
    "base_n",
    "base_mean",
    "base_median",
    "base_hit",
    "edge",  # hit_rate - base_hit
    "excess_mean",  # mean_gross - base_mean
]
HEADER = (
    "INFORMATION ONLY. An exploratory DESCRIPTION of how every pattern behaved "
    "historically. It does NOT establish an edge and must not be treated as "
    "one: with this many cells, chance alone makes some look strong. No "
    "hypothesis log was written; the holdout stays sealed (no holdout path)."
)


# --- the study's definition -------------------------------------------------


def load_config(path: Path = HISTORY) -> dict:
    cfg = yaml.safe_load(Path(path).read_text())["study"]
    if pd.Timestamp(cfg["end"]) >= FIRST_EXCLUDED:
        raise ValueError(
            f"study end {cfg['end']}: 2026 is excluded entirely (incomplete, "
            "single-regime downtrend)"
        )
    return cfg


def signals(cfg: dict, proto: dict) -> dict:
    """name -> (family, conditions): the 21 registered triggers (read from the
    protocol, so the lists cannot drift), then the structural signals."""
    out = {t: ("pattern", {t: 1}) for t in proto["registered"]["triggers"]}
    out.update({n: ("structural", dict(c)) for n, c in cfg["structural"].items()})
    return out


def periods(cfg: dict) -> list:
    """[(name, start, end, before)]: `before` is the next period's start (the
    purge); for the last period, the day after the study end. The periods
    must tile the study with no gap and no overlap, and each spans whole
    years (a year belongs to exactly one period)."""
    out, expect = [], pd.Timestamp(cfg["start"])
    items = list(cfg["periods"].items())
    for i, (name, p) in enumerate(items):
        start, end = pd.Timestamp(p["start"]), pd.Timestamp(p["end"])
        if start != expect or (start.month, start.day, end.month, end.day) != (
            1,
            1,
            12,
            31,
        ):
            raise ValueError(f"period {name} must start {expect.date()} on whole years")
        before = (
            pd.Timestamp(items[i + 1][1]["start"])
            if i + 1 < len(items)
            else end + pd.Timedelta(days=1)
        )
        out.append((name, p["start"], p["end"], str(before.date())))
        expect = end + pd.Timedelta(days=1)
    if expect != pd.Timestamp(cfg["end"]) + pd.Timedelta(days=1):
        raise ValueError("the periods must end on the study end")
    return out


def columns(sigs: dict, cfg: dict) -> list:
    return sorted({c for _, q in sigs.values() for c in q} | {cfg["regime"]})


# --- the gated rows ---------------------------------------------------------


def gated_rows(v: Validated, name: str, start, end, ks, cols) -> pd.DataFrame:
    """The LIQUID rows of one period, out of the gate: the signal columns,
    the regime, and each horizon's gross return and blank reason. A row not
    liquid on t can never be eligible, so it is not carried."""
    if not isinstance(v, Validated):
        raise TypeError("gated_rows takes only a Validated table (validated())")
    x = v.values
    d = pd.to_datetime(x["trade_date"])
    keep = (d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end)) & x["tier"].notna()
    want = ["symbol", "trade_date", *cols]
    want += [c for k in ks for c in (f"ret_{k}", f"reason_{k}")]
    return x.loc[keep, want].assign(period=name).reset_index(drop=True)


# --- the aggregation ----------------------------------------------------------


def _regime(values: pd.Series) -> pd.Series:
    """1 -> up, 0 -> down, unknown stays unknown (it counts in 'all' only)."""
    return values.map({1.0: "up", 0.0: "down"}).astype(object)


def _frame(rows: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    d = pd.to_datetime(rows["trade_date"])
    return pd.DataFrame(
        {
            "period": rows["period"].to_numpy(),
            "year": d.dt.year.to_numpy(),
            "month": d.dt.month.to_numpy(),
            "regime": _regime(rows[cfg["regime"]].astype("float64")).to_numpy(),
        }
    )


LEVEL_KEYS = {
    "month": ["period", "year", "month"],
    "year": ["period", "year"],
    "period": ["period"],
    "all": [],
}


def _describe(e: pd.DataFrame) -> pd.DataFrame:
    """One row per (level, regime, group) from `e`: the eligible rows of one
    signal at one horizon, with columns period/year/month/regime, ret, occ
    (fired) and keep (fired and de-clustered)."""
    e = e.assign(up=(e["ret"] > 0).astype("float64"), _all="all")
    out = []
    for level, keys in LEVEL_KEYS.items():
        by = keys or ["_all"]
        for regime in REGIMES:
            sub = e if regime == "all" else e[e["regime"] == regime]
            if sub.empty:
                continue
            g = sub.groupby(by, sort=True)
            base = pd.DataFrame(
                {
                    "base_n": g.size(),
                    "base_mean": g["ret"].mean(),
                    "base_median": g["ret"].median(),
                    "base_hit": g["up"].mean(),
                }
            )
            kept = sub[sub["keep"]].groupby(by, sort=True)
            t = base.join(
                pd.DataFrame(
                    {
                        "fires_raw": sub[sub["occ"]].groupby(by, sort=True).size(),
                        "fires_declustered": kept.size(),
                        "mean_gross": kept["ret"].mean(),
                        "median_gross": kept["ret"].median(),
                        "hit_rate": kept["up"].mean(),
                    }
                ),
                how="left",
            ).reset_index()
            for c in ("fires_raw", "fires_declustered"):
                t[c] = t[c].fillna(0).astype("int64")
            t = t.drop(columns=["_all"], errors="ignore")
            t["level"], t["regime"] = level, regime
            if "period" not in keys:
                t["period"] = "all"
            out.append(t)
    if not out:  # the signal could never be judged: no eligible row at all
        return pd.DataFrame(columns=[c for c in COLUMNS if c not in _TAGS])
    t = pd.concat(out, ignore_index=True)
    t["edge"] = t["hit_rate"] - t["base_hit"]
    t["excess_mean"] = t["mean_gross"] - t["base_mean"]
    return t


def aggregate(rows: pd.DataFrame, sigs: dict, ks, cfg: dict) -> pd.DataFrame:
    """The tidy table: every signal (and the market base, ALL_LIQUID) x k x
    level x regime x group. `rows`: gated_rows of every period, stacked."""
    rows = rows.reset_index(drop=True)
    keys = _frame(rows, cfg)
    sessions = {x: i for i, x in enumerate(sorted(rows["trade_date"].unique()))}
    parts = []
    for k in ks:
        ret = rows[f"ret_{k}"]
        has = ret.notna()
        # The market itself: every eligible stock-day is an "occurrence", and
        # it is NOT de-clustered: it is the base, not a signal.
        e = keys[has.to_numpy()].assign(ret=ret[has].to_numpy(), occ=True, keep=True)
        parts.append(_describe(e).assign(signal=BASE, family="base", k=k))
        for name, (family, conditions) in sigs.items():
            hit = query(_Rows(rows), conditions).hit
            eligible = hit.notna() & has
            occ = eligible & (hit == 1.0)
            keep = pd.Series(False, index=rows.index)
            keep[occ[occ].index] = declustered(
                rows.loc[occ, "trade_date"], rows.loc[occ, "symbol"], sessions, k
            )
            m = eligible.to_numpy()
            e = keys[m].assign(
                ret=ret[eligible].to_numpy(),
                occ=occ[eligible].to_numpy(),
                keep=keep[eligible].to_numpy(),
            )
            parts.append(_describe(e).assign(signal=name, family=family, k=k))
    return pd.concat(parts, ignore_index=True)[COLUMNS]


class _Rows:
    """What patterns.fingerprint.query reads: an object with `.values`."""

    def __init__(self, values):
        self.values = values


def drops(rows: pd.DataFrame, ks) -> pd.DataFrame:
    """Per period and k: liquid stock-days, how many have an outcome, and how
    many the gate or the returns blanked, by reason. Nothing is silent."""
    out = []
    for k in ks:
        g = rows.groupby("period", sort=False)
        t = pd.DataFrame(
            {"liquid": g.size(), "with_outcome": g[f"ret_{k}"].count()}
        ).reset_index()
        r = rows.groupby(["period", f"reason_{k}"]).size()
        if len(r):
            r = r.unstack(fill_value=0)
            t = t.merge(r, left_on="period", right_index=True, how="left").fillna(0)
        out.append(t.assign(k=k))
    return pd.concat(out, ignore_index=True)


# --- the summary: fixed descriptive rules (config `summary`) -------------------


def consistency(table: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per signal and k: pooled numbers, how many judged years beat
    the base, whether the pooled edge leans on its best years, the up vs down
    market edges, and each period's edge."""
    rule = cfg["summary"]
    t = table[table["family"] != "base"]
    out = []
    for (name, k), g in t.groupby(["signal", "k"], sort=False):
        a = g[g["regime"] == "all"]
        if a.empty:
            continue  # never judged: nothing to describe
        pooled = a[a["level"] == "all"].iloc[0]
        yr = a[a["level"] == "year"].sort_values("year")
        judged = yr[yr["fires_declustered"] >= int(rule["min_declustered_year"])]
        contrib = judged["fires_declustered"] * judged["edge"]
        best = judged.loc[contrib[contrib > 0].sort_values(ascending=False).index].head(
            int(rule["drop_years"])
        )
        rest = yr[~yr["year"].isin(best["year"])]
        wins = (rest["fires_declustered"] * rest["hit_rate"]).sum()
        fires = rest["fires_declustered"].sum()
        base_n = rest["base_n"].sum()
        base = (rest["base_n"] * rest["base_hit"]).sum() / base_n if base_n else np.nan
        edge_rest = wins / fires - base if fires else np.nan
        edge = pooled["edge"]
        leans = bool(
            edge > 0
            and len(best)
            and not (edge_rest > float(rule["lean_share"]) * edge)
        )
        reg = {r: g[(g["level"] == "all") & (g["regime"] == r)] for r in ("up", "down")}
        by_reg = {
            r: (
                (int(x["fires_declustered"].iloc[0]), float(x["edge"].iloc[0]))
                if len(x)
                else (0, np.nan)
            )
            for r, x in reg.items()
        }
        per = a[a["level"] == "period"].set_index("period")
        out.append(
            {
                "signal": name,
                "family": pooled["family"],
                "k": k,
                "fires_declustered": int(pooled["fires_declustered"]),
                "fires_raw": int(pooled["fires_raw"]),
                "hit_rate": pooled["hit_rate"],
                "base_hit": pooled["base_hit"],
                "edge": edge,
                "mean_gross": pooled["mean_gross"],
                "base_mean": pooled["base_mean"],
                "years_judged": len(judged),
                "years_beat": int((judged["edge"] > 0).sum()),
                "years_mean_up": int((judged["mean_gross"] > 0).sum()),
                "best_years": [
                    (int(y), float(e))
                    for y, e in zip(best["year"], best["edge"], strict=True)
                ],
                "edge_without_best": edge_rest,
                "leans": leans,
                "up": by_reg["up"],
                "down": by_reg["down"],
                "regime_gap": by_reg["down"][1] - by_reg["up"][1],
                "periods": {
                    p: float(per.loc[p, "edge"]) if p in per.index else np.nan
                    for p in cfg["periods"]
                },
            }
        )
    s = pd.DataFrame(out)
    s["share_beat"] = s["years_beat"] / s["years_judged"].where(s["years_judged"] > 0)
    return s


def ranking(s: pd.DataFrame, cfg: dict, k: int) -> pd.DataFrame:
    """Most CONSISTENT forward increase at horizon k: signals with enough
    fires, ordered by the share of judged years whose hit rate beat the base,
    then by the pooled edge. A description, not a verdict."""
    rule = cfg["summary"]
    x = s[
        (s["k"] == k)
        & (s["fires_declustered"] >= int(rule["min_declustered_total"]))
        & (s["years_judged"] > 0)
    ]
    return x.sort_values(["share_beat", "edge"], ascending=False).head(int(rule["top"]))


def coin(years: int, beat: int) -> float:
    """The chance that a fair coin, one flip per year, beats the base in at
    least `beat` of `years` years: the yardstick for "consistent" when many
    signals are looked at. A scale for the reader, not a test of anything."""
    from math import comb

    return sum(comb(years, i) for i in range(beat, years + 1)) / 2**years


def _lean_label(r) -> str:
    if not r["edge"] > 0:
        return " -> no positive pooled edge to lean"
    return " -> LEANS ON THOSE YEARS" if r["leans"] else " -> holds without them"


# --- the report -------------------------------------------------------------


def _pct(x, signed=True, digits=1) -> str:
    if x != x:  # NaN
        return "-"
    return f"{x:+.{digits}%}" if signed else f"{x:.{digits}%}"


def _pts(x, digits=1) -> str:
    return "-" if x != x else f"{100 * x:+.{digits}f}"


def _period_of(cfg: dict, year: int) -> str:
    for name, p in cfg["periods"].items():
        if int(p["start"][:4]) <= year <= int(p["end"][:4]):
            return name
    return "?"


TAG = {"discover": "D", "validate": "V", "holdout_spent": "H*"}


def _grid(t: pd.DataFrame, cfg: dict, cell) -> list[str]:
    """A year x month grid; `cell(row)` renders one month; the last column is
    the whole year."""
    lines = ["  year     " + "".join(f"{m:>9}" for m in MONTHS) + f"{'| year':>11}"]
    years = range(int(cfg["start"][:4]), int(cfg["end"][:4]) + 1)
    month = t[t["level"] == "month"].set_index(["year", "month"])
    year = t[t["level"] == "year"].set_index("year")
    for y in years:
        tag = TAG.get(_period_of(cfg, y), "?")
        cells = [
            cell(month.loc[(y, m)]) if (y, m) in month.index else "·"
            for m in range(1, 13)
        ]
        total = cell(year.loc[y]) if y in year.index else "·"
        lines.append(
            f"  {y} {tag:<3} " + "".join(f"{c:>9}" for c in cells) + f"  | {total:>8}"
        )
    return lines


def _signal_cell(r) -> str:
    n = int(r["fires_declustered"])
    # Whole points in the grid, so a cell stays narrow; the CSV keeps the rest.
    return "·" if n == 0 else f"{n}:{_pts(r['edge'], 0)}"


def _base_cell(r) -> str:
    return f"{r['base_hit']:.0%}{100 * r['base_mean']:+.1f}"


def _year_table(t: pd.DataFrame, cfg: dict) -> list[str]:
    a = t[t["regime"] == "all"]
    up = t[t["regime"] == "up"]
    down = t[t["regime"] == "down"]
    lines = [
        "  year          raw  de-cl    mean  median     hit | base hit  base mean |"
        "   edge | up: n  edge | down: n  edge"
    ]

    def reg(x, level, key):
        r = x[(x["level"] == level) & key(x)]
        if r.empty:
            return f"{0:>5} {'-':>6}"
        r = r.iloc[0]
        return f"{int(r['fires_declustered']):>5} {_pts(r['edge']):>6}"

    def line(label, level, key):
        r = a[(a["level"] == level) & key(a)]
        if r.empty:
            return f"  {label:<9} (no eligible rows)"
        r = r.iloc[0]
        return (
            f"  {label:<9}{int(r['fires_raw']):>6} {int(r['fires_declustered']):>6}"
            f" {_pct(r['mean_gross'], digits=2):>7}"
            f" {_pct(r['median_gross'], digits=2):>7}"
            f" {_pct(r['hit_rate'], False):>7} | {_pct(r['base_hit'], False):>8}"
            f" {_pct(r['base_mean'], digits=2):>10} | {_pts(r['edge']):>6} |"
            f" {reg(up, level, key)} |   {reg(down, level, key)}"
        )

    for y in range(int(cfg["start"][:4]), int(cfg["end"][:4]) + 1):
        tag = TAG.get(_period_of(cfg, y), "?")
        lines.append(line(f"{y} {tag}", "year", lambda x, y=y: x["year"] == y))
    for p in cfg["periods"]:
        key = lambda x, p=p: x["period"] == p  # noqa: E731
        span = f"{cfg['periods'][p]['start'][2:4]}-{cfg['periods'][p]['end'][2:4]}"
        lines.append(line(f"{TAG[p]} {span}", "period", key))
    span = f"{cfg['start'][:4]}-{cfg['end'][2:4]}"
    lines.append(line(span, "all", lambda x: x["period"] == "all"))
    return lines


def report(table, dropped, summary, cfg, manifest, sigs) -> list[str]:
    ks = [int(k) for k in cfg["horizons"]]
    lines = [
        "PATTERN HISTORY 2012-01 .. 2025-12 (2026 EXCLUDED ENTIRELY)",
        "=" * 78,
        HEADER,
        "",
        f"build {manifest['build_id']} | fingerprint {manifest['fingerprint']} | "
        f"returns {manifest['returns']}",
        f"signals: {sum(f == 'pattern' for f, _ in sigs.values())} patterns + "
        f"{sum(f == 'structural' for f, _ in sigs.values())} structural | k = "
        f"{ks} sessions | GROSS returns (fee out of scope)",
        "periods: "
        + " | ".join(
            f"{TAG[n]} {n} {p['start'][:4]}-{p['end'][:4]}"
            for n, p in cfg["periods"].items()
        ),
        "  H* = the ALREADY-SPENT holdout window: shown for understanding, NOT for "
        "forming new tests.",
        "point in time: every period through the gate (liquid on t, flagged values "
        "and fill-flagged outcomes blanked), with each outcome KNOWN before the next "
        "period starts (the last: before 2026-01-01).",
        f"regime = {cfg['regime']} on the signal day: up = VN-Index above its MA50, "
        "down = below; unknown counts in 'all' only.",
        "fires: raw = fired with a known outcome at k; de-cl = de-clustered (a "
        "repeat within k sessions on the same stock shares the outcome window). "
        "mean / median / hit are over the de-clustered fires.",
        "hit = share with GROSS return > 0. base = the same over EVERY liquid "
        "stock-day where the signal could be judged. edge = hit - base hit, in "
        "points.",
        "Grids: cell = de-clustered fires : edge (points); · = no fire. The "
        "month x regime splits and every mean/median by month are in the CSV.",
        "",
        "WHAT THE GATE AND THE RETURNS BLANKED (liquid stock-days):",
    ]
    for _, r in dropped.iterrows():
        extra = {
            c: int(r[c])
            for c in dropped.columns
            if c not in ("period", "liquid", "with_outcome", "k") and r[c]
        }
        lines.append(
            f"  k={int(r['k'])} {r['period']:<14} liquid {int(r['liquid']):>9,} | "
            f"with outcome {int(r['with_outcome']):>9,} | blanked {extra}"
        )
    lines += ["", "THE MARKET ITSELF (ALL_LIQUID): cell = base hit% and mean gross %"]
    for k in ks:
        base = table[
            (table["signal"] == BASE) & (table["k"] == k) & (table["regime"] == "all")
        ]
        lines += [f" k={k}", *_grid(base, cfg, _base_cell)]
    for name, (family, _) in sigs.items():
        lines += ["", f"=== {name} ({family}) " + "=" * max(0, 60 - len(name))]
        for k in ks:
            t = table[(table["signal"] == name) & (table["k"] == k)]
            lines += [f" k={k}: by year (regime split = up / down market)"]
            lines += _year_table(t, cfg)
            lines += [f" k={k}: year x month, cell = de-cl fires : edge (points)"]
            lines += _grid(t[t["regime"] == "all"], cfg, _signal_cell)
    lines += ["", *summary_lines(summary, cfg)]
    return lines


def summary_lines(s: pd.DataFrame, cfg: dict) -> list[str]:
    rule = cfg["summary"]
    lines = [
        "SUMMARY (descriptive; fixed rules in config/rules/history.yaml `summary`)",
        "=" * 78,
        HEADER,
        f"Consistency = judged years (>= {rule['min_declustered_year']} de-cl "
        "fires) in which the hit rate beat the base. Ranked by that share, then by "
        f"the pooled edge; >= {rule['min_declustered_total']} de-cl fires in "
        "2012-2025 to be ranked.",
        f"LEANS = with its best {rule['drop_years']} years removed (most excess "
        f"wins, fires x edge) the pooled edge falls to <= {rule['lean_share']:.0%} "
        "of itself: it rests on one or two years.",
        f"Up vs down markets differ when the two pooled edges are >= "
        f"{100 * float(rule['regime_gap']):.0f} points apart.",
    ]
    gap = float(rule["regime_gap"])
    for k in [int(k) for k in cfg["horizons"]]:
        top = ranking(s, cfg, k)
        lines += ["", f"MOST CONSISTENT FORWARD INCREASE, k={k}:"]
        if top.empty:
            lines.append("  (no signal has enough fires)")
        for i, (_, r) in enumerate(top.iterrows(), 1):
            best = ", ".join(f"{y} ({_pts(e)})" for y, e in r["best_years"]) or "-"
            if r["regime_gap"] != r["regime_gap"]:
                regime = "one regime only"
            elif r["regime_gap"] >= gap:
                regime = "stronger in DOWN markets"
            elif r["regime_gap"] <= -gap:
                regime = "stronger in UP markets"
            else:
                regime = "similar in up and down markets"
            per = " ".join(f"{TAG[p]} {_pts(e)}" for p, e in r["periods"].items())
            lines += [
                f"  {i:>2}. {r['signal']} ({r['family']}): beat the base in "
                f"{r['years_beat']}/{r['years_judged']} judged years (mean gross > 0 "
                f"in {r['years_mean_up']}); pooled edge {_pts(r['edge'])} pts on "
                f"{r['fires_declustered']:,} de-cl fires, hit "
                f"{_pct(r['hit_rate'], False)} vs base {_pct(r['base_hit'], False)}, "
                f"mean {_pct(r['mean_gross'], digits=2)} vs "
                f"{_pct(r['base_mean'], digits=2)}",
                f"      driven by {best}; without them edge "
                f"{_pts(r['edge_without_best'])} pts" + _lean_label(r),
                f"      up market {_pts(r['up'][1])} (n {r['up'][0]:,}) vs down "
                f"{_pts(r['down'][1])} (n {r['down'][0]:,}): {regime} | by "
                f"period: {per}",
            ]
        k_s = s[(s["k"] == k) & (s["years_judged"] > 0)]
        leans = k_s[k_s["leans"]]
        if len(top):
            first = top.iloc[0]
            j, b = int(first["years_judged"]), int(first["years_beat"])
            c = coin(j, b)
            lines.append(
                f"  For scale (luck alone): a coin flip per year beats the base in "
                f">= {b} of {j} years {c:.1%} of the time, so among the "
                f"{len(k_s)} signals about {c * len(k_s):.1f} would look like #1 by "
                "chance, before any look at months or regimes."
            )
        lines += [
            f"  All signals at k={k} with a positive pooled edge: "
            f"{int((k_s['edge'] > 0).sum())} of {len(k_s)}; of those, "
            f"{len(leans)} lean on 1-2 years: "
            + (", ".join(leans["signal"]) or "none"),
            "  Stronger in DOWN markets: "
            + (", ".join(k_s.loc[k_s["regime_gap"] >= gap, "signal"]) or "none"),
            "  Stronger in UP markets: "
            + (", ".join(k_s.loc[k_s["regime_gap"] <= -gap, "signal"]) or "none"),
        ]
    lines += [
        "",
        "Read with care: many signals x years x months x regimes were looked at, "
        "and nothing here was tested or corrected for that. A pattern that looks "
        "consistent here is at most an idea for a NEW, registered test on data no "
        "run has used (the forward paper-trading ledger); 2024-2025 is already "
        "spent and cannot serve.",
    ]
    return lines


# --- running it ---------------------------------------------------------------


def study(load, cfg: dict, proto: dict):
    """(table, dropped, summary, manifest) from `load(start, end, before)`,
    which returns a Validated table for one period (the gate applied)."""
    sigs = signals(cfg, proto)
    cols = columns(sigs, cfg)
    ks = [int(k) for k in cfg["horizons"]]
    parts, manifest = [], None
    for name, start, end, before in periods(cfg):
        v = load(start, end, before)
        manifest = manifest or v.manifest
        parts.append(gated_rows(v, name, start, end, ks, cols))
    rows = pd.concat(parts, ignore_index=True)
    if len(rows) and pd.to_datetime(rows["trade_date"]).max() >= FIRST_EXCLUDED:
        raise ValueError("a 2026 row reached the study: 2026 is excluded entirely")
    table = aggregate(rows, sigs, ks, cfg)
    return table, drops(rows, ks), consistency(table, cfg), manifest


def write(table, dropped, summary, cfg, manifest, sigs, reports: Path = REPORTS):
    """The two outputs, and nothing else: the readable report and the tidy
    CSV. No log of any kind is written."""
    reports = Path(reports)
    reports.mkdir(parents=True, exist_ok=True)
    csv = reports / "pattern-history.csv"
    txt = reports / "pattern-history.txt"
    table.to_csv(csv, index=False, float_format="%.6g")
    txt.write_text(
        "\n".join(report(table, dropped, summary, cfg, manifest, sigs)) + "\n",
        encoding="utf-8",
    )
    return txt, csv


def run(conn, reports: Path = REPORTS):
    """On the stored STRUCTURAL fingerprint (features.yaml + structural.yaml on
    the current build: the registered measures and the structural ones) and
    the stored returns, read as GROSS."""
    from .. import structural
    from ..data import universe
    from ..patterns import fingerprint as fpm
    from . import forward_returns as fr

    cfg, proto = load_config(), load_protocol()
    sigs = signals(cfg, proto)
    build, fs = structural.expected(conn)
    uni = universe.tiers(conn, cfg["start"], cfg["end"])

    def load(start, end, before):
        fp = fpm.load(build, fs, columns=columns(sigs, cfg), start=start, end=end)
        rt = fr.load(build, start=start, end=end)
        return validated(fp, gross(rt), uni, before=before)

    table, dropped, summary, manifest = study(load, cfg, proto)
    return write(table, dropped, summary, cfg, manifest, sigs, reports)


if __name__ == "__main__":
    from ..data import db

    with db.connect() as conn:
        for path in run(conn):
            print(path)
