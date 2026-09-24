"""The research protocol: discover -> validate with multiple-testing control
(doc §8.1-8.2; E3). The part of the project that decides whether a number is
an edge or luck.

What is tested, how and what counts as success are PRE-REGISTERED in
config/rules/protocol.yaml, committed before the first run. This module only
carries it out, and refuses every way of bending it:

  - The registered block is FROZEN: the first run writes its hash into the
    hypothesis log, and a changed block is refused afterwards.
  - The HYPOTHESIS LOG (research/hypothesis_log.csv, in git) records every
    hypothesis ever run, on which slice, with its result. N = every distinct
    hypothesis in it, printed with every result. A hypothesis that was not
    part of a slice's first use may never be tested on that slice: data once
    looked at is spent.
  - VALIDATE runs only the discover survivors, as registered, with no
    retuning. The HOLDOUT is refused here: it runs once, with Ben, at the end.

The statistics, per hypothesis and slice, on rows that passed the gate
(backtest.evidence.validated: liquid on t, fillability and feature
quarantines, past-only):
  - occurrences are DE-CLUSTERED (a repeat within k sessions shares the
    outcome window); hit = net return > 0; edge = hit rate - base rate, the
    base taken over every eligible day where the condition was judged;
  - p-value: two-sided, by resampling BLOCKS OF DATES (never rows), because
    many stocks move together on one day and an outcome spans several;
  - discover: Benjamini-Hochberg at q over ALL N;
  - validate: same sign, edge >= min_edge, net expectancy > 0.
Every result is split by year and by market regime, stamped PROVISIONAL (the
fee), and flagged when its hit rate is implausibly high.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .. import store
from ..features.base import MARKET_REGISTRY, REGISTRY, SECTOR_REGISTRY
from .evidence import _hit, declustered, validated
from .forward_returns import CONFIG

PROTOCOL = CONFIG / "protocol.yaml"
LOG = store.PKG.parents[1] / "research" / "hypothesis_log.csv"
OUT = store.PROCESSED / "protocol"
LOG_COLUMNS = [
    "run_id",
    "run_at",
    "protocol",
    "code",
    "build_id",
    "slice",
    "hypothesis",
    "n_raw",
    "n_declustered",
    "hit_rate",
    "base_rate",
    "edge",
    "expectancy",
    "p",
    "survived",
]
SLICES = ("discover", "validate", "holdout")


def load_protocol(path: Path = PROTOCOL) -> dict:
    return yaml.safe_load(Path(path).read_text())


def protocol_hash(proto: dict) -> str:
    """The frozen block's fingerprint, written into the log."""
    blob = json.dumps(proto["registered"], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# --- the vocabulary ---------------------------------------------------------


@dataclass(frozen=True)
class Hypothesis:
    trigger: str
    conditions: tuple  # condition NAMES, sorted
    k: int

    @property
    def id(self) -> str:
        return f"k{self.k}:{self.trigger}" + "".join(f"+{c}" for c in self.conditions)

    def query(self, proto: dict) -> dict:
        q = {self.trigger: 1}
        for name in self.conditions:
            q.update(proto["registered"]["conditions"][name])
        return q


def _check(trigger: str, conditions: dict) -> None:
    """A trigger is a registered boolean pattern; no condition reads a sector
    value (every one is flagged, B3), and every condition is a registered
    measure."""
    m = REGISTRY.get(trigger)
    if m is None or m.kind != "boolean" or m.fn.__module__.split(".")[-2] != "patterns":
        raise ValueError(f"trigger '{trigger}' is not a boolean pattern measure")
    for column in conditions:
        m = REGISTRY.get(column) or MARKET_REGISTRY.get(column)
        if column in SECTOR_REGISTRY or (
            m is not None and any(n in SECTOR_REGISTRY for n in m.needs)
        ):
            raise ValueError(f"condition on '{column}': a sector value is flagged (B3)")
        if m is None:
            raise ValueError(f"condition on '{column}': not a registered measure")


def vocabulary(proto: dict) -> list[Hypothesis]:
    """Every registered hypothesis, then the additions, in a fixed order."""
    reg = proto["registered"]
    for cond in reg["conditions"].values():
        _check(reg["triggers"][0], cond)
    names = sorted(reg["conditions"])
    out = []
    for k in reg["horizons"]:
        for trigger in reg["triggers"]:
            _check(trigger, {})
            for r in range(int(reg["max_conditions"]) + 1):
                out += [Hypothesis(trigger, c, int(k)) for c in combinations(names, r)]
    for a in proto.get("additions") or []:
        _check(a["trigger"], {})
        out.append(
            Hypothesis(a["trigger"], tuple(sorted(a["conditions"])), int(a["horizon"]))
        )
    return out


# --- the log ----------------------------------------------------------------


def read_log(path: Path = LOG) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(path)


def n_tested(log: pd.DataFrame, hyps) -> int:
    """N: every distinct hypothesis ever run, this run's included."""
    return len(set(log["hypothesis"]) | {h.id for h in hyps})


def check_registration(proto: dict, log: pd.DataFrame) -> None:
    now = protocol_hash(proto)
    seen = set(log["protocol"].dropna())
    if seen and seen != {now}:
        raise ValueError(
            f"the registered protocol changed after its first run (log {sorted(seen)}, "
            f"now {now}). Put new ideas in `additions`; never edit `registered`."
        )


def check_unused(hyps, slice_name: str, log: pd.DataFrame) -> None:
    """Data once looked at is spent: a hypothesis may be tested on a slice only
    if the slice is unused, or it was part of the slice's first use."""
    used = log[log["slice"] == slice_name]
    if used.empty:
        return
    first = used[used["run_id"] == used["run_id"].iloc[0]]["hypothesis"]
    late = [h.id for h in hyps if h.id not in set(first)]
    if late:
        raise ValueError(
            f"{len(late)} hypotheses were not part of the first use of '{slice_name}' "
            f"(e.g. {late[0]}): that data is already spent for them"
        )


def discover_survivors(log: pd.DataFrame, hyps) -> list[Hypothesis]:
    """The survivors of the LATEST discover run, the only ones validate may test."""
    d = log[log["slice"] == "discover"]
    if d.empty:
        raise ValueError("validate needs a discover run first")
    last = d[d["run_id"] == d["run_id"].iloc[-1]]
    ok = set(last.loc[last["survived"].astype(bool), "hypothesis"])
    return [h for h in hyps if h.id in ok]


# --- the statistics ---------------------------------------------------------


def benjamini_hochberg(p, q: float, m: int | None = None) -> np.ndarray:
    """Reject the hypotheses whose p-values pass BH at level q among m tests
    (m defaults to len(p); pass N when fewer p-values than hypotheses exist:
    every untested one counts)."""
    p = np.asarray(p, dtype="float64")
    m = len(p) if m is None else int(m)
    order = np.argsort(p)
    below = p[order] <= q * np.arange(1, len(p) + 1) / m
    out = np.zeros(len(p), bool)
    if below.any():
        out[order[: np.nonzero(below)[0].max() + 1]] = True
    return out


def resample_weights(n_blocks: int, resamples: int, seed: int) -> np.ndarray:
    """(resamples x n_blocks): how often each block of dates is drawn, with
    replacement. One matrix per slice, so every hypothesis sees the same
    draws."""
    rng = np.random.default_rng(seed)
    return rng.multinomial(n_blocks, np.full(n_blocks, 1.0 / n_blocks), size=resamples)


def block_pvalue(occ_block, occ_win, base_block, base_win, weights) -> float:
    """Two-sided p that the edge (hit rate - base rate) is zero, from resampled
    BLOCKS OF DATES: the share of draws on the far side of zero."""
    nb = weights.shape[1]
    oh = np.bincount(occ_block, weights=occ_win, minlength=nb)
    on = np.bincount(occ_block, minlength=nb)
    bh = np.bincount(base_block, weights=base_win, minlength=nb)
    bn = np.bincount(base_block, minlength=nb)
    with np.errstate(invalid="ignore", divide="ignore"):
        edge = weights @ oh / (weights @ on) - weights @ bh / (weights @ bn)
    edge = edge[np.isfinite(edge)]
    tail = min((edge <= 0).sum(), (edge >= 0).sum())
    return float(min(1.0, 2 * (tail + 1) / (len(edge) + 1)))


def _stats(rows: pd.DataFrame, occ: pd.Series, eligible: pd.Series, k: int) -> dict:
    o, b = rows[occ], rows[eligible]
    win, base = (o[f"net_{k}"] > 0), (b[f"net_{k}"] > 0)
    hit = win.mean() if len(o) else np.nan
    return {
        "n_declustered": int(len(o)),
        "hit_rate": float(hit),
        "base_rate": float(base.mean()) if len(b) else np.nan,
        "edge": float(hit - base.mean()) if len(o) and len(b) else np.nan,
        "expectancy": float(o[f"net_{k}"].mean()) if len(o) else np.nan,
        "gross": float(o[f"ret_{k}"].mean()) if len(o) else np.nan,
    }


def evaluate(v, hyps, proto: dict, start, end, pvalues: bool = True) -> pd.DataFrame:
    """One row per hypothesis on the gated rows of [start, end]: raw and
    de-clustered n, hit vs base, edge, expectancy, gross, the block p-value,
    the suspicion flag, and the splits by year and by regime (JSON)."""
    reg = proto["registered"]
    values = v.values
    d = pd.to_datetime(values["trade_date"])
    rows = values[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))].reset_index(
        drop=True
    )
    sessions = {x: i for i, x in enumerate(sorted(rows["trade_date"].unique()))}
    L = int(reg["bootstrap"]["block_sessions"])
    block = rows["trade_date"].map(sessions).to_numpy() // L
    weights = resample_weights(
        int(block.max()) + 1 if len(block) else 1,
        int(reg["bootstrap"]["resamples"]),
        int(reg["bootstrap"]["seed"]),
    )
    year = pd.to_datetime(rows["trade_date"]).dt.year
    regime = rows[reg["regime"]]
    # Only rows with an outcome at k can be eligible or an occurrence, so each
    # horizon's rows are cut once (the same answer, a quarter of the work).
    by_k = {}
    for k in sorted({h.k for h in hyps}):
        has = rows[f"net_{k}"].notna().to_numpy()
        by_k[k] = (
            rows[has].reset_index(drop=True),
            block[has],
            year[has].reset_index(drop=True),
            regime[has].reset_index(drop=True),
        )
    out = []
    for h in hyps:
        k = h.k
        rows, block_k, year_k, regime_k = by_k[k]
        net = rows[f"net_{k}"]
        hit = _hit(rows, h.query(proto))
        eligible = hit.notna() & net.notna()
        occ = eligible & (hit == 1.0)
        keep = pd.Series(False, index=rows.index)
        keep[occ[occ].index] = declustered(
            rows.loc[occ, "trade_date"], rows.loc[occ, "symbol"], sessions, k
        )
        s = _stats(rows, keep, eligible, k)
        testable = s["n_declustered"] >= int(reg["min_declustered"])
        p = 1.0
        if pvalues and testable:
            p = block_pvalue(
                block_k[keep.to_numpy()],
                (net[keep] > 0).to_numpy(float),
                block_k[eligible.to_numpy()],
                (net[eligible] > 0).to_numpy(float),
                weights,
            )
        split = {
            name: json.dumps(
                {
                    str(g): _stats(rows, keep & (key == g), eligible & (key == g), k)
                    for g in sorted(key[eligible].dropna().unique())
                },
                default=float,
            )
            for name, key in (("by_year", year_k), ("by_regime", regime_k))
        }
        out.append(
            {
                "hypothesis": h.id,
                "k": k,
                "n_raw": int(occ.sum()),
                **s,
                "testable": testable,
                "p": p,
                "suspicious": bool(s["hit_rate"] > float(reg["suspicious_hit_rate"])),
                **split,
            }
        )
    return pd.DataFrame(out)


