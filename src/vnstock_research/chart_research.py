"""Isolated, price-only research pilot for double levels and triangles.

The production fingerprint and returns hash their own source trees. Keeping
this pilot here means studying a new drawing cannot rewrite the six accepted
daily-scan signals. A chart name is a *question*; this module records causal
episodes, not a claim that the name predicts a return.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = (
    Path(__file__).resolve().parents[2] / "config" / "rules" / "chart_research.yaml"
)


def rules() -> dict:
    """The single registered pilot specification; never fitted to returns."""
    return yaml.safe_load(CONFIG.read_text())


def rules_hash() -> str:
    return hashlib.sha256(CONFIG.read_bytes()).hexdigest()[:16]


def code_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


def source_code_hash() -> str:
    """Bar-loading and data rules also determine which shape was observed."""
    from . import store

    return store.code_hash(("data", "features/bars.py"))


HORIZONS = tuple(int(k) for k in rules()["horizons"])
PRIMARY_HORIZON = int(rules()["primary_horizon"])
EVENT_COLUMNS = (
    "symbol",
    "variant",
    "family",
    "episode_id",
    "state",
    "side",
    "formation_start",
    "formation_end",
    "anchor_dates",
    "anchor_confirmed_on",
    "candidate_on",
    "signal_on",
    "ended_on",
    "failure_on",
    "boundary_at_signal",
    "prior_trend",
    "reason",
)


def _segments(bars: pd.DataFrame):
    """Yield contiguous usable price spans; a real gap never becomes time."""
    close = bars["close"].to_numpy("float64")
    gap = bars["gap_before"].fillna(0).to_numpy() > 0
    broken = (
        bars["factor_break"].fillna(False).to_numpy(bool)
        if "factor_break" in bars
        else np.zeros(len(bars), bool)
    )
    excluded = bars["excluded"].fillna(False).to_numpy(bool)
    shifted = (
        bars["date_shifted"].fillna(False).to_numpy(bool)
        if "date_shifted" in bars
        else np.zeros(len(bars), bool)
    )
    start = None
    for i in range(len(bars)):
        valid = (
            np.isfinite(close[i]) and close[i] > 0 and not (excluded[i] or shifted[i])
        )
        if start is not None and (gap[i] or broken[i] or not valid):
            yield start, i
            start = None
        if valid and start is None:
            start = i
    if start is not None:
        yield start, len(bars)


def _pivot(close: np.ndarray, t: int, radius: int):
    """At close t, confirm only the pivot at t-radius (ties: earliest)."""
    j = t - radius
    window = close[j - radius : t + 1]
    if not np.isfinite(window).all():
        return None
    high = int(np.argmax(window)) == radius
    low = int(np.argmin(window)) == radius
    if high == low:
        return None  # a constant bar cannot be both a high and a low
    return ("high" if high else "low", j, float(close[j]))


def _line(a: tuple, b: tuple):
    """Log-close boundary through two confirmed anchors."""
    slope = (math.log(b[2]) - math.log(a[2])) / (b[1] - a[1])
    return lambda i: math.exp(math.log(a[2]) + slope * (i - a[1]))


def _width(upper: float, lower: float) -> float:
    return 2 * (upper - lower) / (upper + lower)


def _level_candidate(
    pivots: list[tuple], close: np.ndarray, cfg: dict, segment_start: int
):
    if len(pivots) < 3:
        return None
    a, middle, b = pivots[-3:]
    if a[0] != b[0] or a[0] == middle[0]:
        return None
    p = cfg["repeated_level"]
    span = b[1] - a[1]
    if not p["separation_min"] <= span <= p["separation_max"]:
        return None
    mean = (a[2] + b[2]) / 2
    if abs(a[2] - b[2]) / mean > p["level_tolerance"]:
        return None
    depth = (mean - middle[2]) / mean if a[0] == "high" else (middle[2] - mean) / mean
    if depth < p["swing_depth_min"]:
        return None
    variant = "double_top" if a[0] == "high" else "double_bottom"
    prior = "unknown"
    n = int(p["prior_trend_sessions"])
    # A prior-trend label is unknown after a suspension until its whole
    # 60-session window is inside this same adjusted-price segment.
    if a[1] - n >= segment_start:
        change = close[a[1] - 1] / close[a[1] - n] - 1
        expected = (
            change >= p["prior_trend_change"]
            if a[0] == "high"
            else change <= -p["prior_trend_change"]
        )
        prior = "reversal_context" if expected else "other"
    return {
        "variant": variant,
        "family": "repeated_level",
        "anchors": (a, middle, b),
        "start": a[1],
        "end": b[1],
        "expiry": int(p["candidate_expiry"]),
        "upper": lambda i: max(a[2], b[2]) if a[0] == "high" else middle[2],
        "lower": lambda i: middle[2] if a[0] == "high" else min(a[2], b[2]),
        "prior_trend": prior,
    }


def _triangle_candidate(pivots: list[tuple], cfg: dict):
    if len(pivots) < 5:
        return None
    anchors = tuple(pivots[-5:])
    p = cfg["triangle"]
    start, end = anchors[0][1], anchors[-1][1]
    if not p["span_min"] <= end - start <= p["span_max"]:
        return None
    highs = [a for a in anchors if a[0] == "high"]
    lows = [a for a in anchors if a[0] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return None
    upper, lower = _line(highs[0], highs[-1]), _line(lows[0], lows[-1])
    for side, line in ((highs, upper), (lows, lower)):
        for middle in side[1:-1]:
            if abs(middle[2] / line(middle[1]) - 1) > p["middle_touch_tolerance"]:
                return None
    u0, l0, u1, l1 = upper(start), lower(start), upper(end), lower(end)
    if l0 <= 0 or l1 <= 0 or not (u0 > l0 and u1 > l1):
        return None
    w0, w1 = _width(u0, l0), _width(u1, l1)
    if not (
        w0 >= p["width_initial_min"]
        and w1 >= p["width_final_min"]
        and w1 <= p["width_final_initial_max"] * w0
    ):
        return None
    du, dl = u1 / u0 - 1, l1 / l0 - 1
    flat = p["flat_drift_max"]
    if du < -flat and dl > flat:
        variant = "symmetric_triangle"
    elif abs(du) <= flat and dl > flat:
        variant = "ascending_triangle"
    elif du < -flat and abs(dl) <= flat:
        variant = "descending_triangle"
    else:
        return None
    return {
        "variant": variant,
        "family": "triangle",
        "anchors": anchors,
        "start": start,
        "end": end,
        "expiry": int(p["candidate_expiry"]),
        "upper": upper,
        "lower": lower,
        "prior_trend": "not_required",
    }


def detect(bars: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """One row per candidate episode; a signal is only its first known close break.

    Input is one symbol's adjusted bars in trading-session order. Confirmed
    pivots arrive two closes after their extrema; all boundaries are frozen at
    candidate creation. Gaps/adjustment defects terminate the formation.
    """
    cfg = config or rules()
    if not len(bars):
        return pd.DataFrame(columns=EVENT_COLUMNS)
    if bars["symbol"].nunique() != 1 or not bars["trade_date"].is_monotonic_increasing:
        raise ValueError("detect requires one symbol in increasing session order")
    close = bars["close"].to_numpy("float64")
    dates = bars["trade_date"].tolist()
    symbol = str(bars["symbol"].iloc[0])
    radius, sep, margin = (
        int(cfg["pivot_radius"]),
        int(cfg["pivot_separation"]),
        float(cfg["breakout_margin"]),
    )
    events: list[dict] = []
    for start, stop in _segments(bars):
        pivots: list[tuple] = []
        active: dict[str, dict] = {}
        watching: list[dict] = []
        used_end: dict[str, int] = {}
        for t in range(start, stop):
            # Failure is learned on the later day, never backdated to a signal.
            for event in watching[:]:
                if t > event["_signal_idx"] + int(cfg["failure_sessions"]):
                    watching.remove(event)
                    continue
                boundary = event["_boundary"](t)
                failed = (
                    close[t] < boundary * (1 - margin)
                    if event["side"] == "up"
                    else close[t] > boundary * (1 + margin)
                )
                if failed:
                    event["failure_on"] = dates[t]
                    watching.remove(event)

            for family, event in list(active.items()):
                upper, lower = event["_upper"](t), event["_lower"](t)
                expired = t > event["_candidate_idx"] + event["_expiry"] or (
                    family == "triangle"
                    and (
                        t > event["_start_idx"] + cfg["triangle"]["span_max"]
                        or upper <= lower
                    )
                )
                if expired:
                    event.update(
                        state="expired", ended_on=dates[t], reason="age_or_apex"
                    )
                    used_end[family] = event["_end_idx"]
                    del active[family]
                    continue
                prev_up = close[t - 1] > event["_upper"](t - 1) * (1 + margin)
                prev_down = close[t - 1] < event["_lower"](t - 1) * (1 - margin)
                up = close[t] > upper * (1 + margin) and not prev_up
                down = close[t] < lower * (1 - margin) and not prev_down
                if up or down:
                    if up and down:
                        event.update(
                            state="invalidated",
                            ended_on=dates[t],
                            reason="ambiguous_break",
                        )
                    else:
                        side = "up" if up else "down"
                        event.update(
                            state=f"confirmed_{side}",
                            side=side,
                            signal_on=dates[t],
                            ended_on=dates[t],
                            boundary_at_signal=upper if up else lower,
                        )
                        event["_signal_idx"] = t
                        event["_boundary"] = event["_upper"] if up else event["_lower"]
                        watching.append(event)
                    used_end[family] = event["_end_idx"]
                    del active[family]

            if t < start + 2 * radius:
                continue
            new = _pivot(close, t, radius)
            if new is None:
                continue
            if pivots and new[0] == pivots[-1][0]:
                better = (
                    new[2] > pivots[-1][2]
                    if new[0] == "high"
                    else new[2] < pivots[-1][2]
                )
                if better:
                    pivots[-1] = new
                continue
            if pivots and new[1] - pivots[-1][1] < sep:
                continue
            pivots.append(new)
            for candidate in (
                _level_candidate(pivots, close, cfg, start),
                _triangle_candidate(pivots, cfg),
            ):
                if candidate is None:
                    continue
                family = candidate["family"]
                if family in active or candidate["start"] <= used_end.get(family, -1):
                    continue
                upper, lower = candidate["upper"], candidate["lower"]
                if upper(t) <= lower(t):
                    continue
                anchors = candidate["anchors"]
                event = {
                    "symbol": symbol,
                    "variant": candidate["variant"],
                    "family": family,
                    "episode_id": f"{symbol}:{dates[candidate['start']]}:{family}",
                    "state": "forming",
                    "side": None,
                    "formation_start": dates[candidate["start"]],
                    "formation_end": dates[candidate["end"]],
                    "anchor_dates": [dates[a[1]] for a in anchors],
                    "anchor_confirmed_on": [dates[a[1] + radius] for a in anchors],
                    "candidate_on": dates[t],
                    "signal_on": None,
                    "ended_on": None,
                    "failure_on": None,
                    "boundary_at_signal": np.nan,
                    "prior_trend": candidate["prior_trend"],
                    "reason": None,
                    "_upper": upper,
                    "_lower": lower,
                    "_candidate_idx": t,
                    "_start_idx": candidate["start"],
                    "_end_idx": candidate["end"],
                    "_expiry": candidate["expiry"],
                }
                # A late-discovered drawing cannot create a fictitious first
                # crossing from price that was already outside its boundaries.
                outside = any(
                    close[i] > upper(i) * (1 + margin)
                    or close[i] < lower(i) * (1 - margin)
                    for i in range(candidate["end"], t + 1)
                )
                if outside:
                    event.update(
                        state="late_or_unobservable",
                        ended_on=dates[t],
                        reason="outside_before_candidate",
                    )
                    used_end[family] = candidate["end"]
                else:
                    active[family] = event
                events.append(event)

        for event in active.values():
            if stop < len(bars):
                event.update(
                    state="interrupted", ended_on=dates[stop], reason="data_break"
                )
        # Watchers stop at the segment boundary; a later gap cannot be called
        # a normal post-breakout failure.
    return pd.DataFrame(
        [{k: event.get(k) for k in EVENT_COLUMNS} for event in events],
        columns=EVENT_COLUMNS,
    )


def signal_frame(
    bars: pd.DataFrame, events: pd.DataFrame, eligible_history: int | None = None
) -> pd.DataFrame:
    """Dated 1/0/unknown flags, including every comparable no-pattern day.

    The longest pilot geometry needs 120 sessions plus its pivot confirmation.
    Before a whole 125-session clean segment exists, "no signal" is unknown,
    not a valid base-rate observation. This also excludes early new listings.
    """
    history = int(eligible_history or rules()["eligible_history_sessions"])
    variants = rules()["variants"]
    # The detector uses session positions. Normalize arbitrary DataFrame index
    # labels here too, or a date found at position 42 could write to label 42.
    out = bars[["symbol", "trade_date"]].reset_index(drop=True).copy()
    for variant in variants:
        out[variant] = np.nan
    for start, stop in _segments(bars):
        if stop - start >= history:
            out.loc[start + history - 1 : stop - 1, variants] = 0.0
    date_index = pd.Index(bars["trade_date"])
    for event in events.itertuples(index=False):
        if event.signal_on is None or event.variant not in variants:
            continue
        i = date_index.get_loc(event.signal_on)
        if pd.notna(out.at[i, event.variant]):
            out.at[i, event.variant] = 1.0
    return out


def outcomes(bars: pd.DataFrame, calendar) -> pd.DataFrame:
    """The unchanged tradeable return core, called with four explicit horizons."""
    from .backtest import forward_returns as fr

    return fr.outcomes(bars, calendar, ks=HORIZONS)


def _artifact_dir(build_id: int, root: Path) -> Path:
    return root / f"{build_id}_{rules_hash()}_{code_hash()}"


def write_artifact(
    events: pd.DataFrame,
    signals: pd.DataFrame,
    returns: pd.DataFrame,
    build_id: int,
    root: Path | None = None,
) -> Path:
    """Store the census and four-horizon outcomes away from frozen tables."""
    from . import store
    from .backtest import forward_returns as fr
    from .features.base import FLAG

    target = _artifact_dir(build_id, root or store.PROCESSED / "chart_research")
    basis = {
        "build_id": build_id,
        "chart_rules": rules_hash(),
        "chart_code": code_hash(),
        "source_code": source_code_hash(),
    }
    event_rows = events.copy()
    event_rows["trade_date"] = event_rows["signal_on"].where(
        event_rows["signal_on"].notna(), event_rows["candidate_on"]
    )
    for name in ("anchor_dates", "anchor_confirmed_on"):
        event_rows[name] = event_rows[name].map(
            lambda dates: json.dumps([str(d) for d in dates])
        )
    store.write(event_rows, target / "events", basis)
    store.write(
        signals,
        target / "signals",
        {
            **basis,
            "featureset": rules_hash(),
            "code": code_hash(),
            "flagged": [],
            "variants": rules()["variants"],
        },
    )
    costs = fr.load_costs()
    store.write(
        returns,
        target / "returns",
        {
            **basis,
            "rules": fr.rules_hash(),
            "code": fr.code_hash(),
            "horizons": list(HORIZONS),
            "primary_horizon": PRIMARY_HORIZON,
            "net_provisional": costs.provisional,
            "costs": {
                "broker_fee_rate": costs.broker_fee_rate,
                "sale_tax_rate": costs.sale_tax_rate,
            },
            "flag_for": {
                f"{name}_{k}": f"{FLAG}fill_{k}"
                for k in HORIZONS
                for name in fr.OUTCOME
            },
        },
    )
    return target


def load_artifact(build_id: int, root: Path | None = None):
    """Refuse a stale research artifact and return events, flags and returns."""
    from . import store
    from .backtest import forward_returns as fr
    from .patterns.fingerprint import Fingerprint

    target = _artifact_dir(build_id, root or store.PROCESSED / "chart_research")
    basis = {
        "build_id": build_id,
        "chart_rules": rules_hash(),
        "chart_code": code_hash(),
        "source_code": source_code_hash(),
    }
    events, _ = store.load(target / "events", "chart events", str(build_id), basis)
    signals, signal_man = store.load(
        target / "signals",
        "chart signals",
        str(build_id),
        {**basis, "featureset": rules_hash(), "code": code_hash()},
    )
    returns, return_man = store.load(
        target / "returns",
        "chart returns",
        str(build_id),
        {
            **basis,
            "rules": fr.rules_hash(),
            "code": fr.code_hash(),
            "horizons": list(HORIZONS),
        },
    )
    return (
        events,
        Fingerprint(signals, pd.DataFrame(), signal_man),
        fr.Returns(returns, return_man),
    )


def assemble(frames, calendar):
    """Build the event census, comparable signal days and returns together."""
    event_parts, signal_parts, return_parts = [], [], []
    for bars in frames:
        events = detect(bars)
        event_parts.append(events)
        signal_parts.append(signal_frame(bars, events))
        return_parts.append(outcomes(bars, calendar))
    if not signal_parts:
        raise ValueError("no bars available for the chart research census")
    return (
        pd.concat(event_parts, ignore_index=True),
        pd.concat(signal_parts, ignore_index=True),
        pd.concat(return_parts, ignore_index=True),
    )


def build(conn, start: str = "2012-01-01", root: Path | None = None) -> Path:
    """Full promoted-build census, written only to the separate pilot store."""
    from .features import bars

    build_id = bars.current_build(conn)
    calendar = [
        row[0]
        for row in conn.execute(
            "SELECT trade_date FROM trading_day WHERE trade_date >= %s ORDER BY 1",
            (start,),
        ).fetchall()
    ]
    symbols = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
            "AND trade_date >= %s ORDER BY 1",
            (build_id, start),
        ).fetchall()
    ]
    # ponytail: this mirrors the existing fingerprint/returns full-build
    # collector; stream by year if the whole-market pilot exceeds RAM.
    events, signals, returns = assemble(
        (f for _, f in bars.load_many(conn, symbols, start=start, build=build_id)),
        calendar,
    )
    return write_artifact(events, signals, returns, build_id, root)


def descriptive_market(fp, rt, universe: pd.DataFrame) -> pd.DataFrame:
    """All 20 registered cells vs the identical eligible base, NOT proof.

    The old 2012–2023 dates have already informed project research. These
    period tables are diagnostics and temporal replication only, never a new
    holdout verdict or an admission to the production scan.
    """
    from .backtest import evidence

    rows = []
    slices = (
        ("development_seen", "2012-01-01", "2019-12-31", "2020-01-01"),
        ("replication_seen", "2020-01-01", "2023-12-31", "2024-01-01"),
    )
    for label, start, end, before in slices:
        gated = evidence.validated(fp, rt, universe, before=before)
        if gated.values.empty:
            continue
        symbol = str(gated.values["symbol"].iloc[0])
        for variant in rules()["variants"]:
            for k in HORIZONS:
                result = evidence.evidence(
                    gated, {variant: 1}, k, symbol, start=start, end=end
                )
                market = result.levels[-1]
                rows.append(
                    {
                        "slice": label,
                        "variant": variant,
                        "k": k,
                        "n_raw": market.n_raw,
                        "n_declustered": market.n_declustered,
                        "base_n": market.base_n,
                        "hit_rate": market.hit_rate,
                        "base_rate": market.base_rate,
                        "edge": market.edge,
                        "net_expectancy_provisional": market.expectancy,
                        "status": "DESCRIPTIVE_ONLY_SPENT_HISTORY",
                    }
                )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from .data import db, universe

    with db.connect() as connection:
        path = build(connection)
        build_id = int(path.name.split("_")[0])
        events, signals, returns = load_artifact(build_id)
        tiers = universe.tiers(connection, "2012-01-01", "2023-12-31")
        print(f"research artifact: {path}")
        print(f"candidate episodes: {len(events):,}")
        print(descriptive_market(signals, returns, tiers).to_string(index=False))
