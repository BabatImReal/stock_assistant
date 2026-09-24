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
    retuning. The HOLDOUT is refused by `run`: it has its own path,
    `run_holdout`, which runs ONCE (with Ben) on the validate survivors only,
    under the registered holdout_rule.

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

import copy
import dataclasses
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
from .forward_returns import CONFIG, Costs, net_return

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
    """The frozen block's fingerprint, written into the log. The holdout's END
    is left out: it is the one value the registration left open on purpose
    (the freeze, "set when run"), so setting it does not unfreeze the block.
    It cannot be moved and re-run: the holdout runs once (`holdout_plan`)."""
    reg = copy.deepcopy(proto["registered"])
    reg["slices"]["holdout"]["end"] = None
    blob = json.dumps(reg, sort_keys=True, default=str)
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


def _latest(log: pd.DataFrame, slice_name: str) -> pd.DataFrame:
    """The rows of the LATEST run on a slice."""
    d = log[log["slice"] == slice_name]
    if d.empty:
        raise ValueError(f"the next slice needs a {slice_name} run first")
    return d[d["run_id"] == d["run_id"].iloc[-1]]


def survivors(log: pd.DataFrame, hyps, slice_name: str) -> list[Hypothesis]:
    """The survivors of the LATEST run on a slice, the only ones the next slice
    may test (discover -> validate -> holdout)."""
    last = _latest(log, slice_name)
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
    if slice_name not in ("discover", "validate"):
        # A typo, or a command this copy of the code does not have yet (an
        # older checkout): say so, instead of failing deep inside `_slice`.
        raise ValueError(
            f"unknown command '{slice_name}': use discover | validate | summary "
            "| freeze | holdout | describe-holdout"
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
        hyps = survivors(log, hyps, "discover")
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
        d = _latest(log, "discover").set_index("hypothesis")["edge"]
        res["discover_edge"] = res["hypothesis"].map(d).to_numpy()
        res["survived"] = holds(res["discover_edge"], res, proto)
        years = range(int(reg["slices"]["discover"]["start"][:4]), int(end[:4]) + 1)
        res["walk_forward"] = walk_forward(fp, rt, uni, hyps, proto, years)

    run_id = _append_log(res, slice_name, proto, build, log_path)
    d = Path(out) / run_id.replace(":", "")
    d.mkdir(parents=True, exist_ok=True)
    res.to_parquet(d / "results.parquet", index=False)
    (d / "report.txt").write_text(
        "\n".join(report(res, slice_name, n, proto, v.manifest, run_id)),
        encoding="utf-8",
    )
    return d


def _append_log(res, slice_name: str, proto: dict, build, log_path: Path) -> str:
    """Append one row per hypothesis to the log, with the protocol hash, the
    code hash and the build; return the run id."""
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
    return run_id


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


# --- the holdout: the single, final test, run ONCE (with Ben) -------------------

REPORTS = LOG.parent / "reports"
# An outcome in the holdout must be FINAL: not waiting for the calendar
# (pending) and not resolved only after the cutoff (the gate's not_yet_known).
NOT_FINAL = ("pending", "not_yet_known")
# INFORMATION ONLY, beside the verdict (it never changes one): NET recomputed at
# these ALL-IN round-trip costs = both broker fees + the statutory 0.10% sale
# tax, which stays fixed. The registered cost is 2 x 0.15% + 0.10% = 0.40%, so
# 0.10% is a zero-fee broker, 0.25% is 0.075% a side, and 0.40% must reproduce
# the verdict.
FEE_ROUND_TRIPS = (0.0010, 0.0025, 0.0040)


def freeze_date(values: pd.DataFrame, start, ks) -> str:
    """F, the holdout's end: the last session before the first signal day on or
    after `start` with an outcome still `pending` at any horizon in ks (the
    calendar ends before it resolves: the window is not over yet, or an exit
    deferred at the floor is still waiting). Every outcome of an entry in
    [start, F] is then final on settled prices. The cut is made at the first
    pending day, not by dropping the pending rows: those are often the
    floor-locked losers, and dropping only them would flatter the result."""
    rows = values[pd.to_datetime(values["trade_date"]) >= pd.Timestamp(start)]
    pending = np.logical_or.reduce(
        [(rows[f"reason_{k}"] == "pending").to_numpy() for k in ks]
    )
    days = sorted(rows["trade_date"].unique())
    if not pending.any():
        return str(days[-1])
    first = rows.loc[pending, "trade_date"].min()
    return str(max(d for d in days if d < first))


def cutoff(values: pd.DataFrame) -> str:
    """The holdout's point-in-time cutoff (the gate's `before`): the day after
    the last settled session. Every outcome of an entry up to F resolved by
    then, and no price after it exists; entries after F are cut by the slice,
    and `holdout` refuses any entry up to F whose outcome is not final."""
    return str((pd.Timestamp(max(values["trade_date"])) + pd.Timedelta(days=1)).date())


def holdout_plan(proto: dict, log: pd.DataFrame) -> list[Hypothesis]:
    """What the holdout may test: ONLY the hypotheses that held in the latest
    validate run. Refused unless the end is frozen, and refused if the log
    already has any holdout row: the used-data rule at its strictest, since
    the holdout is spent by its one run."""
    if proto["registered"]["slices"]["holdout"]["end"] is None:
        raise ValueError("freeze the holdout end first (registered.slices.holdout)")
    check_registration(proto, log)
    if (log["slice"] == "holdout").any():
        raise ValueError("the holdout has already been run: it runs ONCE")
    return survivors(log, vocabulary(proto), "validate")


def holdout_verdict(discover_edge, res: pd.DataFrame, proto: dict) -> pd.Series:
    """The registered holdout_rule AS WRITTEN (not `holds`: the validate rule's
    min_edge is not part of it): ACCEPT when the edge keeps its discover sign
    and the mean net return per de-clustered occurrence is above
    min_net_expectancy. Below min_declustered it is NOT TESTABLE, never a pass."""
    rule = proto["registered"]["holdout_rule"]
    same = np.sign(res["edge"].to_numpy()) == np.sign(np.asarray(discover_edge, float))
    ok = (same if rule["same_sign"] else True) & (
        res["expectancy"] > float(rule["min_net_expectancy"])
    ).to_numpy()
    testable = (res["n_declustered"] >= int(rule["min_declustered"])).to_numpy()
    verdict = np.where(testable, np.where(ok, "ACCEPT", "REJECT"), "NOT TESTABLE")
    return pd.Series(verdict, index=res.index)


def at_round_trip(v, round_trip: float, tax: float):
    """The same gated rows with NET recomputed from the gross return at another
    all-in round-trip cost: a broker fee of (round_trip - tax) / 2 a side, on
    the traded amounts (forward_returns.net_return)."""
    fee = (round_trip - tax) / 2
    if fee < 0:
        raise ValueError(f"a round trip of {round_trip:.2%} is below the sale tax")
    costs = Costs(fee, tax, True)
    nets = {
        f"net_{k}": net_return(v.values[f"ret_{k}"], costs)
        for k in v.manifest["horizons"]
    }
    return dataclasses.replace(v, values=v.values.assign(**nets))


def break_even(gross_mean: float, tax: float) -> float:
    """The all-in round-trip cost at which the mean NET return is zero. NET is
    linear in the gross, so the mean gross decides it:
    (1 + g)(1 - f - tax) / (1 + f) = 1  ->  f = ((1 + g)(1 - tax) - 1) / (2 + g)."""
    fee = ((1 + gross_mean) * (1 - tax) - 1) / (2 + gross_mean)
    return 2 * fee + tax


def holdout(v, hyps, proto: dict, discover_edge: dict, tax: float) -> pd.DataFrame:
    """The holdout statistics (evaluate: the same gate, de-clustering and
    date-block p as every slice), the frozen verdict, and beside it, as
    information only, the verdict and net at the other all-in costs."""
    sl = proto["registered"]["slices"]["holdout"]
    rows = v.values
    d = pd.to_datetime(rows["trade_date"])
    inside = rows[(d >= pd.Timestamp(sl["start"])) & (d <= pd.Timestamp(sl["end"]))]
    for k in sorted({h.k for h in hyps}):
        late = int(inside[f"reason_{k}"].isin(NOT_FINAL).sum())
        if late:
            raise ValueError(
                f"{late} holdout outcomes at k={k} are not final (pending, or "
                "known only after the cutoff): the freeze date is too late"
            )
    res = evaluate(v, hyps, proto, sl["start"], sl["end"])
    res["discover_edge"] = res["hypothesis"].map(discover_edge).to_numpy()
    res["verdict"] = holdout_verdict(res["discover_edge"], res, proto)
    # Logged as survived: ACCEPTED only (never a not-testable one).
    res["survived"] = res["verdict"] == "ACCEPT"
    res["break_even"] = [break_even(g, tax) for g in res["gross"]]
    for cost in FEE_ROUND_TRIPS:
        alt = evaluate(
            at_round_trip(v, cost, tax), hyps, proto, sl["start"], sl["end"], False
        )
        res[f"exp_at_{cost}"] = alt["expectancy"].to_numpy()
        res[f"verdict_at_{cost}"] = holdout_verdict(
            res["discover_edge"], alt, proto
        ).to_numpy()
    return res


def _holdout_gated(conn, proto: dict, hyps):
    """The gated rows of the holdout: the fingerprint columns the hypotheses
    read, the stored returns, the liquid universe, cut at the last settled
    session. ONE loader, so the holdout run and its later description see the
    same rows."""
    from ..data import universe
    from ..patterns import fingerprint as fpm
    from . import forward_returns as fr

    reg = proto["registered"]
    start, end = reg["slices"]["holdout"]["start"], reg["slices"]["holdout"]["end"]
    build, fs = fpm.expected(conn)
    columns = sorted(
        {h.trigger for h in hyps}
        | {c for x in reg["conditions"].values() for c in x}
        | {reg["regime"]}
    )
    fp = fpm.load(build, fs, columns=columns, start=start, end=end)
    rt = fr.load(build, start=start)
    uni = universe.tiers(conn, "2012-01-01", end)
    return validated(fp, rt, uni, before=cutoff(rt.values))


def run_holdout(
    conn,
    log_path: Path = LOG,
    out: Path = OUT,
    proto_path: Path = PROTOCOL,
    reports: Path = REPORTS,
) -> Path:
    """THE HOLDOUT, once: the validate survivors on [holdout start, F], every
    outcome final on the settled prices up to the last session; appended to
    the log as slice 'holdout'; the report written to reports/holdout-<F>.txt."""
    from . import forward_returns as fr

    proto = load_protocol(proto_path)
    end = proto["registered"]["slices"]["holdout"]["end"]
    log = read_log(log_path)
    hyps = holdout_plan(proto, log)
    n = n_tested(log, hyps)
    v = _holdout_gated(conn, proto, hyps)
    disc = _latest(log, "discover").set_index("hypothesis")["edge"].to_dict()
    res = holdout(v, hyps, proto, disc, fr.load_costs().sale_tax_rate)

    run_id = _append_log(res, "holdout", proto, v.manifest["build_id"], log_path)
    d = Path(out) / run_id.replace(":", "")
    d.mkdir(parents=True, exist_ok=True)
    res.to_parquet(d / "results.parquet", index=False)
    path = Path(reports) / f"holdout-{end}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(holdout_report(res, n, proto, v.manifest, run_id)) + "\n",
        encoding="utf-8",
    )
    return path


