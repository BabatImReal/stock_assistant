"""The daily scan (doc §7.2-7.4): for one settled trading day, AT MOST ONE
proposal with its evidence, or "nothing strong today".

It trades the PRE-REGISTERED accepted set as-is: the ACCEPTs of the latest
holdout run in the hypothesis log (`accepted`). "Strong" means one of them
fired; there is no performance threshold, and no filter chosen after seeing the
holdout or its description. Most days nothing fires, and saying so is the
honest output (doc §7.3).

The rule, frozen in config/rules/protocol.yaml `daily_scan` (its hash goes into
every ledger row, report/paper.py):
  - a candidate is a (signal, stock) pair that fired on T's fingerprint (every
    condition known and true: unknown never fires), on a stock liquid on T,
    whose fillability can be judged at T (a dated exchange, not UPCoM: the
    holdout's gate never measured an accepted signal on any other);
  - ONE is proposed by the registered tie-breaker: HOSE before HNX (Ben's
    focus on the big, reliable companies), then the validate slice's net
    expectancy (per trade, frozen: it ranks, it is never a forward metric),
    then the 20-session mean traded value known at T, then the more liquid
    tier, then the symbol alphabetically.

Point in time: T's fingerprint rows (their own guards: no look-ahead, no window
across a gap), T's liquid set, traded value up to T. The context shown beside a
proposal reuses the engine: the holdout description (backtest.risk via
protocol.describe_holdout), the base rate (backtest.evidence, outcomes known
before T), and the look-alikes (backtest.neighbours, pool frozen before 2024).

It PROPOSES; Ben decides. Nothing here is a prediction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest.evidence import _hit
from ..backtest.protocol import _latest, families, vocabulary

# The fingerprint's market-wide context, shown as T's regime (doc §5.3).
REGIME = (
    "index_above_ma_50",
    "index_ma_50_slope",
    "index_change_20d",
    "index_drawdown_from_high",
    "breadth_advance_share",
    "breadth_advance_share_10d",
)
CANDIDATE_COLUMNS = [
    "symbol",
    "hypothesis",
    "family",
    "k",
    "tier",
    "exchange",
    "validate_expectancy",
    "traded_value_20d",
    "eligible",
    "why",
]
# How each tie-breaker key sorts: (column, ascending).
KEYS = {
    ("validate_expectancy", "highest"): ("validate_expectancy", False),
    ("traded_value_20d", "highest"): ("traded_value_20d", False),
    # data.universe: tier 3 = the most liquid, 1 = the least.
    ("tier", "most_liquid"): ("tier", False),
    ("symbol", "alphabetical"): ("symbol", True),
}


def block_hash(block: dict) -> str:
    return hashlib.sha256(
        json.dumps(block, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def accepted(proto: dict, log: pd.DataFrame) -> list:
    """The ACCEPTs of the latest holdout run, as registered hypotheses."""
    last = _latest(log, "holdout")
    ok = set(last.loc[last["survived"].astype(str) == "True", "hypothesis"])
    return [h for h in vocabulary(proto) if h.id in ok]


def family_of(ids) -> dict:
    """hypothesis id -> its display family (protocol.families), named by the
    family's most general member."""
    return {h: fam[0] for fam in families(list(ids)) for h in fam}


def traded_value_20d(values: pd.DataFrame, day, sessions: int) -> pd.Series:
    """Per symbol: the mean traded_value over its last `sessions` rows up to and
    including `day` (nothing after it), NaN with fewer rows."""
    d = values[pd.to_datetime(values["trade_date"]) <= pd.Timestamp(day)]
    last = d.sort_values("trade_date").groupby("symbol").tail(sessions)
    g = last.groupby("symbol")["traded_value"]
    return g.mean().where(g.count() >= sessions)


def candidates(
    rows: pd.DataFrame,
    hyps: list,
    proto: dict,
    validate_exp: dict,
    tv20: pd.Series,
    exchange: pd.DataFrame,
) -> pd.DataFrame:
    """Every (signal, stock) pair that fired on T, with the tie-breaker keys and
    `eligible` (False with the reason when it cannot be proposed).

    rows: T's fingerprint rows with `tier` (NaN = not liquid on T).
    exchange: symbol -> exchange, exchange_unknown on T.
    """
    fam = family_of([h.id for h in hyps])
    parts = []
    for h in hyps:
        hit = _hit(rows, h.query(proto))
        # 1.0 only: an unknown condition (NaN) never fires.
        fired = rows[(hit == 1.0).to_numpy()]
        parts.append(
            pd.DataFrame(
                {
                    "symbol": fired["symbol"].to_numpy(),
                    "hypothesis": h.id,
                    "family": fam[h.id],
                    "k": h.k,
                    "tier": fired["tier"].to_numpy(),
                }
            )
        )
    c = pd.concat(parts, ignore_index=True)
    c["validate_expectancy"] = c["hypothesis"].map(validate_exp).astype(float)
    c["traded_value_20d"] = c["symbol"].map(tv20).astype(float)
    ex = exchange.set_index("symbol")
    c["exchange"] = c["symbol"].map(ex["exchange"])
    unknown = c["symbol"].map(ex["exchange_unknown"]).fillna(True).astype(bool)
    why = pd.Series(None, index=c.index, dtype=object)
    why = why.mask(c["exchange"].eq("UPCOM"), "UPCoM: fillability not judgeable")
    why = why.mask(unknown, "exchange not dated: fillability not judgeable")
    why = why.mask(c["tier"].isna(), "not liquid on T")
    c["why"], c["eligible"] = why, why.isna()
    return c[CANDIDATE_COLUMNS]


