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
    # Market measures only: which market frame the function reads. The index
    # and breadth are separate frames, so a missing index day (a data defect)
    # cannot blank breadth, and a thin breadth day cannot blank the index.
    frame: str = "index"

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

# Sector measures read the SECTOR frame: one row per (trade_date, sector), not
# one per date. They run once per sector and are joined onto a symbol through
# its sector on each date (`compute`). A third registry because the join key
# differs, and a measure must not be able to land on the wrong frame silently.
SECTOR_REGISTRY: dict[str, Measure] = {}

# Values built on BORROWED (pre-snapshot, current) sector labels carry a
# companion column FLAG + name, True where flagged (decision 2026-09-23).
FLAG = "flag__"


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
    frame: str = "index",
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
            lookback=lookback, fn=fn, frame=frame,
        )
        return fn

    return wrap


def sector_measure(
    *,
    name: str,
    doc_ref: str,
    kind: str,
    needs: tuple[str, ...],
    lookback: Callable[[dict], int],
) -> Callable:
    """Register a sector measure (doc §5.4).

    The function receives ONE sector's rows of the sector frame, oldest first,
    one row per calendar session. Same contract otherwise: declared lookback,
    trailing windows, NaN meaning "no signal".
    """

    def wrap(fn: Callable[[pd.DataFrame, dict], pd.Series]) -> Callable:
        SECTOR_REGISTRY[name] = Measure(
            name=name, doc_ref=doc_ref, kind=kind, needs=needs,
            lookback=lookback, fn=fn, frame="sector",
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
    # Measures whose values can rest on borrowed (current) sector labels. Each
    # has a FLAG + name column in the output. The backtest must pass results
    # through `quarantine_flagged` before calling anything validated.
    flagged: tuple[str, ...] = ()

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
    market: pd.DataFrame | dict[str, pd.DataFrame], config: dict[str, dict]
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Run the enabled market measures once, one row per trade_date.

    `market` is either the index frame alone or a dict of frames by name
    ({"index": ..., "breadth": ...}). Each measure runs on the frame it
    declared, under that frame's own window guard. The frames are then joined
    on trade_date (outer), so a date one frame lacks is NaN for its measures
    only.
    """
    frames = market if isinstance(market, dict) else {"index": market}
    per_frame: dict[str, pd.DataFrame] = {}
    params: dict[str, dict] = {}
    for name, settings in config.items():
        if not settings.get("enabled", False):
            continue
        m = MARKET_REGISTRY[name]
        f = frames.get(m.frame)
        if f is None:
            raise ValueError(
                f"market measure '{name}' reads the '{m.frame}' frame, but no "
                f"{m.frame} frame was supplied"
            )
        out = per_frame.setdefault(
            m.frame, pd.DataFrame({"trade_date": f["trade_date"].to_numpy()},
                                  index=f.index)
        )
        p = {k: v for k, v in settings.items() if k != "enabled"}
        values = pd.Series(m.fn(f, p), index=f.index).astype("float64")
        out[name] = values.where(_market_window_ok(f, m.lookback(p)))
        params[name] = p
    if not per_frame:
        return pd.DataFrame(columns=["trade_date"]), params
    outs = list(per_frame.values())
    joined = outs[0]
    for other in outs[1:]:
        joined = joined.merge(other, on="trade_date", how="outer")
    if len(outs) > 1:
        joined = joined.sort_values("trade_date").reset_index(drop=True)
    return joined, params


def compute_sector(
    frame: pd.DataFrame, config: dict[str, dict]
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Run the enabled sector measures once per sector.

    Returns one row per (trade_date, sector) with each measure and its flag.
    A value is flagged if ANY row it read (its declared lookback plus today)
    had a borrowed label: a 20-session change that straddles the first
    snapshot still rests partly on current labels.
    """
    enabled = [
        (name, SECTOR_REGISTRY[name], {k: v for k, v in st.items() if k != "enabled"})
        for name, st in config.items()
        if st.get("enabled", False)
    ]
    parts = []
    for _, s in frame.groupby("sector", sort=True):
        s = s.sort_values("trade_date").reset_index(drop=True)
        part = s[["trade_date", "sector"]].copy()
        for name, m, p in enabled:
            lb = m.lookback(p)
            values = pd.Series(m.fn(s, p), index=s.index).astype("float64")
            part[name] = values.where(_market_window_ok(s, lb))
            part[FLAG + name] = (
                s["labels_current"].astype("float64")
                .rolling(lb + 1, min_periods=1).max().astype(bool)
            )
        parts.append(part)
    return pd.concat(parts, ignore_index=True), {n: p for n, _, p in enabled}


def quarantine_flagged(values: pd.DataFrame, fs) -> pd.DataFrame:
    """THE HARD GATE (decision 2026-09-23).

    Values resting on a BORROWED label are exploratory: a sector label from
    before the first dated snapshot, or an exchange from before the first dated
    membership (backtest.forward_returns.fillability). Anything reported as a
    validated result must come through here, which blanks every flagged value
    and drops the flag columns. A missing flag column raises; it never passes
    silently.

    `fs` is a FeatureSet (its `flagged` measures) or the names directly.
    """
    names = tuple(fs.flagged) if isinstance(fs, FeatureSet) else tuple(fs)
    out = values.copy()
    for name in names:
        out[name] = out[name].where(~out[FLAG + name].astype(bool))
    return out.drop(columns=[FLAG + n for n in names])


def compute(
    bars: pd.DataFrame,
    config: dict[str, dict] | None = None,
    market: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
    sector=None,
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

    sector_cfg = {k: v for k, v in cfg.items() if k in SECTOR_REGISTRY}
    enabled_sector = [k for k, v in sector_cfg.items() if v.get("enabled", False)]
    if enabled_sector and sector is None:
        raise ValueError(
            f"sector measures are enabled ({', '.join(sorted(enabled_sector))}) "
            "but no sector input was supplied"
        )

    # --- THE SECTOR JOIN ----------------------------------------------------
    #   symbol --(its label on each date)--> sector --(trade_date, sector)--> value
    # Done BEFORE the per-symbol measures so one of them (stock_vs_sector_20d)
    # can read the joined value as a column of `work`.
    work = bars
    flags: dict[str, np.ndarray] = {}
    sector_params: dict[str, dict] = {}
    if enabled_sector:
        from ..data import sectors

        per_sector, sector_params = compute_sector(sector.frame, sector_cfg)
        symbol = str(bars["symbol"].iloc[0]) if len(bars) else ""
        member = sectors.assign(symbol, bars["trade_date"], sector.labels)
        key = pd.DataFrame(
            {"trade_date": bars["trade_date"].to_numpy(),
             "sector": member["sector"].to_numpy()}
        )
        joined = key.merge(per_sector, on=["trade_date", "sector"], how="left")
        work = bars.copy()
        for name in sector_params:
            work[name] = joined[name].to_numpy()
            # Flagged if the sector value read a borrowed label, or THIS
            # symbol's own label is borrowed. No match (no sector) is not
            # known to be dated, so it is flagged too.
            flags[name] = (
                joined[FLAG + name].astype("boolean").fillna(True).to_numpy(bool)
                | member["labels_current"].to_numpy(bool)
            )
            out[name] = work[name].to_numpy()
            ran.append(name)
            params[name] = {**sector_params[name], "labels": sector.basis}

    for name, settings in cfg.items():
        if name in MARKET_REGISTRY or name in SECTOR_REGISTRY:
            continue
        if not settings.get("enabled", False):
            continue
        m = REGISTRY.get(name)
        if m is None:
            raise KeyError(f"measure '{name}' is enabled in config but not registered")

        p = {k: v for k, v in settings.items() if k != "enabled"}
        reads = [n for n in m.needs if n in SECTOR_REGISTRY]
        for n in reads:
            if n not in sector_params:
                raise ValueError(f"'{name}' reads '{n}', which is not enabled")
            if p.get("window_days") != sector_params[n].get("window_days"):
                raise ValueError(
                    f"'{name}' and '{n}' must use the same window_days, or the "
                    "stock and its sector are compared over different sessions"
                )
        values = m.fn(work, p)

        # Numeric so NaN is representable: a boolean measure that cannot be
        # evaluated must not collapse to False, which would read as "no signal
        # here" when the truth is "we cannot tell".
        values = pd.Series(values, index=bars.index).astype("float64")
        values = values.where(_window_ok(bars, m.lookback(p), m.reads_volume))

        out[name] = values
        ran.append(name)
        params[name] = p
        if reads:
            # Built on a flagged sector value, so flagged the same way.
            flags[name] = np.logical_or.reduce([flags[n] for n in reads])
            params[name] = {**p, "labels": sector.basis}

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

    for name, f in flags.items():
        out[FLAG + name] = f
    return out, FeatureSet(measures=tuple(ran), params=params, flagged=tuple(flags))