def holdout_report(
    res: pd.DataFrame, n: int, proto: dict, manifest: dict, run_id: str
) -> list[str]:
    reg = proto["registered"]
    rule, sl = reg["holdout_rule"], reg["slices"]["holdout"]
    net = (
        " | NET PROVISIONAL (fee not confirmed)" if manifest["net_provisional"] else ""
    )
    count = res["verdict"].value_counts()
    lines = [
        f"{run_id} | HOLDOUT {sl['start']} .. {sl['end']} (the freeze) | outcomes "
        f"final before {manifest['before']} | protocol {protocol_hash(proto)} | "
        f"N = {n}{net}",
        f"the rule, as registered: {rule['text']}",
        f"validate survivors run: {len(res)} | ACCEPTED {count.get('ACCEPT', 0)} | "
        f"REJECTED {count.get('REJECT', 0)} | not testable on the holdout (< "
        f"{rule['min_declustered']} de-clustered) {count.get('NOT TESTABLE', 0)}",
        "beside each verdict, INFORMATION ONLY (it changes no verdict): the "
        "two-sided date-block bootstrap p, and NET at other ALL-IN round-trip "
        "costs (both broker fees + the 0.10% sale tax; registered = 0.40%)",
    ]
    order = {"ACCEPT": 0, "REJECT": 1, "NOT TESTABLE": 2}
    shown = res.assign(o=res["verdict"].map(order)).sort_values(
        ["o", "edge"], ascending=[True, False]
    )
    for _, r in shown.iterrows():
        kept = (
            "kept" if np.sign(r["edge"]) == np.sign(r["discover_edge"]) else "FLIPPED"
        )
        p = f"p {r['p']:.4f}" if r["testable"] else "p n/a (not testable)"
        tail = "  SUSPICIOUS" if r["suspicious"] else ""
        lines.append(
            f"  [N={n}] {r['hypothesis']}: {r['verdict']} | edge {r['edge']:+.1%} "
            f"(discover {r['discover_edge']:+.1%}, sign {kept})"
            f" | net exp {r['expectancy']:+.2%} | {r['n_declustered']} de-cl. "
            f"(n {r['n_raw']}) hit {r['hit_rate']:.1%} vs base {r['base_rate']:.1%}"
            f" | {p}{tail}"
        )
        fees = "; ".join(
            f"{c:.2%}: exp {r[f'exp_at_{c}']:+.2%} {r[f'verdict_at_{c}']}"
            for c in FEE_ROUND_TRIPS
        )
        lines.append(
            f"      all-in cost: {fees} | net exp is zero at {r['break_even']:.2%}"
        )
        for name in ("by_regime", "by_year"):
            cells = [
                f"{g}: {x['edge']:+.1%} (n {x['n_declustered']})"
                for g, x in json.loads(r[name]).items()
            ]
            lines.append(f"      {name}: " + ", ".join(cells))
    lines.append("display grouping only (families of nested survivors):")
    for fam in families(res["hypothesis"]):
        v = res.set_index("hypothesis").loc[fam, "verdict"]
        lines.append("  " + ", ".join(f"{h} {v[h]}" for h in fam))
    return lines


