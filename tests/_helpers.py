"""Shared synthetic-symbol builder for the feature tests.

Lives in its own module rather than in one test file so both the volume and
trend suites use the SAME frame. If they drifted apart, a guard could pass in
one suite and be silently untested in the other.
"""

import numpy as np
import pandas as pd


def frame(n=60, volume=1000.0, close=10.0, gaps=None, excluded=None,
          adjustable=True):
    """A clean synthetic symbol, with defects injected where asked."""
    dates = pd.bdate_range("2020-01-01", periods=n).date
    closes = np.full(n, float(close)) if np.isscalar(close) else np.asarray(
        close, dtype=float
    )
    vols = np.full(n, float(volume)) if np.isscalar(volume) else np.asarray(
        volume, dtype=float
    )
    df = pd.DataFrame(
        {
            "symbol": "TST",
            "trade_date": dates,
            "open": closes, "high": closes, "low": closes, "close": closes,
            "matched_volume": vols,
            "volume_is_adjustable": True,
            "gap_before": 0,
            "excluded": False,
            # Raw = adjusted unless a test needs them apart (candle tick floor).
            "raw_high": closes, "raw_low": closes, "raw_close": closes,
            "exchange": "HOSE", "exchange_unknown": False,
        }
    )
    for i in gaps or []:
        df.loc[i, "gap_before"] = 10
    for i in excluded or []:
        df.loc[i, "excluded"] = True
    if adjustable is not True:
        df.loc[adjustable, "volume_is_adjustable"] = False
    return df


