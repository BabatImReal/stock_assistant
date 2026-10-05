"""Daily cross-sectional ranking (Amendment 1, section 12 of the knowledge document).

Two features with documented Vietnamese evidence and signs fixed from that evidence
(Huang, Liu & Shu 2023, Pacific-Basin Finance Journal 82:102176), never from our data:

  high52   adjusted close / highest adjusted high of the past 250 sessions
           (higher is better)
  abn_vol  mean matched volume, past 20 sessions / past 250 sessions
           (higher is better)

Each is ranked across that day's liquid stocks and the two ranks are averaged with
equal weights. No fitted weights, no training. Pure functions here; the Phase 1
development run (scripts/phase1_cross_section.py) wires them to the database.

Package root on purpose: outside the hashed features/ patterns/ data/ trees.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

LONG = 250  # sessions: the 52-week window
SHORT = 20  # sessions: the "1-month" window
MIN_RANKED = 50  # a day with fewer ranked stocks produces no ranking
# Correction 1 (docs section 12.4a). A skipped session that hit most of the market at
# once (the 2018-01-23/24 HOSE halt, a 6-session data hole in 2023-01) is not a
# symbol-specific suspension, and under a strict no-gap rule it blanked every stock
# for a year. A window stays valid with at most this many skipped sessions in total
# (about 5% of 250) and no single skip longer than MAX_SINGLE_GAP.
MAX_SKIPPED = 12
MAX_SINGLE_GAP = 10


def features(bars: pd.DataFrame) -> pd.DataFrame:
    """high52 and abn_vol for ONE symbol, oldest first (pure).

    A value exists only where the 250-session window is usable: at most MAX_SKIPPED
    skipped sessions with none longer than MAX_SINGLE_GAP, no excluded row, a matched
    volume on every day and, for abn_vol, volume that can be inverse-adjusted.
    Anything else is NaN, never zero, so a bad window cannot rank.
    """
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    vol = bars["matched_volume"].astype(float)
    skipped = bars["gap_before"].fillna(0).clip(lower=0)
    exc = bars["excluded"].fillna(False).astype(int)
    clean = (
        (skipped.rolling(LONG).sum() <= MAX_SKIPPED)
        & (skipped.rolling(LONG).max() <= MAX_SINGLE_GAP)
        & (exc.rolling(LONG).sum() == 0)
    )
    # The project's rule (decision 2026-09-22): volume on a span that cannot be
    # inverse-adjusted for splits is unknown, never a signal. It blanks abn_vol only.
    adj = bars["volume_is_adjustable"].fillna(True).astype(bool)
    vol_adjustable = (~adj).astype(int).rolling(LONG).sum() == 0
    full_vol = vol.rolling(LONG, min_periods=LONG).count() == LONG
    top = high.rolling(LONG, min_periods=LONG).max()
    long_mean = vol.rolling(LONG, min_periods=LONG).mean()
    short_mean = vol.rolling(SHORT, min_periods=SHORT).mean()
    ok = clean & full_vol
    ok_vol = ok & vol_adjustable
    out = pd.DataFrame(
        {
            "symbol": bars["symbol"].to_numpy(),
            "trade_date": bars["trade_date"].to_numpy(),
            "high52": (close / top).where(ok),
            "abn_vol": (short_mean / long_mean).where(ok_vol & (long_mean > 0)),
        }
    )
    return out


def score(day: pd.DataFrame) -> pd.Series:
    """Equal-weight average of the two percentile ranks, higher = better (pure)."""
    r = day[["high52", "abn_vol"]].rank(pct=True, method="average")
    return r.mean(axis=1, skipna=False)


def daily_selection(
    panel: pd.DataFrame, frac: float = 0.10, min_ranked: int = MIN_RANKED
) -> pd.DataFrame:
    """Per day: which stocks are in the top decile / top 3 / top 1 (pure).

    panel needs: symbol, trade_date, high52, abn_vol (liquid, valid rows only).
    Returns the panel plus score, rank (1 = best) and in_top columns. Ties are broken
    by symbol, which is arbitrary but fixed and not a function of any outcome.
    """
    rows = []
    for _, g in panel.groupby("trade_date", sort=True):
        g = g.dropna(subset=["high52", "abn_vol"]).copy()
        if len(g) < min_ranked:
            continue
        g["score"] = score(g)
        g = g.sort_values(["score", "symbol"], ascending=[False, True])
        g["rank"] = np.arange(1, len(g) + 1)
        g["n_ranked"] = len(g)
        g["in_top"] = g["rank"] <= max(1, math.ceil(frac * len(g)))
        rows.append(g)
    return pd.concat(rows, ignore_index=True) if rows else panel.iloc[0:0]


def newey_west_mean(x: pd.Series, lags: int = 5) -> dict:
    """Mean of x with a Newey-West (Bartlett) standard error (pure).

    Overlapping 5-session holds make consecutive daily excess returns correlated, so
    the plain SE would be too small. With lags=0 this is the ordinary SE of a mean.
    """
    v = x.dropna().to_numpy(dtype=float)
    n = len(v)
    if n < 2:
        return {"n": n, "mean": float("nan"), "se": float("nan"), "t": float("nan")}
    m = v.mean()
    e = v - m
    s = float(e @ e) / n
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1 - lag / (lags + 1)
        s += 2 * w * float(e[lag:] @ e[:-lag]) / n
    se = math.sqrt(max(s, 0.0) / n)
    return {"n": n, "mean": float(m), "se": se, "t": m / se if se > 0 else float("nan")}


def excess_series(sel: pd.DataFrame, net: str = "net_5") -> pd.DataFrame:
    """One row per day: top-decile / top-3 / top-1 mean net minus the universe mean.

    sel is daily_selection output joined to the resolved, unflagged outcome `net`.
    Only stocks with a resolved outcome enter a mean; the RANKING did not use it.
    """
    out = []
    for _, g in sel.dropna(subset=[net]).groupby("trade_date", sort=True):
        base = g[net].mean()
        top = g[g["in_top"]]
        t3 = g[g["rank"] <= 3]
        t1 = g[g["rank"] == 1]
        if top.empty:
            continue
        out.append(
            {
                "trade_date": g["trade_date"].iloc[0],
                "n_universe": len(g),
                "n_top": len(top),
                "excess_top": top[net].mean() - base,
                "excess_top3": t3[net].mean() - base if len(t3) else np.nan,
                "excess_top1": t1[net].mean() - base if len(t1) else np.nan,
                "hit_gap": (top[net] > 0).mean() - (g[net] > 0).mean(),
            }
        )
    return pd.DataFrame(out)
