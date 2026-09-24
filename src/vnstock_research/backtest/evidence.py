"""The analysis engine's gate and base rates (doc §2 layer 3, §7.1, §8; E2).

THE GATE, `validated(fp, returns, universe, before)`, is the ONE place where
features (the fingerprint, known at t's close) meet outcomes (the returns,
known later). Everything that reaches a validated number has passed it:

  - the fingerprint and the returns come from the SAME adjustment build;
  - flagged feature values are blanked (features.base.quarantine_flagged,
    the sector hard gate);
  - an outcome whose fillability is flagged (the exchange is not dated, or is
    UPCoM, ruling A9) is blanked: the entry decision itself may be wrong;
  - an outcome outside the point-in-time liquid universe ON t is blanked;
  - with `before` = T: rows from T on do not exist yet, and an outcome whose
    `known_on` is not strictly before T is blanked. A past day is evidence for
    T only once its outcome window has closed.
  - G20 factor defects are applied upstream (features/bars.py): a window
    across one was already blanked, in the features and in the returns.

A blanked outcome keeps its REASON, so every number can say how many rows it
lost and why. Blank is never 0: a blank row is in no numerator and no
denominator.

THE NUMBERS, `evidence(v, conditions, k, symbol)`, for an exact combination
(`patterns.fingerprint.query`) at horizon k:
  hit        net return > 0: after both fees and the sale tax (the broker fee
             is PROVISIONAL, and every result says so);
  base rate  the hit share over ALL eligible stock-days at the same level, in
             the same period, at the same horizon, through the same gate and
             window rules, where the condition could be judged. Filtered
             identically, so the edge is the pattern's and nothing else's;
  fallback   this stock -> its liquidity tier -> the whole market: the first
             level with >= min_occurrences DE-CLUSTERED occurrences (a repeat
             within k sessions of a counted one shares its outcome window, so
             it is not new evidence). The sector level is shown beside,
             labelled EXPLORATORY: it groups on TODAY's labels.

Not here (E3): the hypothesis log, FDR, and the discover/validate protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yaml

from ..features.base import FLAG, quarantine_flagged
from ..patterns.fingerprint import query
from ..store import KEYS
from .forward_returns import OUTCOME, PATTERNS

# Why the gate blanked an outcome, beyond the returns' own REASONS.
GATE_REASONS = ("not_liquid", "fill_flagged", "not_yet_known")
LEVELS = ("stock", "tier", "market")


def min_occurrences() -> int:
    cfg = yaml.safe_load(PATTERNS.read_text())["reliability"]
    return int(cfg["min_occurrences_per_stock"])


_KEY = object()


@dataclass(frozen=True)
class Validated:
    """Features and outcomes that have passed the gate. Statistics take THIS
    type, and only `validated()` can make one."""

    values: pd.DataFrame
    manifest: dict
    _key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self._key is not _KEY:
            raise TypeError(
                "a Validated table comes only from validated(), the one path "
                "that applies the gate"
            )


def validated(fp, rt, universe: pd.DataFrame, before=None) -> Validated:
    """THE GATE. fp: a loaded Fingerprint; rt: loaded Returns; universe:
    (trade_date, symbol, tier) of the stock-days liquid on that date
    (data.universe.tiers); before: the query day T, or None for all history.
    """
    a, b = fp.manifest["build_id"], rt.manifest["build_id"]
    if a != b:
        raise ValueError(
            f"cannot join a fingerprint of build {a} to returns of build {b}"
        )
    flagged = [n for n in fp.manifest["flagged"] if n in fp.values.columns]
    values = quarantine_flagged(fp.values, flagged).merge(
        rt.values, on=KEYS, how="inner", validate="one_to_one"
    )
    values = values.merge(universe[[*KEYS, "tier"]], on=KEYS, how="left")
    if before is not None:
        values = values[pd.to_datetime(values["trade_date"]) < pd.Timestamp(before)]
    liquid = values["tier"].notna()
    ks = rt.manifest["horizons"]
    for k in ks:
        reason = values[f"reason_{k}"].astype(object)
        open_ = reason.isna()
        reason = reason.mask(open_ & ~liquid, "not_liquid")
        reason = reason.mask(
            reason.isna() & values[f"{FLAG}fill_{k}"].astype(bool), "fill_flagged"
        )
        if before is not None:
            known = pd.to_datetime(values[f"known_on_{k}"])
            reason = reason.mask(
                reason.isna() & ~(known < pd.Timestamp(before)), "not_yet_known"
            )
        values[f"reason_{k}"] = reason
        for name in OUTCOME:
            values[f"{name}_{k}"] = values[f"{name}_{k}"].where(reason.isna())
    values = values.drop(columns=[f"{FLAG}fill_{k}" for k in ks])
    manifest = {
        "build_id": a,
        "horizons": list(ks),
        "before": None if before is None else str(before),
        "net_provisional": rt.manifest["net_provisional"],
        "fingerprint": {x: fp.manifest[x] for x in ("featureset", "code")},
        "returns": {x: rt.manifest[x] for x in ("rules", "code")},
    }
    return Validated(values.reset_index(drop=True), manifest, _KEY)


# --- the numbers ----------------------------------------------------------


@dataclass(frozen=True)
class Level:
    """One level's numbers. Every figure travels with where it came from."""

    level: str  # stock | tier | market | sector
    group: str  # the symbol, the tier, 'all', or the sector code
    n_raw: int
    n_declustered: int
    hit_rate: float  # share of occurrences with net > 0
    base_rate: float  # the same share over every eligible stock-day
    base_n: int
    edge: float  # hit_rate - base_rate
    gross_mean: float
    expectancy: float  # mean NET return per occurrence
    avg_win: float
    avg_loss: float
    mfe_mean: float
    mae_mean: float
    mae_worst: float
    drops: dict  # reason -> rows of this level's population in the period
    exploratory: bool = False  # the sector level: grouped on TODAY's labels


