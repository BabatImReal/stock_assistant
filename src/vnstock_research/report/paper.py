"""Paper trading: the forward test of the accepted signals (doc §8.2).

The holdout is spent, so the only clean data left is days that have not
happened yet. Each run of the daily scan RECORDS its proposal (or none) in an
append-only ledger, research/paper_ledger.csv (in git). A separate step SCORES
the proposals whose outcomes have resolved.

The ledger:
  - one row per signal day, written once. Re-running a day is safe: the same
    proposal returns the recorded row, and a DIFFERENT one is refused (the
    record is never rewritten);
  - every row carries the hashes of the frozen `daily_scan` and
    `paper_trading` blocks (config/rules/protocol.yaml), the hypothesis
    protocol, the holdout run it trades, the build, the fingerprint and the
    code. Once the ledger has a row, a changed block is refused;
  - `forward` = the day is strictly after `paper_trading.frozen_on`. Earlier
    days are BEFORE THE FREEZE: shown apart, never in the forward record.

Scoring is PER SIGNAL DAY: one proposal, one stake, its stored outcome
(backtest.forward_returns: entry at the next open, exit at the signal's k, no
buy at the ceiling, a floor-locked exit waits, net at the all-in cost). A
proposal is
  scored   it has a net return;
  pending  its outcome is not known yet;
  void     decided at entry with no trade (e.g. the next open was at the
           ceiling): no stake was placed. Counted, never scored;
  stuck    a stake was placed but there is no return (a gap in the hold, the
           data ends, an exit locked at the floor past the cap). It withholds
           any verdict until Ben rules on it: dropping it would hide a loss.
The verdict is the registered rule (`paper_trading.verdict`), on the aggregate
forward record; per family is information only. While the broker fee is
PROVISIONAL no PASS or FAIL is declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .. import store
from ..backtest import risk
from ..backtest.protocol import _latest, protocol_hash
from .scan import Pick, block_hash

LEDGER = store.PKG.parents[1] / "research" / "paper_ledger.csv"
REPORTS = LEDGER.parent / "reports"
COLUMNS = [
    "day",
    "forward",
    "outcome",  # proposal | nothing
    "symbol",
    "hypothesis",
    "family",
    "k",
    "fired",  # (signal, stock) pairs that fired
    "eligible",
    "validate_expectancy",
    "traded_value_20d",
    "tier",
    "scan",
    "paper",
    "protocol",
    "holdout_run",
    "build_id",
    "featureset",
    "fp_code",
    "code",
    "recorded_at",
]
# The code a proposal depends on.
CODE = ("report", "backtest", "data", "features", "patterns", "store.py")


def read(path: Path = LEDGER) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype={"day": str, "symbol": str})


def check_frozen(proto: dict, ledger: pd.DataFrame) -> None:
    """Once the ledger has a row, the registered blocks may not change."""
    for name, col in (("daily_scan", "scan"), ("paper_trading", "paper")):
        seen = set(ledger[col].dropna())
        now = block_hash(proto[name])
        if seen and seen != {now}:
            raise ValueError(
                f"the registered `{name}` block changed after the ledger's first "
                f"row (ledger {sorted(seen)}, now {now}); only Ben may change it"
            )


def is_forward(day, proto: dict) -> bool:
    return pd.Timestamp(day) > pd.Timestamp(proto["paper_trading"]["frozen_on"])


def row_for(p: Pick, proto: dict, log: pd.DataFrame) -> dict:
    x = p.proposal
    chosen = (
        {}
        if x is None
        else {
            "symbol": x["symbol"],
            "hypothesis": x["hypothesis"],
            "family": x["family"],
            "k": int(x["k"]),
            "validate_expectancy": float(x["validate_expectancy"]),
            "traded_value_20d": float(x["traded_value_20d"]),
            "tier": int(x["tier"]),
        }
    )
    return {
        **dict.fromkeys(COLUMNS),
        **chosen,
        "day": p.day,
        "forward": is_forward(p.day, proto),
        "outcome": "nothing" if x is None else "proposal",
        "fired": len(p.candidates),
        "eligible": len(p.ranked),
        "scan": block_hash(proto["daily_scan"]),
        "paper": block_hash(proto["paper_trading"]),
        "protocol": protocol_hash(proto),
        "holdout_run": _latest(log, "holdout")["run_id"].iloc[0],
        "build_id": p.build_id,
        "featureset": p.featureset,
        "fp_code": p.fp_code,
        "code": store.code_hash(CODE),
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _same(a, b) -> bool:
    # A "nothing" day has no symbol: None when made, NaN once read from the CSV.
    return a == b or (pd.isna(a) and pd.isna(b))


def record(p: Pick, proto=None, log=None, path: Path = LEDGER) -> dict:
    """Append the day's proposal (or none), once. Returns the ledger row."""
    from ..backtest.protocol import load_protocol, read_log

    proto = proto or load_protocol()
    log = read_log() if log is None else log
    ledger = read(path)
    check_frozen(proto, ledger)
    new = row_for(p, proto, log)
    old = ledger[ledger["day"] == p.day]
    if len(old):
        o = old.iloc[0]
        if not all(_same(o[c], new[c]) for c in ("outcome", "symbol", "hypothesis")):
            raise ValueError(
                f"{p.day} is already recorded as {o['outcome']} {o['symbol']} "
                f"{o['hypothesis']}; now {new['outcome']} {new['symbol']} "
                f"{new['hypothesis']}. The ledger is append-only: not rewritten"
            )
        return o.to_dict()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([new])[COLUMNS].to_csv(
        path, mode="a", header=not path.exists(), index=False
    )
    return new