def _column(t: dict) -> str:
    return "exchange" if t["key"] == "exchange" else KEYS[(t["key"], t["prefer"])][0]


def _sort_key(c: pd.DataFrame, t: dict) -> tuple[pd.Series, bool]:
    """(values, ascending) for one tie-breaker key. The exchange key sorts by
    its position in `prefer` (HOSE first); an unlisted exchange ranks last."""
    if t["key"] == "exchange":
        order = {x: i for i, x in enumerate(t["prefer"])}
        return c["exchange"].map(order).astype(float), True
    col, ascending = KEYS[(t["key"], t["prefer"])]
    return c[col], ascending


def rank(c: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """The eligible candidates, best first, by the registered tie-breaker."""
    e = c[c["eligible"]]
    keys = [_sort_key(e, t) for t in spec["tie_breaker"]]
    tmp = pd.DataFrame({f"k{i}": v for i, (v, _) in enumerate(keys)}, index=e.index)
    order = tmp.sort_values(
        list(tmp.columns),
        ascending=[a for _, a in keys],
        na_position="last",
        kind="stable",
    ).index
    return e.loc[order].reset_index(drop=True)


def lost_on(winner: pd.Series, other: pd.Series, spec: dict) -> str:
    """The first tie-breaker key on which `other` ranked below `winner`."""
    for t in spec["tie_breaker"]:
        col = _column(t)
        a, b = winner[col], other[col]
        if not (a == b or (pd.isna(a) and pd.isna(b))):
            if col == "traded_value_20d":  # thousands of VND -> billions
                return f"{t['key']} {b / 1e6:,.1f} vs {a / 1e6:,.1f} bn VND/day"
            return f"{t['key']} {b} vs {a}"
    return "identical keys"


@dataclass(frozen=True)
class Pick:
    day: str
    proposal: pd.Series | None  # the chosen candidate, or None: nothing strong
    ranked: pd.DataFrame  # eligible candidates, best first
    candidates: pd.DataFrame  # every pair that fired, eligible or not
    liquid: int  # stocks liquid on T
    regime: dict
    build_id: int
    featureset: str
    fp_code: str


def pick(conn, day, proto: dict | None = None, log: pd.DataFrame | None = None) -> Pick:
    """The registered scan for one settled trading day."""
    from ..backtest.protocol import load_protocol, read_log
    from ..data import universe
    from ..features import bars
    from ..patterns import fingerprint as fpm

    proto = proto or load_protocol()
    log = read_log() if log is None else log
    spec = proto["daily_scan"]
    hyps = accepted(proto, log)
    reg = proto["registered"]
    day = pd.Timestamp(day).date()
    build, fs = fpm.expected(conn)
    cols = sorted(
        {h.trigger for h in hyps}
        | {c for x in reg["conditions"].values() for c in x}
        | {"traded_value", *REGIME}
    )
    # Enough calendar days back for 20 sessions of traded value.
    start = str(day - pd.Timedelta(days=int(spec["traded_value_sessions"]) * 3))
    fp = fpm.load(build, fs, columns=cols, start=start, end=str(day))
    rows = fp.values[fp.values["trade_date"] == day]
    if rows.empty:
        raise ValueError(f"{day} is not a settled session in the fingerprint")
    uni = universe.tiers(conn, str(day), str(day))
    rows = rows.merge(
        uni[["symbol", "trade_date", "tier"]], on=["symbol", "trade_date"], how="left"
    )
    tv20 = traded_value_20d(fp.values, day, int(spec["traded_value_sessions"]))
    val = _latest(log, "validate").set_index("hypothesis")["expectancy"].to_dict()

    fired_symbols = set()
    for h in hyps:
        hit = _hit(rows, h.query(proto))
        fired_symbols |= set(rows.loc[(hit == 1.0).to_numpy(), "symbol"])
    ex = []
    for s in sorted(fired_symbols):  # only stocks that fired: a handful
        b = bars.load(conn, s, start=str(day), build=build)
        b = b[b["trade_date"] == day]
        if len(b):
            ex.append(
                {
                    "symbol": s,
                    "exchange": b["exchange"].iloc[0],
                    "exchange_unknown": bool(b["exchange_unknown"].iloc[0]),
                }
            )
    exchange = pd.DataFrame(ex, columns=["symbol", "exchange", "exchange_unknown"])

    c = candidates(rows, hyps, proto, val, tv20, exchange)
    ranked = rank(c, spec)
    regime = {
        x: rows[x].dropna().iloc[0] if rows[x].notna().any() else np.nan for x in REGIME
    }
    return Pick(
        day=str(day),
        proposal=ranked.iloc[0] if len(ranked) else None,
        ranked=ranked,
        candidates=c,
        liquid=int(rows["tier"].notna().sum()),
        regime=regime,
        build_id=build,
        featureset=fs.fingerprint,
        fp_code=fp.manifest["code"],
    )


# --- the evidence report ------------------------------------------------------


def _pct(x) -> str:
    return "n/a" if x is None or x != x else f"{x:+.2%}"


def header(p: Pick, proto: dict, net_provisional: bool, round_trip: float) -> list[str]:
    frozen = proto["paper_trading"]["frozen_on"]
    forward = pd.Timestamp(p.day) > pd.Timestamp(frozen)
    fee = (
        f"NET PROVISIONAL: all-in {round_trip:.2%} a round trip, broker fee NOT "
        "confirmed"
        if net_provisional
        else f"net at all-in {round_trip:.2%}"
    )
    return [
        f"DAILY SCAN {p.day} | it PROPOSES, Ben decides: this is not a prediction",
        f"  {fee}",
        f"  scan {block_hash(proto['daily_scan'])} | paper "
        f"{block_hash(proto['paper_trading'])}"
        f" | build {p.build_id} | fingerprint {p.featureset} code {p.fp_code}",
        "  FORWARD RECORD day"
        if forward
        else f"  BEFORE THE FREEZE ({frozen}): shown for information, NOT part of the "
        "forward record",
    ]


def funnel(p: Pick, n_signals: int) -> list[str]:
    r = p.regime
    above = {1: "yes", 0: "no"}.get(r["index_above_ma_50"], "unknown")
    lines = [
        f"REGIME on T (doc §5.3): index above its 50-day average {above}"
        f" | 50-day slope {_pct(r['index_ma_50_slope'])} | index 20-day change "
        f"{_pct(r['index_change_20d'])} | below its high "
        f"{_pct(r['index_drawdown_from_high'])}"
        f" | advancers today {r['breadth_advance_share']:.0%}, 10-day "
        f"{r['breadth_advance_share_10d']:.0%}",
        f"FUNNEL: {p.liquid} stocks liquid on T -> {len(p.candidates)} (signal, stock) "
        f"pairs of the {n_signals} accepted signals fired -> {len(p.ranked)} eligible",
    ]
    for _, c in p.candidates[~p.candidates["eligible"].astype(bool)].iterrows():
        lines.append(f"  not eligible: {c['symbol']} {c['hypothesis']} ({c['why']})")
    return lines


def entry_plan(p: Pick) -> list[str]:
    x = p.proposal
    return [
        f"PROPOSAL: {x['symbol']} ({x['exchange']}, liquidity tier "
        f"{int(x['tier'])} of 3, 3 = most liquid)"
        f" | signal {x['hypothesis']} | family {x['family']}",
        f"  entry: buy at the OPEN of the next session after {p.day}; NO TRADE if it "
        "opens at the ceiling",
        f"  exit: sell at the CLOSE of the {int(x['k'])}th session after the entry; if "
        "that close is at the floor, at the next close that is not (up to 5 sessions)",
        "  no stop and no target: none was registered or tested. The frozen rule is "
        "a time exit, and the holdout's worst trades below show the downside",
        "  what would invalidate it: an opening at the ceiling (no trade). Nothing "
        "else was tested: news vetoes are Ben's",
    ]


def runners_up(p: Pick, spec: dict) -> list[str]:
    if len(p.ranked) < 2:
        return ["RUNNERS-UP: none"]
    lines = ["RUNNERS-UP (registered tie-breaker, first key that decided):"]
    for _, r in p.ranked.iloc[1:6].iterrows():
        lines.append(
            f"  {r['symbol']} {r['hypothesis']}: lost on {lost_on(p.proposal, r, spec)}"
        )
    return lines


def history(proto: dict, log: pd.DataFrame, hid: str) -> list[str]:
    """The proposal's signal in the log: validate and holdout, per trade."""
    lines = []
    for slice_name in ("validate", "holdout"):
        r = _latest(log, slice_name).set_index("hypothesis").loc[hid]
        lines.append(
            f"  {slice_name}: edge {r['edge']:+.1%} (hit {r['hit_rate']:.1%} vs base "
            f"{r['base_rate']:.1%}) | net {r['expectancy']:+.2%} per trade | "
            f"{int(r['n_declustered'])} de-clustered trades | p {r['p']:.4f}"
        )
    return lines


def described(d: pd.Series) -> list[str]:
    """The holdout description at the registered cost (backtest.risk)."""
    return [
        f"  holdout, as followed (INFORMATION ONLY): avg per trade {_pct(d['avg'])} | "
        f"avg per SIGNAL DAY {_pct(d['per_day'])} over {int(d['signal_days'])} signal "
        "days (how the daily pick trades)",
        f"    avg win {_pct(d['avg_win'])} | avg loss {_pct(d['avg_loss'])} | best "
        f"{_pct(d['best'])} ({d['best_trade']}) | worst {_pct(d['worst'])} "
        f"({d['worst_trade']})",
        f"    one pick a day, in stakes: max drawdown {d['pick_drawdown_median']:+.2f} "
        f"median path, {d['pick_drawdown_bad']:+.2f} bad path | losing streak "
        f"{d['pick_streak_median']:.0f} median, {d['pick_streak_bad']:.0f} bad | up to "
        f"{int(d['max_open'])} stakes open at once",
    ]


def daily_scan(conn, day) -> tuple[Pick, list[str]]:
    """The evidence report for `day` (doc §7.4): the proposal and its honest
    context, or NOTHING STRONG TODAY."""
    from ..backtest import evidence as ev
    from ..backtest import forward_returns as fr
    from ..backtest import neighbours
    from ..backtest.protocol import (
        _holdout_gated,
        describe_holdout,
        load_protocol,
        read_log,
    )
    from ..data import universe
    from ..patterns import fingerprint as fpm

    proto, log = load_protocol(), read_log()
    hyps = accepted(proto, log)
    p = pick(conn, day, proto, log)
    costs = fr.load_costs()
    lines = header(p, proto, costs.provisional, costs.round_trip)
    lines += [
        f"ACCEPTED SIGNALS (the holdout's {len(hyps)} ACCEPTs, as-is): "
        + ", ".join(h.id for h in hyps)
    ]
    lines += funnel(p, len(hyps))
    if p.proposal is None:
        return p, [
            *lines,
            "NOTHING STRONG TODAY: no accepted signal fired on an "
            "eligible stock. Waiting is part of the method (doc §7.3).",
        ]
    x = p.proposal
    h = next(h for h in hyps if h.id == x["hypothesis"])
    lines += entry_plan(p)
    lines += ["ITS MEASURED HISTORY (per trade, from the hypothesis log):"]
    lines += history(proto, log, h.id)

    # The holdout description, re-derived by the engine (it refuses unless the
    # trades reproduce the logged ones), at the registered cost only.
    v = _holdout_gated(conn, proto, [h])
    one = log[(log["slice"] == "holdout") & (log["hypothesis"] == h.id)]
    d = describe_holdout(v, proto, one, costs.sale_tax_rate, costs=(costs.round_trip,))
    lines += described(d.iloc[0])

    # The base rate: every outcome known before T, through the gate.
    build, fs = fpm.expected(conn)
    cols = sorted({*h.query(proto)})
    before = str(pd.Timestamp(p.day).date())
    va = ev.validated(
        fpm.load(build, fs, columns=cols, end=before),
        fr.load(build, end=before),
        universe.tiers(conn, "2012-01-01", before),
        before=before,
    )
    e = ev.evidence(va, h.query(proto), h.k, x["symbol"])
    lines += ["BASE RATE (outcomes known before T; stock -> tier -> market):"]
    lines += ["  " + s for s in ev.stamp(e).splitlines()]
    lines += ["LOOK-ALIKES:"]
    lines += ["  " + s for s in neighbours.run(conn, x["symbol"], p.day)]
    lines += runners_up(p, proto["daily_scan"])
    return p, lines


if __name__ == "__main__":
    import sys

    from ..data import db
    from . import paper

    with db.connect() as conn:
        day = (
            sys.argv[1]
            if len(sys.argv) > 1
            else str(
                conn.execute("SELECT max(trade_date) FROM trading_day").fetchone()[0]
            )
        )
        p, lines = daily_scan(conn, day)
        row = paper.record(p)
    out = paper.REPORTS / f"scan-{p.day}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nledger: {row['outcome']} recorded for {row['day']} -> {paper.LEDGER}")