# --- after the holdout: what following each survivor would have felt like -----
#
# INFORMATION ONLY. The holdout is spent and is never re-judged: this reads its
# verdicts from the log, re-derives the SAME de-clustered trades, refuses to go
# on unless they reproduce the logged count and mean exactly, and then adds the
# numbers doc §8.3 asks for beside the hit rate (backtest/risk.py).

# All-in round-trip costs to describe at (researched 2026-09-24, see
# knowledge/context-vietnam.md): 0.16% = a zero-commission broker, which still
# passes on the exchange's 0.03% a side, + the 0.10% sale tax; 0.40% = the
# registered cost (0.15% a side); 0.60% = 0.25% a side, a full-service rate on
# small orders.
DESCRIBE_ROUND_TRIPS = (0.0016, 0.0040, 0.0060)
DESCRIBE_PATHS = 1000
DESCRIBE_SEED = 20260924
DESCRIBE_WINDOW = 60  # picks: about three months of daily proposals


def occurrences(v, h: Hypothesis, proto: dict, start, end) -> pd.DataFrame:
    """The de-clustered occurrences `evaluate` counts for h on [start, end], as
    rows (trade_date, symbol, ret, net, exit = the date it was sold): the same
    slice, the same outcome filter, eligibility and de-clustering, so their
    count and mean NET are evaluate's n_declustered and expectancy."""
    values = v.values
    d = pd.to_datetime(values["trade_date"])
    rows = values[(d >= pd.Timestamp(start)) & (d <= pd.Timestamp(end))]
    # Sessions are numbered over the whole slice, before any row is dropped,
    # exactly as in evaluate: de-clustering counts sessions, not rows.
    sessions = {x: i for i, x in enumerate(sorted(rows["trade_date"].unique()))}
    k = h.k
    rows = rows[rows[f"net_{k}"].notna()].reset_index(drop=True)
    hit = _hit(rows, h.query(proto))
    o = rows[hit.notna() & (hit == 1.0)]
    keep = declustered(o["trade_date"], o["symbol"], sessions, k)
    return (
        o[keep][["trade_date", "symbol", f"ret_{k}", f"net_{k}", f"known_on_{k}"]]
        .rename(columns={f"ret_{k}": "ret", f"net_{k}": "net", f"known_on_{k}": "exit"})
        .reset_index(drop=True)
    )


