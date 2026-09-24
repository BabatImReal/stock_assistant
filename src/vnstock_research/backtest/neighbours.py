"""Look-alikes (doc §3.6; E4): past days that looked like today, and what
followed. ONE fixed method, pre-registered in config/rules/protocol.yaml
(`neighbours`, its own frozen block) before it ran.

ILLUSTRATIVE, not a statistical claim. It shows Ben concrete past cases the way
a broker thinks ("I have seen this before"), with their outcomes. It never
enters N, the discover/validate results, or anything called validated.

The method, exactly as registered:
  - a neighbour has EXACTLY today's fired set of the registered triggers,
    every trigger known on both days (a NaN trigger never matches anything);
  - numeric context measures become the SAME-DAY percentile among that day's
    liquid stocks, never scaled over full history (that would be look-ahead);
    booleans stay 1 / 0;
  - distance = the mean absolute difference over the columns known on BOTH
    days (equal weights). A missing value never matches a 0: that column is
    left out, and a pair needs `min_known_share` of columns known on both;
  - the k nearest;
  - the pool passes the gate (backtest.evidence.validated: liquid on t,
    quarantines, same build) and its outcomes resolved strictly before the
    query day. Until the holdout is run, the pool also stops before the
    holdout starts (`pool_before`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .. import store
from .evidence import validated

LOG = store.PKG.parents[1] / "research" / "neighbours_log.csv"


def neighbours_hash(proto: dict) -> str:
    blob = json.dumps(proto["neighbours"], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def check_frozen(proto: dict, log_path: Path = LOG) -> None:
    if not Path(log_path).exists():
        return
    seen = set(pd.read_csv(log_path)["neighbours"].dropna())
    now = neighbours_hash(proto)
    if seen and seen != {now}:
        raise ValueError(
            f"the registered neighbour method changed after its first run "
            f"(log {sorted(seen)}, now {now})"
        )


def encode(rows: pd.DataFrame, spec: dict, triggers: list) -> pd.DataFrame:
    """KEYS, `liquid`, `fired` (the fired-set key, None unless every trigger is
    known), and each context column as matched on: numerics as that day's
    percentile among the LIQUID rows, booleans as 1 / 0."""
    liquid = rows["tier"].notna()
    out = rows[store.KEYS].copy()
    out["liquid"] = liquid.to_numpy()
    t = rows[triggers]
    names = pd.Series([f"{n}|" for n in triggers], index=triggers)
    key = (t == 1).astype(int).dot(names) if len(t) else pd.Series(dtype=object)
    # None, not NaN, where a trigger could not be judged (object dtype: a
    # string column would silently turn None into NaN).
    out["fired"] = np.where(t.notna().all(axis=1).to_numpy(), key.to_numpy(), None)
    for c in spec["numeric"]:
        out[c] = (
            rows[c].where(liquid).groupby(rows["trade_date"]).rank(pct=True).to_numpy()
        )
    for c in spec["boolean"]:
        out[c] = rows[c].astype("float64").to_numpy()
    return out


def distance(q: np.ndarray, m: np.ndarray, min_share: float):
    """(distance, share known on both) of each row of m to q. A column unknown
    on either side is left out, never counted as a match."""
    known = ~np.isnan(m) & ~np.isnan(q)
    n = known.sum(axis=1)
    share = n / m.shape[1]
    d = np.where(known, np.abs(m - q), 0.0).sum(axis=1) / np.maximum(n, 1)
    return np.where(share >= min_share, d, np.nan), share


@dataclass(frozen=True)
class LookAlikes:
    symbol: str
    day: str
    fired: str | None
    neighbours: pd.DataFrame  # nearest first: symbol, trade_date, distance, ...
    reason: str | None  # why there are none, if none
    pool_before: str
    net_provisional: bool


def look_alikes(fp, rt, universe_rows, symbol: str, day, proto: dict) -> LookAlikes:
    """The registered look-alike search for `symbol` on `day`."""
    spec, triggers = proto["neighbours"], proto["registered"]["triggers"]
    cols = spec["numeric"] + spec["boolean"]
    day = pd.Timestamp(day).date()
    before = min(pd.Timestamp(day), pd.Timestamp(spec["pool_before"]))

    def result(fired, found, reason):
        return LookAlikes(
            symbol,
            str(day),
            fired,
            found,
            reason,
            str(before.date()),
            bool(rt.manifest["net_provisional"]),
        )

    # The query: its own row that day, ranked among that day's liquid stocks.
    today = fp.values[fp.values["trade_date"] == day].merge(
        universe_rows[[*store.KEYS, "tier"]], on=store.KEYS, how="left"
    )
    enc = encode(today, spec, triggers)
    q = enc[enc["symbol"] == symbol]
    if q.empty or not q["liquid"].iloc[0]:
        return result(None, pd.DataFrame(), "not liquid that day")
    fired = q["fired"].iloc[0]
    if pd.isna(fired):
        return result(None, pd.DataFrame(), "a trigger could not be judged that day")

    # The pool: through the gate, outcomes resolved strictly before `before`.
    v = validated(fp, rt, universe_rows, before=before)
    pool = v.values
    penc = encode(pool, spec, triggers)
    ks = spec["horizons"]
    # An outcome at every horizon: the gate has already blanked every row that
    # is not liquid, is fill-flagged, or resolved too late, so this one check
    # carries all of them.
    known = np.logical_and.reduce([pool[f"net_{k}"].notna().to_numpy() for k in ks])
    cand = (penc["fired"] == fired).to_numpy() & known
    d, share = distance(
        q[cols].to_numpy(float)[0],
        penc.loc[cand, cols].to_numpy(float),
        float(spec["min_known_share"]),
    )
    found = pool.loc[
        cand, [*store.KEYS] + [f"{x}_{k}" for k in ks for x in ("ret", "net")]
    ]
    found = found.assign(
        distance=d, known_share=share, same_stock=found["symbol"] == symbol
    )
    found = found[found["distance"].notna()].sort_values(["distance", "trade_date"])
    found = found.head(int(spec["k"])).reset_index(drop=True)
    return result(
        fired, found, None if len(found) else "no past day with this fired set"
    )


def report(la: LookAlikes, proto: dict) -> list[str]:
    ks = proto["neighbours"]["horizons"]
    net = " | NET PROVISIONAL (fee not confirmed)" if la.net_provisional else ""
    lines = [
        f"LOOK-ALIKES (ILLUSTRATIVE, not a statistical claim) {la.symbol} {la.day} | "
        f"method {neighbours_hash(proto)} | pool resolved before {la.pool_before}{net}",
        f"  fired: {la.fired.rstrip('|').replace('|', ' + ') if la.fired else '-'}"
        + ("  (nothing fired)" if la.fired == "" else ""),
    ]
    if la.reason:
        return lines + [f"  none: {la.reason}"]
    n = la.neighbours
    parts = []
    for k in ks:
        net_k = n[f"net_{k}"]
        parts.append(
            f"{k}d: {(net_k > 0).mean():.0%} net > 0, mean {net_k.mean():+.2%}"
        )
    lines.append(
        f"  {len(n)} neighbours (same stock {int(n['same_stock'].sum())}); "
        + "; ".join(parts)
    )
    for _, r in n.head(10).iterrows():
        outs = " ".join(f"{k}d {r[f'net_{k}']:+.1%}" for k in ks)
        lines.append(
            f"    {r['symbol']} {r['trade_date']} d {r['distance']:.3f} "
            f"known {r['known_share']:.0%} | {outs}"
        )
    return lines


def run(conn, symbol: str, day, log_path: Path = LOG) -> list[str]:
    from ..data import universe
    from ..patterns import fingerprint as fpm
    from . import forward_returns as fr
    from .protocol import load_protocol

    proto = load_protocol()
    check_frozen(proto, log_path)
    spec = proto["neighbours"]
    build, fs = fpm.expected(conn)
    cols = proto["registered"]["triggers"] + spec["numeric"] + spec["boolean"]
    fp = fpm.load(build, fs, columns=cols, end=str(day))
    rt = fr.load(build, end=str(day))
    uni = universe.tiers(conn, "2012-01-01", str(day))
    la = look_alikes(fp, rt, uni, symbol, day, proto)
    row = pd.DataFrame(
        [
            {
                "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "neighbours": neighbours_hash(proto),
                "build_id": build,
                "symbol": symbol,
                "day": la.day,
                "fired": la.fired,
                "found": len(la.neighbours),
                "pool_before": la.pool_before,
            }
        ]
    )
    log_path = Path(log_path)
    row.to_csv(log_path, mode="a", header=not log_path.exists(), index=False)
    return report(la, proto)


if __name__ == "__main__":
    import sys

    from ..data import db

    with db.connect() as conn:
        for line in run(conn, sys.argv[1], sys.argv[2]):
            print(line)
