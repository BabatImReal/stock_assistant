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

# Market-level measures live in their own registry because they are a different
# shape of function: they read ONE market frame aligned to the trading calendar,
# not one symbol's bars, and they are computed once per run rather than once per
# symbol. A single registry would need a discriminated union at every call site
# to say which kind it was holding.
MARKET_REGISTRY: dict[str, Measure] = {}


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


def market_measure(
    *,
    name: str,
    doc_ref: str,
    kind: str,
    needs: tuple[str, ...],
    lookback: Callable[[dict], int],
) -> Callable:
    """Register a market-level measure (doc §5.3).

    Same contract as `measure`, different input: the function receives the
    market frame rather than a symbol's bars. Everything else -- declared
    lookback, the trailing-window rule, NaN meaning "no signal" -- is shared,
    and so is `boolean_from` and the FeatureSet fingerprint.
    """

    def wrap(fn: Callable[[pd.DataFrame, dict], pd.Series]) -> Callable:
        MARKET_REGISTRY[name] = Measure(
            name=name, doc_ref=doc_ref, kind=kind, needs=needs,
            lookback=lookback, fn=fn,
        )
        return fn

    return wrap


def load_config(path: Path | None = None) -> dict[str, dict]:
    """The measure block only. Other top-level keys (e.g. which index the
    regime measures read) are configuration for the loaders, not measures."""
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


def boolean_from(condition: pd.Series, *inputs: pd.Series) -> pd.Series:
    """A boolean measure that stays NaN where its INPUTS are undefined.

    `(a >= x) & (b >= y)` silently yields False when b is NaN, because a
    comparison against NaN is False. That reads downstream as "the condition was
    evaluated and did not hold" when the truth is "we could not evaluate it" --
    the same collapse the float64 storage exists to prevent, sneaking back in
    one level lower.

    Example that motivated this: price-volume agreement compares the recent
    average volume with the earlier one. When the earlier window's mean is zero
    the ratio is undefined, and the measure was returning False on days it knew
    nothing about.
    """
    out = condition.astype("float64")
    undefined = pd.Series(False, index=condition.index)
    for series in inputs:
        undefined = undefined | series.isna()
    return out.where(~undefined)


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


def _market_window_ok(market: pd.DataFrame, lookback: int) -> pd.Series:
    """True where a market window of `lookback` prior sessions plus today is usable.

    Simpler than the per-symbol version and stricter about one thing: the index
    trades every session by definition, so a missing session in `index_bar` is
    a DATA DEFECT, not a suspension. It is fatal to any window containing it,
    and `data/checks.py` reports it separately so the defect is visible rather
    than merely routed around.
    """
    n = len(market)
    if n == 0:
        return pd.Series(dtype=bool)
    span = lookback + 1
    gap = market["gap_before"].fillna(0).to_numpy() > 0
    if span > 1:
        inside = (
            pd.Series(gap, index=market.index)
            .rolling(span - 1, min_periods=span - 1)
            .max()
        )
        inside = inside.fillna(1.0).astype(bool)
    else:
        inside = pd.Series(False, index=market.index)
    enough = pd.Series(np.arange(n) >= lookback, index=market.index)
    return (enough & ~inside).fillna(False)


def compute_market(
    market: pd.DataFrame, config: dict[str, dict]
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Run the enabled market measures once, indexed by trade_date."""
    out = pd.DataFrame(index=market.index)
    params: dict[str, dict] = {}
    for name, settings in config.items():
        if not settings.get("enabled", False):
            continue
        m = MARKET_REGISTRY[name]
        p = {k: v for k, v in settings.items() if k != "enabled"}
        values = pd.Series(m.fn(market, p), index=market.index).astype("float64")
        out[name] = values.where(_market_window_ok(market, m.lookback(p)))
        params[name] = p
    out["trade_date"] = market["trade_date"].to_numpy()
    return out, params


def compute(
    bars: pd.DataFrame,
    config: dict[str, dict] | None = None,
    market: pd.DataFrame | None = None,
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

    market_cfg = {k: v for k, v in cfg.items() if k in MARKET_REGISTRY}
    enabled_market = [k for k, v in market_cfg.items() if v.get("enabled", False)]
    if enabled_market and market is None:
        raise ValueError(
            f"market measures are enabled ({', '.join(sorted(enabled_market))}) "
            "but no market frame was supplied. Silently dropping them would "
            "leave a hole where the regime context should be."
        )

    for name, settings in cfg.items():
        if name in MARKET_REGISTRY:
            continue
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

    if enabled_market:
        market_values, market_params = compute_market(market, market_cfg)
        # Joined on trade_date, and NEVER forward-filled. A symbol day the
        # market frame does not cover comes back NaN: carrying yesterday's
        # regime forward would silently assert a market state we have no index
        # for, which is the quiet kind of wrong the other guards exist to stop.
        joined = bars[["trade_date"]].merge(
            market_values, on="trade_date", how="left"
        )
        for name in market_params:
            out[name] = joined[name].to_numpy()
        ran.extend(market_params)
        params.update(market_params)

    return out, FeatureSet(measures=tuple(ran), params=params)