def discover_verdict(res: pd.DataFrame, proto: dict, n: int) -> pd.Series:
    """Passed discovery: Benjamini-Hochberg at the registered q among ALL N
    hypotheses ever run (an untested one still counts), and testable."""
    q = float(proto["registered"]["fdr_q"])
    passed = benjamini_hochberg(res["p"], q, m=n)
    return pd.Series(passed, index=res.index) & res["testable"].astype(bool)


def holds(discover_edge, val: pd.DataFrame, proto: dict) -> pd.Series:
    """The registered validate rule, applied as written: the same sign, an edge
    of at least min_edge, a net expectancy above min_net_expectancy."""
    rule = proto["registered"]["validate_rule"]
    same = np.sign(val["edge"].to_numpy()) == np.sign(np.asarray(discover_edge, float))
    ok = (
        (same if rule["same_sign"] else True)
        & (val["edge"] >= float(rule["min_edge"])).to_numpy()
        & (val["expectancy"] > float(rule["min_net_expectancy"])).to_numpy()
    )
    return pd.Series(ok, index=val.index)


# --- running a slice ----------------------------------------------------------


def _slice(proto: dict, name: str) -> tuple[str, str, str]:
    """(start, end, before): `before` is the next slice's start, the purge."""
    sl = proto["registered"]["slices"]
    after = SLICES[SLICES.index(name) + 1]
    return sl[name]["start"], sl[name]["end"], sl[after]["start"]