def describe_holdout(
    v,
    proto: dict,
    log: pd.DataFrame,
    tax: float,
    costs=DESCRIBE_ROUND_TRIPS,
    paths: int = DESCRIBE_PATHS,
    seed: int = DESCRIBE_SEED,
    window: int = DESCRIBE_WINDOW,
) -> pd.DataFrame:
    """One row per (holdout hypothesis, all-in cost): the logged verdict and
    backtest.risk.describe of its de-clustered holdout trades at that cost."""
    from . import risk

    reg = proto["registered"]
    sl = reg["slices"]["holdout"]
    logged = _latest(log, "holdout").set_index("hypothesis")
    if {str(b) for b in logged["build_id"]} != {str(v.manifest["build_id"])}:
        raise ValueError(
            f"the holdout ran on build {sorted(set(logged['build_id']))}, these rows "
            f"are build {v.manifest['build_id']}: not the trades it judged"
        )
    by_id = {h.id: h for h in vocabulary(proto)}
    floor = int(reg["holdout_rule"]["min_declustered"])
    out = []
    for hid, r in logged.iterrows():
        occ = occurrences(v, by_id[hid], proto, sl["start"], sl["end"])
        # The guard: these must be the very trades the holdout counted.
        if len(occ) != int(r["n_declustered"]) or not np.isclose(
            occ["net"].mean(), float(r["expectancy"]), rtol=1e-9, atol=1e-12
        ):
            raise ValueError(
                f"{hid}: {len(occ)} trades, mean {occ['net'].mean():+.6f}, but the "
                f"holdout logged {r['n_declustered']}, {float(r['expectancy']):+.6f}: "
                "not the trades it judged"
            )
        n = int(r["n_declustered"])
        verdict = (
            "NOT TESTABLE"
            if n < floor
            else ("ACCEPT" if str(r["survived"]) == "True" else "REJECT")
        )
        for cost in costs:
            fee = (cost - tax) / 2
            if fee < 0:
                raise ValueError(f"a round trip of {cost:.2%} is below the sale tax")
            net = net_return(occ["ret"], Costs(fee, tax, True))
            # Named, so an extreme trade can be checked against the prices.
            best, worst = occ.loc[net.idxmax()], occ.loc[net.idxmin()]
            out.append(
                {
                    "hypothesis": hid,
                    "verdict": verdict,
                    "cost": cost,
                    **risk.describe(
                        occ["trade_date"], net, occ["exit"], paths, seed, window
                    ),
                    "best_trade": f"{best['symbol']} {best['trade_date']}",
                    "worst_trade": f"{worst['symbol']} {worst['trade_date']}",
                }
            )
    return pd.DataFrame(out)