# --- scoring, per signal day ------------------------------------------------


def outcomes(ledger: pd.DataFrame, returns: pd.DataFrame, calendar) -> pd.DataFrame:
    """One row per PROPOSAL: its status and, when scored, its net return.

    returns: stored forward returns (symbol, trade_date, net_k, reason_k,
    known_on_k); calendar: every market session."""
    cal = sorted(pd.to_datetime(pd.Series(list(calendar))).dt.date.unique())
    rt = returns.assign(trade_date=pd.to_datetime(returns["trade_date"]).dt.date)
    rt = rt.set_index(["symbol", "trade_date"])
    props = ledger[ledger["outcome"] == "proposal"]
    out = []
    for _, r in props.iterrows():
        day, k = pd.Timestamp(r["day"]).date(), int(r["k"])
        later = [d for d in cal if d > day]
        entry = later[0] if later else None
        key = (r["symbol"], day)
        net = reason = known = None
        if key in rt.index:
            x = rt.loc[key]
            net, reason, known = x[f"net_{k}"], x[f"reason_{k}"], x[f"known_on_{k}"]
        if key not in rt.index or entry is None or reason == "pending":
            status = "pending"
        elif pd.notna(net):
            status = "scored"
        elif pd.notna(known) and pd.Timestamp(known).date() <= entry:
            status = "void"
        else:
            status = "stuck"
        out.append(
            {
                "day": day,
                "forward": str(r["forward"]) == "True",
                "symbol": r["symbol"],
                "hypothesis": r["hypothesis"],
                "family": r["family"],
                "k": k,
                "status": status,
                "reason": reason,
                "net": float(net) if status == "scored" else np.nan,
            }
        )
    return pd.DataFrame(
        out,
        columns=[
            "day",
            "forward",
            "symbol",
            "hypothesis",
            "family",
            "k",
            "status",
            "reason",
            "net",
        ],
    )


def summary(o: pd.DataFrame) -> dict:
    """The record of scored signal days, in signal-day order, in STAKES."""
    s = o[o["status"] == "scored"].sort_values("day")
    net = s["net"].to_numpy(float)
    months = s.groupby(pd.to_datetime(s["day"]).dt.to_period("M"))["net"].sum()
    return {
        "signal_days": len(s),
        "cumulative": float(net.sum()),
        "drawdown": risk.max_drawdown(net),
        "hit_rate": float((net > 0).mean()) if len(net) else np.nan,
        "months": len(months),
        "positive_months": int((months > 0).sum()),
        "first": s["day"].min() if len(s) else None,
        "last": s["day"].max() if len(s) else None,
        **{
            f"n_{x}": int((o["status"] == x).sum())
            for x in ("scored", "pending", "void", "stuck")
        },
    }


def verdict(sm: dict, rule: dict, fee_provisional: bool) -> str:
    """The registered paper-trading rule on the aggregate forward record."""
    v = rule["verdict"]
    span_ok = sm["first"] is not None and pd.Timestamp(sm["last"]) >= pd.Timestamp(
        sm["first"]
    ) + pd.DateOffset(months=int(v["min_span_months"]))
    if sm["signal_days"] < int(v["min_signal_days"]) or not span_ok:
        return (
            f"NO VERDICT YET: {sm['signal_days']} of {v['min_signal_days']} scored "
            f"signal days, spanning at least {v['min_span_months']} months needed"
        )
    if sm["n_stuck"]:
        return f"WITHHELD: {sm['n_stuck']} stuck proposals need Ben's ruling"
    fail = (sm["cumulative"] <= float(v["fail"]["cumulative_at_most"])) or (
        sm["drawdown"] < float(v["fail"]["drawdown_below"])
    )
    ok = (
        sm["cumulative"] > float(v["pass"]["cumulative_above"])
        and sm["drawdown"] >= float(v["pass"]["drawdown_at_least"])
        and sm["positive_months"] * 2 > sm["months"]
    )
    word = "FAIL" if fail else "PASS" if ok else "PROVISIONAL"
    if word != "PROVISIONAL" and fee_provisional:
        return f"would be {word}, NOT DECLARED: the broker fee is PROVISIONAL"
    return word


