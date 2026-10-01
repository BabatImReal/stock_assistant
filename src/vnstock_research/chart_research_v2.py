"""Contained, observed-break-side chart pilot; v1 and the scan stay frozen.

V2 reuses v1's pivot/geometry primitives but owns the episode loop: an
invalid formation must be rejected before it can suppress a later candidate.
Filtering v1's finished event table would silently lose those later cases.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import chart_research as v1

CONFIG = (
    Path(__file__).resolve().parents[2] / "config" / "rules" / "chart_research_v2.yaml"
)


def rules() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def rules_hash() -> str:
    return hashlib.sha256(CONFIG.read_bytes()).hexdigest()[:16]


def code_hash() -> str:
    # V2 imports v1 geometry; a v1 edit must stale every v2 artifact.
    return hashlib.sha256(
        Path(__file__).read_bytes() + v1.code_hash().encode()
    ).hexdigest()[:16]


def _require_base() -> None:
    if rules()["geometry_base"] != {
        "rules_hash": v1.rules_hash(),
        "code_hash": v1.code_hash(),
    }:
        raise ValueError("v2 geometry base changed; register a new version")


VARIANTS = tuple(rules()["variants"])
SIDES = tuple(rules()["observed_break_sides"])
HORIZONS = tuple(rules()["horizons"])
SIGNALS = tuple(f"{variant}__{side}" for variant in VARIANTS for side in SIDES)
POLICY = rules()["formation_containment"]


def _contained(candidate: dict, close: np.ndarray, policy: dict) -> bool:
    """The eventual walls must contain every first-to-last-anchor close."""
    tolerance = float(
        policy[
            "triangle_tolerance"
            if candidate["family"] == "triangle"
            else "repeated_level_tolerance"
        ]
    )
    upper, lower = candidate["upper"], candidate["lower"]
    return all(
        upper(i) > lower(i)
        and lower(i) * (1 - tolerance) <= close[i] <= upper(i) * (1 + tolerance)
        for i in range(candidate["start"], candidate["end"] + 1)
    )


def detect(bars: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """V1 causal episode states, with full-formation containment before entry."""
    _require_base()
    cfg = config or v1.rules()
    if not len(bars):
        return pd.DataFrame(columns=v1.EVENT_COLUMNS)
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
    for start, stop in v1._segments(bars):
        pivots: list[tuple] = []
        active: dict[str, dict] = {}
        watching: list[dict] = []
        used_end: dict[str, int] = {}
        for t in range(start, stop):
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
            new = v1._pivot(close, t, radius)
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
                v1._level_candidate(pivots, close, cfg, start),
                v1._triangle_candidate(pivots, cfg),
            ):
                if candidate is None:
                    continue
                family = candidate["family"]
                if family in active or candidate["start"] <= used_end.get(family, -1):
                    continue
                upper, lower = candidate["upper"], candidate["lower"]
                if upper(t) <= lower(t) or not _contained(candidate, close, POLICY):
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
                # The older 0.5% first-cross rule still rejects a break
                # between the last anchor and candidate confirmation.
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
    return pd.DataFrame(
        [{key: event.get(key) for key in v1.EVENT_COLUMNS} for event in events],
        columns=v1.EVENT_COLUMNS,
    )


def signal_frame(bars: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """One-hot observed break side, with v1's unknown-history semantics."""
    out = bars[["symbol", "trade_date"]].reset_index(drop=True).copy()
    for name in SIGNALS:
        out[name] = np.nan
    history = int(rules()["eligible_history_sessions"])
    for start, stop in v1._segments(bars):
        if stop - start >= history:
            out.loc[start + history - 1 : stop - 1, list(SIGNALS)] = 0.0
    date_index = pd.Index(bars["trade_date"])
    for event in events.itertuples(index=False):
        if event.signal_on is None or event.side not in SIDES:
            continue
        name = f"{event.variant}__{event.side}"
        i = date_index.get_loc(event.signal_on)
        if pd.notna(out.at[i, name]):
            out.at[i, name] = 1.0
    return out