@dataclass(frozen=True)
class Evidence:
    symbol: str
    conditions: dict
    k: int
    period: tuple  # (start, end) of trade dates used; `before` is in manifest
    chosen: Level  # the first level with enough de-clustered occurrences
    levels: list  # every level tried, in fallback order
    sufficient: bool  # False if even the market level is below the floor
    min_occurrences: int
    net_provisional: bool
    before: str | None
    sector: Level | None = None  # EXPLORATORY, beside, never in the fallback


def decluster(dates: pd.Series, symbols: pd.Series, sessions: dict, k: int) -> int:
    """Occurrences that do not share an outcome window: per symbol, one within
    k sessions of the last COUNTED one is not new."""
    count = 0
    frame = pd.DataFrame({"s": dates.map(sessions), "sym": symbols.to_numpy()})
    for _, s in frame.sort_values("s").groupby("sym")["s"]:
        last = None
        for x in s:
            if last is None or x - last > k:
                count, last = count + 1, x
    return count


def _level(v, mask, hit, k, sessions, level, group, exploratory=False) -> Level:
    net = v[f"net_{k}"]
    eligible = mask & hit.notna() & net.notna()
    occ = eligible & (hit == 1.0)
    o = v[occ]
    wins = o[f"net_{k}"] > 0
    base_hit = (net[eligible] > 0).mean() if eligible.any() else np.nan
    rate = wins.mean() if len(o) else np.nan
    reasons = v.loc[mask, f"reason_{k}"].dropna().value_counts().to_dict()
    reasons["condition_unknown"] = int((mask & hit.isna() & net.notna()).sum())
    return Level(
        level=level,
        group=str(group),
        n_raw=int(occ.sum()),
        n_declustered=decluster(o["trade_date"], o["symbol"], sessions, k),
        hit_rate=float(rate),
        base_rate=float(base_hit),
        base_n=int(eligible.sum()),
        edge=float(rate - base_hit),
        gross_mean=float(o[f"ret_{k}"].mean()),
        expectancy=float(o[f"net_{k}"].mean()),
        avg_win=float(o.loc[wins, f"net_{k}"].mean()),
        avg_loss=float(o.loc[~wins, f"net_{k}"].mean()),
        mfe_mean=float(o[f"mfe_{k}"].mean()),
        mae_mean=float(o[f"mae_{k}"].mean()),
        mae_worst=float(o[f"mae_{k}"].min()),
        drops={key: int(n) for key, n in reasons.items()},
        exploratory=exploratory,
    )


