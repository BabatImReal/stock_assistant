"""Market breadth (doc §5.3): how many stocks rose today.

The VN-Index is cap-weighted, so a handful of large names can carry it up while
most of the market falls. Breadth counts stocks instead of weighting them, which
is why it is taken over ALL TRADEABLE stocks, not the liquid universe (Ben,
2026-09-23). Broad participation is exactly what the index misses.

Built in two layers:

1. `counts`: one row per session in its OWN frame, separate from the index
   frame. It holds advancers, decliners, unchanged, and the number counted.
   The rules for counting a stock on D, each tested in tests/test_breadth.py:
   - it is tradeable on D (data/universe.py: traded, not shifted, not excluded);
   - it was tradeable on the IMMEDIATELY PRECEDING session. A stock resuming
     after a suspension would otherwise compare against a close from weeks ago.
     That is the no-gap rule, with a lookback of one session;
   - direction comes from the ADJUSTED close. On an ex-dividend day the raw
     price drops by the dividend; a raw comparison would record a fake
     market-wide decline on exactly the days most companies pay.

2. The measures, which read that frame and blank THIN days: a session where far
   fewer stocks were counted than usual. The usual cause is a lost exchange file
   (2025-05-05: CafeF's HNX file had 1 stock), and a ratio taken over the
   exchanges that survived is not whole-market breadth. The guard parameters
   are measure parameters, so they are in the FeatureSet fingerprint.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import universe
from .base import market_measure

# Adjusted closes are stored to 6 decimals. With the same factor on both days,
# an unchanged raw close gives an identical adjusted close, so this only
# absorbs float noise. A real move is at least one tick, orders of magnitude
# larger.
UNCHANGED_EPS = 1e-9


# Enough prior sessions that the first research date has a full trailing
# baseline for the thin-day guard and a full 10-session window.
WARMUP = 40


def counts(rows: pd.DataFrame, calendar) -> pd.DataFrame:
    """Advancers / decliners / unchanged per session, from universe rows."""
    # The panel holds TRADEABLE rows only and sits on the full calendar, so
    # adj.shift(1) is the close of the immediately preceding session, and NaN
    # unless the stock traded then. That NaN is the no-gap rule: a stock back
    # from a suspension, or after a zero-volume placeholder, is not counted.
    # Never ffill here -- that would compare against a close from weeks ago.
    adj = universe.panel(rows, calendar, "adj_close")
    change = adj / adj.shift(1) - 1.0
    out = pd.DataFrame(
        {
            "advancers": (change > UNCHANGED_EPS).sum(axis=1),
            "decliners": (change < -UNCHANGED_EPS).sum(axis=1),
            "unchanged": (change.abs() <= UNCHANGED_EPS).sum(axis=1),
            "counted": change.notna().sum(axis=1),
        }
    )
    out.index.name = "trade_date"
    out = out.reset_index()
    # Aligned to the calendar by construction, so the frame itself never has a
    # missing session. The window guard reads this column.
    out["gap_before"] = 0
    return out


def load(conn, start: str = "2012-01-01", build: int | None = None) -> pd.DataFrame:
    """The breadth frame from `start`, plus warm-up sessions before it."""
    from .bars import current_build

    build_id = build if build is not None else current_build(conn)
    rows, calendar = universe.load_rows(conn, start, warmup=WARMUP, build=build_id)
    return counts(rows, calendar)


def _advance_share(b: pd.DataFrame, p: dict) -> pd.Series:
    """adv / (adv + dec), NaN on a thin day.

    Unchanged stays out of the denominator: thin names print unchanged all the
    time, and counting them would drag every day toward 0.5 without saying
    anything about direction.

    Thin = counted < min_count_share x the median count of the PREVIOUS
    count_median_sessions sessions. Trailing, so today's count is judged
    against what was known before today. No baseline means no judgement: NaN.
    """
    counted = b["counted"].astype("float64")
    k = int(p["count_median_sessions"])
    baseline = counted.shift(1).rolling(k, min_periods=k).median()
    ok = counted >= float(p["min_count_share"]) * baseline
    moved = (b["advancers"] + b["decliners"]).astype("float64")
    share = b["advancers"].astype("float64") / moved.replace(0.0, np.nan)
    return share.where(ok)


def _guard_lookback(p: dict) -> int:
    # The baseline reads count_median_sessions counts before today, and each
    # count reads the session before it: + 1.
    return int(p["count_median_sessions"]) + 1


@market_measure(
    name="breadth_advance_share",
    doc_ref="doc §5.3",
    kind="numeric",
    needs=("advancers", "decliners", "counted"),
    lookback=_guard_lookback,
    frame="breadth",
)
def breadth_advance_share(b: pd.DataFrame, p: dict) -> pd.Series:
    """Today's share of advancing stocks among those that moved."""
    return _advance_share(b, p)


@market_measure(
    name="breadth_advance_share_10d",
    doc_ref="doc §5.3",
    kind="numeric",
    needs=("advancers", "decliners", "counted"),
    lookback=lambda p: int(p["window_days"]) - 1 + _guard_lookback(p),
    frame="breadth",
)
def breadth_advance_share_10d(b: pd.DataFrame, p: dict) -> pd.Series:
    """The daily share averaged over window_days sessions. One thin day inside
    the window blanks it: an average with a hole is a different quantity."""
    w = int(p["window_days"])
    return _advance_share(b, p).rolling(w, min_periods=w).mean()