def describe_report(res: pd.DataFrame, proto: dict, registered: float) -> list[str]:
    sl = proto["registered"]["slices"]["holdout"]
    w = int(res["window"].iloc[0]) if len(res) else DESCRIBE_WINDOW
    others = ", ".join(
        f"{c:.2%}" for c in sorted(set(res["cost"])) if not np.isclose(c, registered)
    )
    lines = [
        f"HOLDOUT {sl['start']} .. {sl['end']}: WHAT FOLLOWING EACH SURVIVOR WOULD "
        "HAVE FELT LIKE | INFORMATION ONLY: every verdict is the logged one, "
        "nothing is re-judged",
        "UNITS: totals and drawdowns are in STAKES, not a share of an account. A "
        "stake is the money put on one signal day (e.g. 100M VND): -0.25 stakes "
        "= 25M lost. 'avg' figures are % of the money in the trade.",
        "avg per trade = the holdout's number (every trade counted once); avg per "
        "signal day = one stake a day, which is how the daily pick trades. They "
        "differ when many stocks fire on the same few days.",
        "basket = the day's stake split over every stock that fired; one pick = "
        f"the stake on ONE of them at random ({DESCRIBE_PATHS} seeded paths: the "
        "median path, and 'bad' = the worst 5% of paths); a losing streak counts "
        f"signal days in a row with net <= 0; '{w}-pick stretches below zero' = "
        f"the share of every {w} picks in a row that ended at or below zero.",
        f"all-in round-trip costs (both broker fees + the 0.10% sale tax): "
        f"{registered:.2%} registered; beside it {others} "
        "(0.16% = a zero-commission broker still passing on the exchange's 0.03% "
        "a side; 0.60% = 0.25% a side). A cheaper cost can LOWER the avg win: "
        "small losers become small winners. The holdout report's own fee lines "
        "use 0.10/0.25/0.40%.",
        "cash = the most stakes open at once, from the real exit dates (a day's "
        "stake is busy until its last exit; the T+2 wait for sale money is not "
        "included). No slippage beyond the costs.",
    ]
    order = {"ACCEPT": 0, "REJECT": 1, "NOT TESTABLE": 2}
    main = res[np.isclose(res["cost"], registered)]
    shown = main.assign(o=main["verdict"].map(order)).sort_values(
        ["o", "per_day"], ascending=[True, False]
    )

    def pct(x):
        return "n/a" if x != x else f"{x:+.2%}"

    def stakes(x):
        return "n/a" if x != x else f"{x:+.2f}"

    for _, r in shown.iterrows():
        lines += [
            f"  {r['hypothesis']}: {r['verdict']} | {r['trades']} trades on "
            f"{r['signal_days']} signal days | cash: up to {r['max_open']} stakes "
            "open at once",
            f"      at {registered:.2%}: avg per trade {pct(r['avg'])} | avg per "
            f"signal day {pct(r['per_day'])}",
            f"      per trade: avg win {pct(r['avg_win'])} | avg loss "
            f"{pct(r['avg_loss'])} | payoff {r['payoff']:.2f} | best "
            f"{pct(r['best'])} ({r['best_trade']}) | worst {pct(r['worst'])} "
            f"({r['worst_trade']})",
            f"      basket, in stakes: total {stakes(r['basket_total'])} | max "
            f"drawdown {stakes(r['basket_drawdown'])} | worst losing streak "
            f"{r['basket_streak']} signal days",
            f"      one pick, in stakes: total {stakes(r['pick_total_median'])} "
            f"(median path) | max drawdown {stakes(r['pick_drawdown_median'])} "
            f"median, {stakes(r['pick_drawdown_bad'])} bad | losing streak "
            f"{r['pick_streak_median']:.0f} median, {r['pick_streak_bad']:.0f} bad"
            + (
                ""
                if r["pick_losing_windows"] != r["pick_losing_windows"]
                else f" | {w}-pick stretches below zero {r['pick_losing_windows']:.0%}"
            ),
        ]
        for _, a in res[
            (res["hypothesis"] == r["hypothesis"])
            & ~np.isclose(res["cost"], registered)
        ].iterrows():
            lines.append(
                f"      at {a['cost']:.2%}: avg per trade {pct(a['avg'])}, per "
                f"signal day {pct(a['per_day'])} | basket total "
                f"{stakes(a['basket_total'])}, drawdown "
                f"{stakes(a['basket_drawdown'])} | one pick drawdown "
                f"{stakes(a['pick_drawdown_median'])} median, "
                f"{stakes(a['pick_drawdown_bad'])} bad"
            )
    return lines