@dataclass(frozen=True)
class Scorecard:
    outcomes: pd.DataFrame
    forward: dict
    before: dict
    verdict: str
    families: pd.DataFrame


def score(ledger, returns, calendar, proto: dict, fee_provisional: bool) -> Scorecard:
    o = outcomes(ledger, returns, calendar)
    fwd = o[o["forward"]]
    fam = (
        fwd[fwd["status"] == "scored"]
        .groupby("family")["net"]
        .agg(signal_days="size", cumulative="sum", hit_rate=lambda x: (x > 0).mean())
    )
    sm = summary(fwd)
    return Scorecard(
        outcomes=o,
        forward=sm,
        before=summary(o[~o["forward"]]),
        verdict=verdict(sm, proto["paper_trading"], fee_provisional),
        families=fam,
    )


def score_report(sc: Scorecard, ledger: pd.DataFrame, proto, fee_provisional) -> list:
    def block(title, sm):
        return [
            f"{title}: {sm['signal_days']} scored signal days "
            f"(pending {sm['n_pending']}, void {sm['n_void']}, stuck {sm['n_stuck']})",
            f"  cumulative {sm['cumulative']:+.3f} stakes | max drawdown "
            f"{sm['drawdown']:+.3f} stakes | hit rate (net > 0) "
            + ("n/a" if sm["hit_rate"] != sm["hit_rate"] else f"{sm['hit_rate']:.0%}")
            + f" | months net positive {sm['positive_months']} of {sm['months']}",
        ]

    fwd_days = ledger[ledger["forward"].astype(str) == "True"]
    lines = [
        f"PAPER TRADING, PER SIGNAL DAY | paper {block_hash(proto['paper_trading'])} "
        f"| forward record = days after {proto['paper_trading']['frozen_on']}"
        + (" | NET PROVISIONAL (broker fee not confirmed)" if fee_provisional else ""),
        f"ledger: {len(ledger)} days recorded, {len(fwd_days)} forward, of which "
        f"{int((fwd_days['outcome'] == 'proposal').sum())} with a proposal",
        *block("FORWARD RECORD", sc.forward),
        f"  VERDICT (registered rule, aggregate): {sc.verdict}",
        "  per family (INFORMATION ONLY; the bar is on the aggregate):",
    ]
    for fam, r in sc.families.iterrows():
        lines.append(
            f"    {fam}: {int(r['signal_days'])} days, {r['cumulative']:+.3f} stakes, "
            f"hit {r['hit_rate']:.0%}"
        )
    lines += block("BEFORE THE FREEZE (information, NOT the forward record)", sc.before)
    for _, r in sc.outcomes.iterrows():
        tag = "forward" if r["forward"] else "before the freeze"
        res = (
            f"net {r['net']:+.2%}"
            if r["status"] == "scored"
            else (
                f"{r['status']}"
                + (f" ({r['reason']})" if isinstance(r["reason"], str) else "")
            )
        )
        lines.append(f"  {r['day']} {r['symbol']} {r['hypothesis']}: {res} [{tag}]")
    return lines


def run_score(conn, path: Path = LEDGER) -> list[str]:
    from ..backtest import forward_returns as fr
    from ..backtest.protocol import load_protocol
    from ..patterns import fingerprint as fpm

    proto = load_protocol()
    ledger = read(path)
    check_frozen(proto, ledger)
    build, _ = fpm.expected(conn)
    first = ledger["day"].min() if len(ledger) else None
    rt = fr.load(build, start=first) if first else None
    calendar = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT trade_date FROM trading_day WHERE trade_date >= %s "
            "ORDER BY 1",
            (first or "2100-01-01",),
        ).fetchall()
    ]
    returns = (
        rt.values if rt is not None else pd.DataFrame(columns=["symbol", "trade_date"])
    )
    costs = fr.load_costs()
    sc = score(ledger, returns, calendar, proto, costs.provisional)
    return [
        f"scored on build {build}",
        *score_report(sc, ledger, proto, costs.provisional),
    ]


if __name__ == "__main__":
    import sys

    from ..data import db
    from .scan import pick

    with db.connect() as conn:
        if sys.argv[1] == "record":
            for day in sys.argv[2:]:
                row = record(pick(conn, day))
                print(day, row["outcome"], row["symbol"], row["hypothesis"])
        elif sys.argv[1] == "score":
            print("\n".join(run_score(conn)))
        else:
            raise SystemExit("use: record DAY [DAY ...] | score")