def _artifact_dir(build_id: int, root: Path) -> Path:
    return root / f"{build_id}_{rules_hash()}_{code_hash()}"


def _basis(build_id: int) -> dict:
    return {
        "build_id": build_id,
        "chart_rules": rules_hash(),
        "chart_code": code_hash(),
        "v1_rules": v1.rules_hash(),
        "v1_code": v1.code_hash(),
        "source_code": v1.source_code_hash(),
    }


def write_artifact(
    events: pd.DataFrame,
    signals: pd.DataFrame,
    build_id: int,
    root: Path | None = None,
) -> Path:
    """Store only v2 events/signals; existing v1 four-horizon returns remain."""
    from . import store

    _require_base()
    target = _artifact_dir(build_id, root or store.PROCESSED / "chart_research_v2")
    basis = _basis(build_id)
    event_rows = events.copy()
    event_rows["trade_date"] = event_rows["signal_on"].where(
        event_rows["signal_on"].notna(), event_rows["candidate_on"]
    )
    for name in ("anchor_dates", "anchor_confirmed_on"):
        event_rows[name] = event_rows[name].map(
            lambda dates: json.dumps([str(date) for date in dates])
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
            "variants": list(SIGNALS),
        },
    )
    return target


def load_artifact(build_id: int, root: Path | None = None, v1_root: Path | None = None):
    """Load v2 episodes/flags and the version-checked unchanged v1 returns."""
    from . import store
    from .backtest import forward_returns as fr
    from .patterns.fingerprint import Fingerprint

    _require_base()
    target = _artifact_dir(build_id, root or store.PROCESSED / "chart_research_v2")
    basis = _basis(build_id)
    events, _ = store.load(target / "events", "chart v2 events", str(build_id), basis)
    signals, signal_man = store.load(
        target / "signals",
        "chart v2 signals",
        str(build_id),
        {**basis, "featureset": rules_hash(), "code": code_hash()},
    )
    old = v1._artifact_dir(build_id, v1_root or store.PROCESSED / "chart_research")
    returns, return_man = store.load(
        old / "returns",
        "chart v1 returns",
        str(build_id),
        {
            "build_id": build_id,
            "chart_rules": v1.rules_hash(),
            "chart_code": v1.code_hash(),
            "source_code": v1.source_code_hash(),
            "rules": fr.rules_hash(),
            "code": fr.code_hash(),
            "horizons": list(HORIZONS),
        },
    )
    if not signals[["symbol", "trade_date"]].equals(returns[["symbol", "trade_date"]]):
        raise ValueError("v2 signals and v1 returns have different stock-day keys")
    return (
        events,
        Fingerprint(signals, pd.DataFrame(), signal_man),
        fr.Returns(returns, return_man),
    )


def build(conn, start: str = "2012-01-01", root: Path | None = None) -> Path:
    """Re-detect every stock; leave the old return table and scan unchanged."""
    from .features import bars

    _require_base()
    build_id = bars.current_build(conn)
    symbols = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
            "AND trade_date >= %s ORDER BY 1",
            (build_id, start),
        ).fetchall()
    ]
    event_parts, signal_parts = [], []
    for _, frame in bars.load_many(conn, symbols, start=start, build=build_id):
        episodes = detect(frame)
        event_parts.append(episodes)
        signal_parts.append(signal_frame(frame, episodes))
    if not signal_parts:
        raise ValueError("no bars available for v2 chart research")
    return write_artifact(
        pd.concat(event_parts, ignore_index=True),
        pd.concat(signal_parts, ignore_index=True),
        build_id,
        root,
    )


def descriptive_market(fp, rt, universe: pd.DataFrame) -> pd.DataFrame:
    """All 40 registered long-only cells; spent history is not a verdict."""
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
        for name in SIGNALS:
            for k in HORIZONS:
                result = evidence.evidence(
                    gated, {name: 1}, k, symbol, start=start, end=end
                )
                market = result.levels[-1]
                rows.append(
                    {
                        "slice": label,
                        "signal": name,
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
