"""What following a signal would have FELT like (doc §8.3): the numbers beside
the hit rate that decide whether Ben could live with it.

Win rate alone is not a metric. 45% hits can make money when the wins are
big; 65% can lose when the losses are bigger. And an average of +0.8% a
trade says nothing about the bad stretch on the way. So, for one list of
trades (net returns, in the order they were entered):

  per trade   the average win, the average loss, their ratio (payoff), the
              best and the worst single trade;
  drawdown    the deepest fall of the running total from its previous peak;
  streak      the longest run of trades in a row that lost money.

Two ways of following a signal, both with a FIXED STAKE per signal day (not
compounding, so every total and drawdown is in STAKES, not a share of an
account: -0.25 is a quarter of one stake, 25M VND at 100M a stake):

  basket      the stake is split equally over EVERY stock that fired that day.
              Smooth: the day's result is an average.
  one pick    the stake goes on ONE of that day's stocks, drawn at random,
              repeated over many seeded paths. This is closer to what the
              daily scan will do (one proposal a day), and much bumpier: the
              drawdown is reported as the median path and a bad path (the
              95th percentile), plus how often a stretch of `window`
              consecutive picks ended below zero.

Assumptions, stated because they flatter or hurt:
  - trades are ordered by their SIGNAL day; positions can overlap, so the
    cash needed is `max_open` stakes, measured from the real exit dates (a
    signal that fires once a month needs one stake; a daily one needs
    several);
  - no slippage beyond the costs already in NET, and the fills the gate
    allowed (no buy at the ceiling, a floor-locked exit waits).

INFORMATION ONLY: nothing here changes a verdict.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(pnl) -> float:
    """The deepest fall of the running total below its previous peak, as a
    number <= 0 in units of one stake. The start (0) counts as a peak, so a
    first trade that loses is a drawdown too."""
    total = np.concatenate([[0.0], np.cumsum(np.asarray(pnl, float))])
    return float((total - np.maximum.accumulate(total)).min())


def worst_streak(pnl) -> int:
    """The longest run of consecutive losing trades. A loss is net <= 0,
    because a hit is net > 0: a trade that only paid its costs lost."""
    best = run = 0
    for x in np.asarray(pnl, float):
        run = run + 1 if x <= 0 else 0
        best = max(best, run)
    return best


def per_trade(net) -> dict:
    """Average win / average loss / payoff / best / worst, over the trades."""
    net = pd.Series(net, dtype="float64").dropna()
    win, loss = net[net > 0], net[net <= 0]
    avg_win = float(win.mean()) if len(win) else np.nan
    avg_loss = float(loss.mean()) if len(loss) else np.nan
    return {
        "trades": int(len(net)),
        "avg": float(net.mean()) if len(net) else np.nan,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        # How many losses one average win pays for. Below 1, the hit rate
        # must stay above 50% for the signal to make money.
        "payoff": avg_win / -avg_loss if avg_loss < 0 else np.nan,
        "best": float(net.max()) if len(net) else np.nan,
        "worst": float(net.min()) if len(net) else np.nan,
    }


def basket(dates, net) -> pd.Series:
    """One result per signal day: the mean net over that day's trades."""
    return (
        pd.Series(np.asarray(net, float), index=pd.to_datetime(pd.Series(dates)))
        .groupby(level=0)
        .mean()
        .sort_index()
    )


def one_pick_paths(dates, net, paths: int, seed: int) -> np.ndarray:
    """(paths x signal days): on each signal day, ONE of that day's trades,
    drawn uniformly at random, independently per path and day."""
    frame = pd.DataFrame(
        {"d": pd.to_datetime(pd.Series(dates)).to_numpy(), "x": np.asarray(net, float)}
    ).sort_values("d", kind="stable")
    day, start, size = np.unique(frame["d"], return_index=True, return_counts=True)
    rng = np.random.default_rng(seed)
    pick = start + np.floor(rng.random((paths, len(day))) * size).astype(int)
    return frame["x"].to_numpy()[pick]


def max_open(dates, exits) -> int:
    """The most stakes tied up at once. A signal day's stake is bought at the
    next open and is busy until the LAST of that day's exits (the basket's
    slowest piece; the one pick's stock can be any of them, so this is the
    safe side). When day d's stake goes in, every earlier day whose last exit
    is after d is still open. The T+2 wait for the sale money is left out: it
    would add about two sessions to each hold."""
    last = (
        pd.Series(
            pd.to_datetime(pd.Series(exits)).to_numpy(),
            index=pd.to_datetime(pd.Series(dates)).to_numpy(),
        )
        .groupby(level=0)
        .max()
        .sort_index()
    )
    days, ends = last.index.to_numpy(), last.to_numpy()
    return int(max(((days <= d) & (ends > d)).sum() for d in days)) if len(days) else 0


def losing_windows(pnl, window: int) -> float:
    """The share of stretches of `window` consecutive trades whose total is
    <= 0 (every start point). NaN when there are fewer trades than that."""
    pnl = np.asarray(pnl, float)
    if len(pnl) < window:
        return np.nan
    total = np.concatenate([[0.0], np.cumsum(pnl)])
    return float((total[window:] - total[:-window] <= 0).mean())


def describe(
    dates, net, exits, paths: int = 1000, seed: int = 20260924, window: int = 60
) -> dict:
    """Every number above for one list of trades (signal dates, net, and the
    date each trade was sold)."""
    day = basket(dates, net)
    picks = one_pick_paths(dates, net, paths, seed)
    dd = np.array([max_drawdown(p) for p in picks])
    streak = np.array([worst_streak(p) for p in picks])
    lose = np.array([losing_windows(p, window) for p in picks])
    return {
        **per_trade(net),
        "signal_days": int(len(day)),
        # The fair comparison with the per-trade average: one stake per signal
        # day, averaged over the days. They differ when many stocks fire on
        # the same few days.
        "per_day": float(day.mean()) if len(day) else np.nan,
        "max_open": max_open(dates, exits),
        "basket_total": float(day.sum()),
        "basket_drawdown": max_drawdown(day),
        "basket_streak": worst_streak(day),
        "pick_total_median": float(np.median(picks.sum(axis=1))),
        # A drawdown is negative: the bad path is the 5th percentile of it.
        "pick_drawdown_median": float(np.median(dd)),
        "pick_drawdown_bad": float(np.percentile(dd, 5)),
        "pick_streak_median": float(np.median(streak)),
        "pick_streak_bad": float(np.percentile(streak, 95)),
        "window": window,
        "pick_losing_windows": float(np.mean(lose)) if len(day) >= window else np.nan,
    }
