"""The measure registry and the guarantees every measure gets for free.

Doc §4 treats volume as a first-class signal: define it as a rule, find every
occurrence, count what happened next. That only works if every rule is written
the same way and obeys the same constraints, so the constraints live here rather
than in each measure's head.

Three guarantees, enforced centrally because any one of them is easy to forget
in an individual rule and impossible to spot afterwards in a number:

1. NO LOOK-AHEAD. Every window is trailing. A measure sees rows up to and
   including the current one, never past it (doc §8.1).
2. NO WINDOW SPANS A GAP. CLAUDE.md forbids it. A 20-day relative-volume figure
   whose window straddles a two-month suspension is not slightly wrong, it is a
   different quantity. It comes back NaN.
3. MATCHED VOLUME ONLY, AND ONLY WHERE IT IS COMPARABLE. Backfilled spans have
   prices adjusted by vnstock but volume that could never be adjusted (no factor
   is derivable), so `volume_is_adjustable` is false there and every volume
   measure returns NaN across such a window.

NaN means "no signal here" -- excluded, unknowable, or out of data. It is never
a zero and never a neutral value. A disabled measure produces no column at all,
so a consumer can tell "switched off" from "switched on and unknown".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parents[3] / "config" / "rules" / "features.yaml"

# Columns a measure may ask for. Asking for matched_volume is what triggers the
# volume_is_adjustable guard, so the declaration is not documentation -- it is
# the mechanism.
VOLUME_COLUMNS = frozenset({"matched_volume", "traded_value"})


@dataclass(frozen=True)
class Measure:
    name: str
    doc_ref: str
    kind: str  # 'numeric' | 'boolean'
    needs: tuple[str, ...]
    lookback: Callable[[dict], int]
    fn: Callable[[pd.DataFrame, dict], pd.Series]

    @property
    def reads_volume(self) -> bool:
        return bool(VOLUME_COLUMNS & set(self.needs))


REGISTRY: dict[str, Measure] = {}


def measure(
    *,
    name: str,
    doc_ref: str,
    kind: str,
    needs: tuple[str, ...],
    lookback: Callable[[dict], int],
) -> Callable:
    """Register a measure.

    `lookback` is a function of the measure's own parameters and returns how
    many PRIOR rows the measure needs. It is declared rather than inferred
    because that is what lets the gap rule be enforced generically: the guard
    knows how far back to look without reading the measure's body.
    """

    def wrap(fn: Callable[[pd.DataFrame, dict], pd.Series]) -> Callable:
        REGISTRY[name] = Measure(
            name=name, doc_ref=doc_ref, kind=kind, needs=needs,
            lookback=lookback, fn=fn,
        )
        return fn

    return wrap


def load_config(path: Path | None = None) -> dict[str, dict]:
    return yaml.safe_load((path or CONFIG).read_text())["measures"]


@dataclass(frozen=True)
class FeatureSet:
    """What was computed, and with exactly which parameters.

    Recorded alongside any output so a value can be traced to the measure
    version that produced it -- the same discipline as research_result.build_id.
    """

    measures: tuple[str, ...]
    params: dict[str, dict] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        import hashlib
        import json

        blob = json.dumps(
            {m: self.params.get(m, {}) for m in sorted(self.measures)},
            sort_keys=True, default=str,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _window_ok(bars: pd.DataFrame, lookback: int, needs_volume: bool) -> pd.Series:
    """True where a window of `lookback` prior rows plus today is usable.

    Three ways a window fails, and the reason each is fatal rather than
    tolerable:

      - it straddles a trading gap: the rows are not consecutive sessions, so a
        "20-day average" covers something other than 20 days;
      - it touches an excluded window: a corporate action we could not adjust
        for sits inside it, so the prices are not comparable across it;
      - it touches a span where volume is not adjustable: share counts differ
        across it, so volumes are not comparable (blocker G1).
    """
    n = len(bars)
    if n == 0:
        return pd.Series(dtype=bool)

    span = lookback + 1  # the window includes today

    # A gap recorded on row j sits between j-1 and j, so it only breaks a window
    # that contains BOTH -- i.e. gaps on the first row of the window are before
    # it and harmless.
    gap = bars["gap_before"].fillna(0).to_numpy() > 0
    gap_inside = (
        pd.Series(gap, index=bars.index)
        .rolling(span - 1, min_periods=span - 1)
        .max()
        .shift(0)
        if span > 1
        else pd.Series(False, index=bars.index)
    )
    gap_inside = gap_inside.fillna(1.0).astype(bool) if span > 1 else gap_inside

    bad = bars["excluded"].fillna(False).to_numpy().astype(bool)
    if needs_volume:
        usable = bars["volume_is_adjustable"].fillna(False).to_numpy().astype(bool)
        bad = bad | ~usable
    bad_inside = (
        pd.Series(bad, index=bars.index)
        .rolling(span, min_periods=span)
        .max()
        .astype("float")
    )

    enough_history = pd.Series(np.arange(n) >= lookback, index=bars.index)
    ok = enough_history & (~gap_inside) & (bad_inside.fillna(1.0) == 0)
    return ok.fillna(False)


def compute(
    bars: pd.DataFrame,
    config: dict[str, dict] | None = None,
) -> tuple[pd.DataFrame, FeatureSet]:
    """Run every ENABLED measure over one symbol's bars.

    Returns a frame indexed like `bars`, one column per enabled measure, plus
    the FeatureSet describing what ran. A disabled measure produces NO COLUMN,
    which is how a consumer distinguishes "switched off" from "switched on and
    unknown here" (NaN).
    """
    cfg = config if config is not None else load_config()
    out = pd.DataFrame(index=bars.index)
    ran: list[str] = []
    params: dict[str, dict] = {}

    for name, settings in cfg.items():
        if not settings.get("enabled", False):
            continue
        m = REGISTRY.get(name)
        if m is None:
            raise KeyError(f"measure '{name}' is enabled in config but not registered")

        p = {k: v for k, v in settings.items() if k != "enabled"}
        values = m.fn(bars, p)

        # Numeric so NaN is representable: a boolean measure that cannot be
        # evaluated must not collapse to False, which would read as "no signal
        # here" when the truth is "we cannot tell".
        values = pd.Series(values, index=bars.index).astype("float64")
        values = values.where(_window_ok(bars, m.lookback(p), m.reads_volume))

        out[name] = values
        ran.append(name)
        params[name] = p

    return out, FeatureSet(measures=tuple(ran), params=params)
