"""The one-screen daily brief for Ben: the verdict in plain words, then the evidence.

Read-only. It reuses the registered scan (report/scan.py) and the scored ledger
(report/paper.py) and adds NOTHING to what they measure; it only decides how strongly to
word the day. The wording rule below uses registered numbers only, and the result is
mostly "nothing strong today" on purpose: until a forward record says otherwise, no
signal has earned a stronger word (decisions log, 2026-10-05).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paper, scan


def strength(per_day: float, fwd_days: int, fwd_cum: float, min_days: int) -> str:
    """STRONG / UNPROVEN / WEAK for one fired signal (pure).

    per_day: the signal's holdout net per SIGNAL DAY at the registered cost (the number
    that matches how one daily pick trades); fwd_days / fwd_cum: the whole forward
    record's scored signal days and cumulative net in stakes.
    """
    if per_day != per_day or per_day <= 0:
        return "WEAK"  # in its own holdout, one pick a day lost money
    if fwd_days < min_days:
        return "UNPROVEN"  # positive in the holdout, no forward record yet
    return "STRONG" if fwd_cum > 0 else "WEAK"


def headline(day: str, label: str | None, symbol: str | None) -> str:
    if label == "STRONG":
        return f"{day}: STRONG candidate {symbol} (still research, Ben decides)"
    if label is None:
        return f"{day}: NOTHING STRONG TODAY (no accepted signal fired)"
    return f"{day}: NOTHING STRONG TODAY ({symbol} fired, labelled {label})"


def scorecard_lines(o: pd.DataFrame) -> list[str]:
    """Every forward proposal and what became of it (pure)."""
    fwd = o[o["forward"].astype(bool)].sort_values("day")
    if fwd.empty:
        return ["  no forward proposals yet"]
    lines = []
    for _, r in fwd.iterrows():
        res = (
            f"net {r['net']:+.2%}"
            if r["status"] == "scored"
            else f"{r['status']} (5-session result not in yet)"
            if r["status"] == "pending"
            else r["status"]
        )
        lines.append(f"  {r['day']} {r['symbol']}: {res}")
    scored = fwd[fwd["status"] == "scored"]
    lines.append(
        f"  running total: {len(scored)} scored, {scored['net'].sum():+.3f} stakes"
        if len(scored)
        else "  running total: nothing scored yet"
    )
    return lines


def market_line(r: dict) -> str:
    above = {1: "above", 0: "below"}.get(r.get("index_above_ma_50"), "unknown vs")
    adv, adv10 = r.get("breadth_advance_share"), r.get("breadth_advance_share_10d")
    pct = lambda x: "n/a" if x is None or x != x else f"{x:.0%}"  # noqa: E731
    return (
        f"Market: VN-Index {above} its 50-day average | advancers today {pct(adv)}, "
        f"10-day {pct(adv10)}"
    )


def brief(conn, day: str) -> tuple[str, list[str]]:
    """(headline, lines) for `day`. The headline goes into the notification."""
    from .. import chart_forward as cf
    from ..backtest import forward_returns as fr

    p = scan.pick(conn, day)
    _, ledger, proto, _, sc = paper.scorecard(conn)
    min_days = int(proto["paper_trading"]["verdict"]["min_signal_days"])
    label = symbol = None
    lines = [market_line(p.regime)]
    if p.proposal is not None:
        symbol, hid = p.proposal["symbol"], p.proposal["hypothesis"]
        text = scan.HOLDOUT_DESCRIPTION.read_text(encoding="utf-8")
        d = scan.frozen_description(text, hid, fr.load_costs().round_trip)
        label = strength(
            d["per_day"], sc.forward["signal_days"], sc.forward["cumulative"], min_days
        )
        lines += [
            f"Engine: {symbol} fired {hid}  ->  {label}",
            f"  its holdout: {d['avg']:+.2%} per trade, but {d['per_day']:+.2%} per "
            f"SIGNAL DAY ({int(d['signal_days'])} days) - one pick a day is what you "
            "would actually trade",
            "  a time exit only, no stop; full evidence in the scan report",
        ]
    else:
        lines.append("Engine: no accepted signal fired on an eligible stock.")
    lines += [
        f"Forward record ({sc.forward['signal_days']} of {min_days} scored signal days "
        f"needed before any verdict): {sc.verdict}",
        *scorecard_lines(sc.outcomes),
    ]
    log = cf.read()
    ev = log[log["symbol"] != ""] if len(log) else log
    lines.append(
        f"Chart track (shadow): {log['day'].nunique() if len(log) else 0} forward "
        "days, "
        f"{len(ev)} events logged; no verdict before 60 resolved events"
    )
    lines.append(
        "Fee: 0.15% a side + 0.1% sale tax, confirmed by Ben (the 'provisional' flag "
        "clears at the next returns rebuild)."
    )
    head = headline(day, label, symbol)
    return head, [head, *lines]


def write(conn, day: str) -> tuple[str, Path]:
    head, lines = brief(conn, day)
    out = paper.REPORTS / f"brief-{day}.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return head, out
