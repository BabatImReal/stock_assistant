"""Tranche 4 of the pattern catalogue (doc §3.4): short consolidations, the
"shape forming over 3-5 days" that the broker friend probably watches.

Each is dated on its LAST day and reads nothing after it. The declared lookback
covers every session read, so a window spanning a trading gap or an excluded
row is blank (base.py).

  tight_range     mean range of the last lookback_days sessions < range_vs_
                  baseline_max x the mean range of the baseline_days sessions
                  BEFORE them (doc: "average range of last N days < X% of the
                  20-day average range"; the window is kept out of its own
                  baseline). Lookback = lookback_days + baseline_days - 1.
  inside_day_run  each of the last min_days days sits inside the day before:
                  high not above, low not below, and a strictly SMALLER range,
                  so an identical flat repeat does not count. Lookback = min_days.
  higher_lows     over lookback_days days each low is above the one before,
                  while the highs stay flat (max - min high <= highs_flat_
                  tolerance x today's close). Lookback = lookback_days - 1.
  breakout        today's close above the highest high of the previous
                  lookback_days sessions. PRICE-ONLY (Ben, P6): "breakout on
                  volume" is a fingerprint combination with rvol, not baked in.
  flag / pause    DEFERRED (P7).

TICK NOISE, the same self-meaningful rule as tranches 1-3:
  - tight_range needs the BASELINE mean RAW range >= min_baseline_ticks ticks.
    Against a normal range of 1-2 ticks, "tight" is tick noise. (The baseline
    uses raw ranges against today's tick: a coarse floor. A corporate action
    inside the window only shifts which side of the floor a borderline case
    falls.)
  - inside_day_run needs the "mother" bar (the first of the run) to have a RAW
    range >= min_mother_range_ticks: being inside a 1-tick bar means nothing.
  - higher_lows and breakout need no floor: every step is a whole tick
    anyway, and a one-tick breakout is still a breakout.
Ticks come from data/checks.py `floor_tick` (the dated exchange's own tick, the
largest where undated). Cross-day price comparisons use tranche 2's REL_TOL
(adjustment rounding).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.checks import floor_tick
from ..features.base import boolean_from, measure
from .two_candle import EPS, _ge, _gt, _le

NEEDS = (
    "open",
    "high",
    "low",
    "close",
    "raw_high",
    "raw_low",
    "raw_close",
    "exchange",
    "exchange_unknown",
)


def _f(bars: pd.DataFrame, col: str) -> pd.Series:
    return bars[col].astype("float64")


def _tick(bars: pd.DataFrame) -> np.ndarray:
    return floor_tick(
        bars["trade_date"],
        bars["raw_close"],
        bars["exchange"],
        bars["exchange_unknown"],
    )


@measure(
    name="tight_range",
    doc_ref="doc §3.4",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: int(p["lookback_days"]) + int(p["baseline_days"]) - 1,
)
def tight_range(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Several days whose range is much smaller than the stock's usual range:
    energy building."""
    n, b = int(p["lookback_days"]), int(p["baseline_days"])
    rng = _f(bars, "high") - _f(bars, "low")
    recent = rng.rolling(n, min_periods=n).mean()
    baseline = rng.shift(n).rolling(b, min_periods=b).mean()
    raw_rng = _f(bars, "raw_high") - _f(bars, "raw_low")
    raw_base = raw_rng.shift(n).rolling(b, min_periods=b).mean()
    cond = (recent < float(p["range_vs_baseline_max"]) * baseline - EPS) & (
        raw_base >= float(p["min_baseline_ticks"]) * _tick(bars) - EPS
    )
    return boolean_from(cond, recent, baseline)


@measure(
    name="inside_day_run",
    doc_ref="doc §3.4",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: int(p["min_days"]),
)
def inside_day_run(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Each of the last min_days days sits inside the day before."""
    k = int(p["min_days"])
    h, lo = _f(bars, "high"), _f(bars, "low")
    rng = h - lo
    cond = pd.Series(True, index=bars.index)
    for j in range(k):  # day t-j inside day t-j-1
        cond &= _le(h.shift(j), h.shift(j + 1))
        cond &= _ge(lo.shift(j), lo.shift(j + 1))
        cond &= rng.shift(j) < rng.shift(j + 1) - EPS
    raw_rng = _f(bars, "raw_high") - _f(bars, "raw_low")
    mother_ok = raw_rng >= float(p["min_mother_range_ticks"]) * _tick(bars) - EPS
    cond &= mother_ok.shift(k, fill_value=False)
    return boolean_from(cond, h.shift(k))


@measure(
    name="higher_lows",
    doc_ref="doc §3.4",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: int(p["lookback_days"]) - 1,
)
def higher_lows(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Each low above the one before while the highs stay flat: buyers
    stepping in earlier each day."""
    n = int(p["lookback_days"])
    h, lo, c = _f(bars, "high"), _f(bars, "low"), _f(bars, "close")
    cond = pd.Series(True, index=bars.index)
    for j in range(n - 1):  # low t-j above low t-j-1
        cond &= _gt(lo.shift(j), lo.shift(j + 1))
    spread = h.rolling(n, min_periods=n).max() - h.rolling(n, min_periods=n).min()
    cond &= spread <= float(p["highs_flat_tolerance"]) * c + EPS
    return boolean_from(cond, lo.shift(n - 1))


@measure(
    name="breakout",
    doc_ref="doc §3.4",
    kind="boolean",
    needs=NEEDS,
    lookback=lambda p: int(p["lookback_days"]),
)
def breakout(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Today's close above the highest high of the previous lookback_days
    sessions. Price only (P6)."""
    n = int(p["lookback_days"])
    prior_high = _f(bars, "high").shift(1).rolling(n, min_periods=n).max()
    cond = _gt(_f(bars, "close"), prior_high)
    return boolean_from(cond, prior_high)