def run(
    conn,
    slice_name: str,
    log_path: Path = LOG,
    out: Path = OUT,
    proto_path: Path = PROTOCOL,
) -> Path:
    """Run discover or validate as registered; append the log; write results."""
    if slice_name == "holdout":
        raise ValueError(
            "the holdout runs ONCE, with Ben, at the very end (protocol.yaml "
            "holdout_rule); it is not run here"
        )
    from ..data import universe
    from ..patterns import fingerprint as fpm
    from . import forward_returns as fr

    proto = load_protocol(proto_path)
    reg = proto["registered"]
    log = read_log(log_path)
    check_registration(proto, log)
    hyps = vocabulary(proto)
    if slice_name == "validate":
        hyps = discover_survivors(log, hyps)
    check_unused(hyps, slice_name, log)
    n = n_tested(log, hyps)
    start, end, before = _slice(proto, slice_name)

    build, fs = fpm.expected(conn)
    columns = sorted(
        {h.trigger for h in hyps}
        | {c for x in reg["conditions"].values() for c in x}
        | {reg["regime"]}
    )
    fp = fpm.load(build, fs, columns=columns, end=end)
    rt = fr.load(build, end=end)
    uni = universe.tiers(conn, "2012-01-01", end)
    v = validated(fp, rt, uni, before=before)
    res = evaluate(v, hyps, proto, start, end)
    if slice_name == "discover":
        res["survived"] = discover_verdict(res, proto, n)
    else:
        d = log[(log["slice"] == "discover")]
        d = d[d["run_id"] == d["run_id"].iloc[-1]].set_index("hypothesis")["edge"]
        res["discover_edge"] = res["hypothesis"].map(d).to_numpy()
        res["survived"] = holds(res["discover_edge"], res, proto)
        years = range(int(reg["slices"]["discover"]["start"][:4]), int(end[:4]) + 1)
        res["walk_forward"] = walk_forward(fp, rt, uni, hyps, proto, years)

    run_at = datetime.now(UTC).isoformat(timespec="seconds")
    run_id = f"{slice_name}-{run_at}"
    entry = res.assign(
        run_id=run_id,
        run_at=run_at,
        protocol=protocol_hash(proto),
        code=store.code_hash(("backtest", "data", "features", "patterns", "store.py")),
        build_id=build,
        slice=slice_name,
    )[LOG_COLUMNS]
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry.to_csv(log_path, mode="a", header=not log_path.exists(), index=False)

    d = Path(out) / run_id.replace(":", "")
    d.mkdir(parents=True, exist_ok=True)
    res.to_parquet(d / "results.parquet", index=False)
    (d / "report.txt").write_text(
        "\n".join(report(res, slice_name, n, proto, v.manifest, run_id)),
        encoding="utf-8",
    )
    return d


