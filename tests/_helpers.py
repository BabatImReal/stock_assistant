"""Shared synthetic-symbol builder for the feature tests.

Lives in its own module rather than in one test file so both the volume and
trend suites use the SAME frame. If they drifted apart, a guard could pass in
one suite and be silently untested in the other.
"""

import re

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
            "raw_open": closes, "raw_high": closes,
            "raw_low": closes, "raw_close": closes,
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




def fails_with(exc, match, fn, *args, **kwargs):
    """Assert `fn` fails with the guard's OWN error: type `exc`, message
    matching `match`.

    Not `pytest.raises(exc)`: that lets any OTHER exception escape as a crash.
    With the guard removed, the code usually breaks a line later on an obscure
    AttributeError, and a crash is not a catch. Here every outcome is judged
    by an assert: no error, the wrong type, or the wrong message all fail it.
    """
    try:
        fn(*args, **kwargs)
        err = None
    except Exception as e:  # noqa: BLE001 - judging the type is the point
        err = e
    # Asserted OUTSIDE the except block, so the traceback is this assert, not
    # a chained "during handling of ..." showing the other error as a crash.
    assert err is not None, f"did not raise {exc.__name__}"
    assert type(err) is exc and re.search(match, str(err)), (
        f"wrong failure: {type(err).__name__}: {err}"
    )