def run_describe_holdout(
    conn,
    log_path: Path = LOG,
    proto_path: Path = PROTOCOL,
    reports: Path = REPORTS,
) -> Path:
    """Describe the holdout survivors (never re-judge them): the report goes to
    reports/holdout-<F>-describe.txt. Safe to repeat: it writes no log row."""
    from . import forward_returns as fr

    proto = load_protocol(proto_path)
    log = read_log(log_path)
    check_registration(proto, log)
    by_id = {h.id: h for h in vocabulary(proto)}
    hyps = [by_id[h] for h in _latest(log, "holdout")["hypothesis"]]
    v = _holdout_gated(conn, proto, hyps)
    c = fr.load_costs()
    res = describe_holdout(v, proto, log, c.sale_tax_rate)
    end = proto["registered"]["slices"]["holdout"]["end"]
    path = Path(reports) / f"holdout-{end}-describe.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(describe_report(res, proto, c.round_trip)) + "\n", encoding="utf-8"
    )
    return path


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

    disc, val = (
        _latest(log, x).set_index("hypothesis") for x in ("discover", "validate")
    )
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
    elif sys.argv[1] == "freeze":
        # Compute F from the stored returns; writing it into protocol.yaml is
        # a separate, committed step, before the holdout runs.
        from ..patterns import fingerprint as fpm
        from . import forward_returns as fr

        reg = load_protocol()["registered"]
        start = reg["slices"]["holdout"]["start"]
        with db.connect() as conn:
            build, _ = fpm.expected(conn)
        values = fr.load(build, start=start).values
        print(
            f"F = {freeze_date(values, start, reg['horizons'])} | last session "
            f"{max(values['trade_date'])} | build {build}"
        )
    elif sys.argv[1] == "holdout":
        with db.connect() as conn:
            print(run_holdout(conn).read_text())
    elif sys.argv[1] == "describe-holdout":
        with db.connect() as conn:
            print(run_describe_holdout(conn).read_text())
    else:
        with db.connect() as conn:
            path = run(conn, sys.argv[1])
        print((path / "report.txt").read_text())