def walk_forward(fp, rt, universe_rows, hyps, proto: dict, years) -> list:
    """Each hypothesis's edge YEAR BY YEAR, each year purged at its own end (an
    outcome known only in the next year is not that year's): does the edge
    persist, or was it one good stretch? JSON per hypothesis: year -> (n, edge)."""
    per = {h.id: {} for h in hyps}
    for y in years:
        v = validated(fp, rt, universe_rows, before=f"{y + 1}-01-01")
        r = evaluate(v, hyps, proto, f"{y}-01-01", f"{y}-12-31", pvalues=False)
        for _, row in r.iterrows():
            per[row["hypothesis"]][y] = (row["n_declustered"], row["edge"])
    return [json.dumps(per[h.id], default=float) for h in hyps]


def report(
    res: pd.DataFrame, slice_name: str, n: int, proto: dict, manifest: dict, run_id: str
) -> list[str]:
    """Every line carries N; survivors listed with their splits."""
    reg = proto["registered"]
    boot = reg["bootstrap"]
    net = (
        " | NET PROVISIONAL (fee not confirmed)" if manifest["net_provisional"] else ""
    )
    if slice_name == "discover":
        outcome = (
            f"passed discovery (BH q={reg['fdr_q']} over N = {n}): "
            f"{int(res['survived'].sum())}"
        )
    else:
        outcome = (
            f"discover survivors run: {len(res)} | "
            f"HELD on validate: {int(res['survived'].sum())}"
        )
    lines = [
        f"{run_id} | {slice_name} {_slice(proto, slice_name)[:2]} | purged before "
        f"{manifest['before']} | protocol {protocol_hash(proto)} | N = {n}{net}",
        f"hit = net > 0; liquid on t; two-sided; date-block bootstrap "
        f"({boot['block_sessions']} sessions x {boot['resamples']})",
        f"run here: {len(res)} | testable (>= {reg['min_declustered']} "
        f"de-clustered): {int(res['testable'].sum())} | {outcome}",
        f"suspicious (hit > {reg['suspicious_hit_rate']:.0%}, suspect a bug first): "
        f"{int(res['suspicious'].sum())}",
    ]
    shown = res[res["survived"]] if slice_name == "discover" else res
    for _, r in shown.sort_values("edge", ascending=False).iterrows():
        tail = "  SUSPICIOUS" if r["suspicious"] else ""
        if slice_name != "discover":
            verdict = "HELD" if r["survived"] else "failed"
            tail = f" | discover {r['discover_edge']:+.1%} -> {verdict}{tail}"
        lines.append(
            f"  [N={n}] {r['hypothesis']}: n {r['n_raw']} "
            f"({r['n_declustered']} de-cl.) hit {r['hit_rate']:.1%} "
            f"vs base {r['base_rate']:.1%} edge {r['edge']:+.1%} "
            f"exp {r['expectancy']:+.2%} p {r['p']:.4f}{tail}"
        )
        for name in ("by_regime", "by_year"):
            parts = json.loads(r[name])
            cells = [
                f"{g}: {x['edge']:+.1%} (n {x['n_declustered']})"
                for g, x in parts.items()
            ]
            lines.append(f"      {name}: " + ", ".join(cells))
        if "walk_forward" in r:
            wf = json.loads(r["walk_forward"])
            pos = sum(1 for _, e in wf.values() if e == e and e > 0)
            cells = [f"{y}: {e:+.1%}" for y, (_, e) in wf.items()]
            lines.append(
                f"      walk-forward, each year purged: {pos} of {len(wf)} "
                "years positive: " + ", ".join(cells)
            )
    return lines