def evidence(
    v: Validated,
    conditions: dict,
    k: int,
    symbol: str,
    start=None,
    end=None,
    sectors: dict | None = None,
) -> Evidence:
    """The numbers for `conditions` on `symbol` at horizon k, falling back
    stock -> tier -> market. `sectors` (symbol -> sector, TODAY's labels) adds
    the exploratory sector level beside."""
    if not isinstance(v, Validated):
        raise TypeError("evidence() takes only a Validated table (validated())")
    values = v.values
    dates = pd.to_datetime(values["trade_date"])
    in_period = pd.Series(True, index=values.index)
    if start is not None:
        in_period &= dates >= pd.Timestamp(start)
    if end is not None:
        in_period &= dates <= pd.Timestamp(end)
    values = values[in_period].reset_index(drop=True)
    hit = _hit(values, conditions)
    sessions = {d: i for i, d in enumerate(sorted(values["trade_date"].unique()))}
    own = values["symbol"] == symbol
    # The stock's tier as of its latest liquid day in the period: known then.
    tiers = values.loc[own & values["tier"].notna(), "tier"]
    masks = [("stock", symbol, own)]
    if len(tiers):
        masks.append(("tier", int(tiers.iloc[-1]), values["tier"] == tiers.iloc[-1]))
    masks.append(("market", "all", pd.Series(True, index=values.index)))
    floor = min_occurrences()
    levels = [_level(values, m, hit, k, sessions, name, g) for name, g, m in masks]
    chosen = next((x for x in levels if x.n_declustered >= floor), levels[-1])
    sector = None
    if sectors is not None and symbol in sectors:
        same = values["symbol"].map(sectors) == sectors[symbol]
        sector = _level(values, same, hit, k, sessions, "sector", sectors[symbol], True)
    shown = values["trade_date"]
    return Evidence(
        symbol=symbol,
        conditions=dict(conditions),
        k=k,
        period=(
            str(shown.min()) if len(shown) else None,
            str(shown.max()) if len(shown) else None,
        ),
        chosen=chosen,
        levels=levels,
        sufficient=chosen.n_declustered >= floor,
        min_occurrences=floor,
        net_provisional=bool(v.manifest["net_provisional"]),
        before=v.manifest["before"],
        sector=sector,
    )


def _hit(values: pd.DataFrame, conditions: dict) -> pd.Series:
    """patterns.fingerprint.query on the gated rows: 1 / 0 / NaN (unknown)."""
    from types import SimpleNamespace

    return query(SimpleNamespace(values=values), conditions).hit


def stamp(e: Evidence) -> str:
    """One line per level, for a report: never a number without its level."""
    net = " NET PROVISIONAL (broker fee not confirmed)" if e.net_provisional else ""
    lines = [
        f"{e.symbol} {e.conditions} k={e.k} period {e.period[0]}..{e.period[1]}"
        f" before {e.before}{net}"
    ]
    for x in [*e.levels, *([e.sector] if e.sector else [])]:
        mark = " <- used" if x is e.chosen else ""
        tag = " EXPLORATORY (current labels)" if x.exploratory else ""
        lines.append(
            f"  {x.level}:{x.group} n {x.n_raw} ({x.n_declustered} de-clustered)"
            f" hit {x.hit_rate:.1%} vs base {x.base_rate:.1%} (n {x.base_n})"
            f" edge {x.edge:+.1%} exp {x.expectancy:+.2%} drops {x.drops}{mark}{tag}"
        )
    return "\n".join(lines)