# --- display only: families and exploratory avoid candidates (no claim) -------


def _parts(hypothesis_id: str) -> tuple[str, frozenset]:
    trigger, *conditions = hypothesis_id.split(":", 1)[1].split("+")
    return trigger, frozenset(conditions)


def families(ids) -> list[list[str]]:
    """Nested hypotheses grouped FOR DISPLAY: the same trigger, one's
    conditions containing the other's (any horizon), joined transitively.
    Five marubozu variants are one idea seen five ways, not five edges. Each
    family is listed most general first."""
    ids = list(ids)
    parent = {h: h for h in ids}

    def root(h):
        while parent[h] != h:
            h = parent[h]
        return h

    for a, b in combinations(ids, 2):
        (ta, ca), (tb, cb) = _parts(a), _parts(b)
        if ta == tb and (ca <= cb or cb <= ca):
            parent[root(a)] = root(b)
    groups: dict = {}
    for h in ids:
        groups.setdefault(root(h), []).append(h)
    order = [sorted(g, key=lambda h: (len(_parts(h)[1]), h)) for g in groups.values()]
    return sorted(order, key=lambda g: g[0])


def summary(log: pd.DataFrame) -> list[str]:
    """The latest discover and validate runs from the log (in git), for
    display: the held survivors collapsed into families, and the negative-edge
    discover survivors as EXPLORATORY avoid candidates. Nothing here changes a
    verdict; no avoid rule is registered (there is no unused data to test one
    on without spending the holdout)."""

    def latest(name):
        d = log[log["slice"] == name]
        return d[d["run_id"] == d["run_id"].iloc[-1]].set_index("hypothesis")

    disc, val = latest("discover"), latest("validate")
    n = log["hypothesis"].nunique()
    held = val[val["survived"].astype(bool)]
    fams = families(held.index)
    lines = [
        f"N = {n} | passed discovery {int(disc['survived'].astype(bool).sum())} | "
        f"held on validate {len(held)}, in {len(fams)} families (display grouping only)"
    ]
    for i, fam in enumerate(fams, 1):
        lines.append(
            f"  family {i}: {fam[0]} ({len(fam)} member{'s' * (len(fam) > 1)})"
        )
        for h in fam:
            r = held.loc[h]
            lines.append(
                f"    [N={n}] {h}: validate edge {r['edge']:+.1%} exp "
                f"{r['expectancy']:+.2%} | discover edge {disc.loc[h, 'edge']:+.1%}"
            )
    avoid = disc[disc["survived"].astype(bool) & (disc["edge"] < 0)]
    lines.append(
        f"EXPLORATORY 'avoid' candidates: {len(avoid)} discover survivors with a "
        "NEGATIVE edge. No validated claim; no avoid rule registered."
    )
    for h, r in avoid.sort_values("edge").iterrows():
        later = f"{val.loc[h, 'edge']:+.1%}" if h in val.index else "not run"
        lines.append(
            f"    [N={n}] {h}: discover edge {r['edge']:+.1%} p {r['p']:.4f} | "
            f"validate edge {later} (exploratory)"
        )
    return lines


if __name__ == "__main__":
    import sys

    from ..data import db

    if sys.argv[1] == "summary":
        print("\n".join(summary(read_log())))
    else:
        with db.connect() as conn:
            path = run(conn, sys.argv[1])
        print((path / "report.txt").read_text())
