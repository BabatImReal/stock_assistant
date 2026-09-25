"""New-hypothesis batches: CANDIDATE GENERATION, not confirmation (doc §8.2).

The registered run (backtest/protocol.py) tested 1,554 hypotheses, and its
holdout is spent. A batch is a NEW set of hypotheses, defined by a written
rule over the measures we already have, registered in its own frozen block
(config/rules/protocol.yaml `batches`) BEFORE it runs, and run through
discover and validate on the registered slices with the same machinery:
`evaluate` (de-clustered occurrences, hit vs base rate, the date-block
bootstrap), Benjamini-Hochberg over the batch's own N, and the purged
year-by-year walk-forward.

What is different, and why a survivor is only a CANDIDATE:
  - the 2012-2023 slices were already looked at by the registered run, and
    the batch was designed after seeing it. The forward paper-trading ledger
    is the only clean test left, so a batch survivor goes there, if Ben
    chooses, and nowhere else;
  - the holdout is never run for a batch: this module has no path for it;
  - the fee is out of scope (Ben, 2026-09-24): hit = GROSS return > 0. The
    outcomes are read through `gross`, which puts the gross return where the
    engine reads net, so every statistic is gross. Net at the provisional
    cost is computed beside it as information only;
  - a batch writes ONLY research/hypothesis_log_batches.csv, tagged with the
    batch name and its hash. The original log, which the scan and the
    holdout description read, is never touched.

The batch `complements_1`: the registered context vocabulary made two-sided.
Every registered condition gains its exact complement (`complement`), and the
batch is every trigger x 1-2 conditions x horizon holding at least one
complement and never a condition with its own complement.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from .. import store
from ..patterns.fingerprint import _CONDITION
from .evidence import validated
from .protocol import (
    LOG,
    LOG_COLUMNS,
    OUT,
    REPORTS,
    _latest,
    _slice,
    benjamini_hochberg,
    evaluate,
    load_protocol,
    read_log,
    vocabulary,
    walk_forward,
)

BATCH_LOG = LOG.parent / "hypothesis_log_batches.csv"
BATCH_COLUMNS = ["batch", *LOG_COLUMNS, "gross", "net_expectancy"]
# The exact logical complement of each comparison (NaN stays unknown: query
# blanks a row whose value is unknown, whatever the operator).
NOT = {">=": "<", ">": "<=", "<=": ">", "<": ">=", "==": "!=", "!=": "=="}


def batch_hash(block: dict) -> str:
    from ..report.scan import block_hash

    return block_hash(block)


def complement(condition: dict) -> dict:
    """not_<condition>: the other side of the same comparison, same measure."""
    ((column, want),) = condition.items()
    text = str(want)
    m = _CONDITION.match(text) or _CONDITION.match("==" + text)
    return {column: f"{NOT[m[1]]}{m[2]}"}


@dataclass(frozen=True)
class BatchHypothesis:
    """Duck-types protocol.Hypothesis for `evaluate`: id, k, query(proto)."""

    trigger: str
    conditions: tuple  # condition NAMES, sorted
    k: int
    spec: tuple  # ((column, comparison), ...) of the conditions

    @property
    def id(self) -> str:
        return f"k{self.k}:{self.trigger}" + "".join(f"+{c}" for c in self.conditions)

    def query(self, proto: dict) -> dict:
        return {self.trigger: 1, **dict(self.spec)}


def conditions(proto: dict) -> dict:
    """The 16: every registered condition and its complement."""
    reg = proto["registered"]["conditions"]
    out = dict(reg)
    out.update({f"not_{name}": complement(c) for name, c in reg.items()})
    return out


def enumerate_batch(proto: dict, name: str) -> list[BatchHypothesis]:
    """The batch's rule, in a fixed order: every trigger x 1..max_conditions
    of the 16 x horizon, holding at least one complement and never a
    condition with its own complement. A batch registered with
    `rule: structural` has its own rule (`enumerate_structural`)."""
    block = proto["batches"][name]
    if block.get("rule") == "structural":
        return enumerate_structural(proto, block)
    reg = proto["registered"]
    table = conditions(proto)
    names = sorted(table)
    out = []
    for k in reg["horizons"]:
        for trigger in reg["triggers"]:
            for r in range(1, int(block["max_conditions"]) + 1):
                for combo in combinations(names, r):
                    if not any(c.startswith("not_") for c in combo):
                        continue  # registered already
                    if any(f"not_{c}" in combo for c in combo):
                        continue  # a condition with its own complement
                    spec = tuple(item for c in combo for item in table[c].items())
                    out.append(BatchHypothesis(trigger, combo, int(k), spec))
    return out


def enumerate_structural(proto: dict, block: dict) -> list[BatchHypothesis]:
    """Every trigger x exactly ONE structural condition x (no other
    condition, or ONE registered condition) x horizon."""
    reg = proto["registered"]
    new = block["structural_conditions"]
    table = {**reg["conditions"], **new}
    out = []
    for k in reg["horizons"]:
        for trigger in reg["triggers"]:
            for s in sorted(new):
                for partner in [None, *sorted(reg["conditions"])]:
                    combo = tuple(sorted(c for c in (s, partner) if c))
                    spec = tuple(item for c in combo for item in table[c].items())
                    out.append(BatchHypothesis(trigger, combo, int(k), spec))
    return out


def all_conditions(proto: dict, block: dict) -> dict:
    """Every condition a batch may read: the registered ones, plus the
    batch's own structural conditions."""
    return {
        **proto["registered"]["conditions"],
        **block.get("structural_conditions", {}),
    }


def batch_vocabulary(proto: dict, name: str) -> list[BatchHypothesis]:
    """The batch as registered: refuses a count other than the registered N,
    and any id the registered run already used."""
    block = proto["batches"][name]
    out = enumerate_batch(proto, name)
    if len(out) != int(block["n"]):
        raise ValueError(
            f"batch {name}: the rule gives {len(out)} hypotheses, registered "
            f"n = {block['n']}"
        )
    taken = {h.id for h in vocabulary(proto)} & {h.id for h in out}
    if taken:
        raise ValueError(f"batch {name} reuses registered ids, e.g. {min(taken)}")
    return out


# --- the batch log ------------------------------------------------------------


def read_batch_log(path: Path = BATCH_LOG) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=BATCH_COLUMNS)
    return pd.read_csv(path)


def check_frozen(proto: dict, name: str, log: pd.DataFrame) -> None:
    seen = set(log.loc[log["batch"] == name, "protocol"].dropna())
    now = batch_hash(proto["batches"][name])
    if seen and seen != {now}:
        raise ValueError(
            f"batch `{name}` changed after its first run (log {sorted(seen)}, now "
            f"{now}); register a NEW batch instead"
        )


def check_once(log: pd.DataFrame, name: str, slice_name: str) -> None:
    """Each slice runs ONCE per batch: a second look would be data re-used."""
    if ((log["batch"] == name) & (log["slice"] == slice_name)).any():
        raise ValueError(f"batch `{name}` has already run on {slice_name}")


def discover_survivors(log: pd.DataFrame, name: str, hyps) -> list:
    d = log[(log["batch"] == name) & (log["slice"] == "discover")]
    if d.empty:
        raise ValueError(f"batch `{name}` needs its discover run first")
    ok = set(d.loc[d["survived"].astype(str) == "True", "hypothesis"])
    return [h for h in hyps if h.id in ok]


def append(res: pd.DataFrame, name: str, slice_name: str, proto, build, path) -> str:
    run_at = datetime.now(UTC).isoformat(timespec="seconds")
    run_id = f"{name}:{slice_name}-{run_at}"
    entry = res.assign(
        batch=name,
        run_id=run_id,
        run_at=run_at,
        protocol=batch_hash(proto["batches"][name]),
        code=store.code_hash(("backtest", "data", "features", "patterns", "store.py")),
        build_id=build,
        slice=slice_name,
    )[BATCH_COLUMNS]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry.to_csv(path, mode="a", header=not path.exists(), index=False)
    return run_id


# --- the verdicts ---------------------------------------------------------------


def gross(rt):
    """The outcomes with the GROSS return where the engine reads net: every
    statistic downstream (hit, base rate, expectancy, p) is then gross."""
    ks = rt.manifest["horizons"]
    return dataclasses.replace(
        rt, values=rt.values.assign(**{f"net_{k}": rt.values[f"ret_{k}"] for k in ks})
    )


def discover_verdict(res: pd.DataFrame, block: dict) -> pd.Series:
    """BH at q over the batch's registered N, testable, and |edge| at least
    min_abs_edge (either sign: two-sided, label-free)."""
    rule = block["discover"]
    bh = benjamini_hochberg(res["p"], float(rule["fdr_q"]), m=int(block["n"]))
    big = res["edge"].abs() >= float(rule["min_abs_edge"])
    return pd.Series(bh, index=res.index) & res["testable"].astype(bool) & big


def holds(discover_edge, val: pd.DataFrame, block: dict) -> pd.Series:
    """Validate, as registered for the batch: the discover sign kept and a
    GROSS expectancy above the floor. No net figure gates anything."""
    rule = block["validate"]
    same = np.sign(val["edge"].to_numpy()) == np.sign(np.asarray(discover_edge, float))
    ok = (same if rule["same_sign"] else True) & (
        val["gross"] > float(rule["min_gross_expectancy"])
    ).to_numpy()
    return pd.Series(ok, index=val.index)


def candidates(val: pd.DataFrame) -> pd.DataFrame:
    """Paper-trading candidates: held on validate with a POSITIVE edge."""
    return val[val["survived"].astype(bool) & (val["edge"] > 0)]


def years_positive(walk: str) -> int:
    return sum(1 for _, e in json.loads(walk).values() if e == e and e > 0)


def stronger(c: pd.DataFrame, six: pd.DataFrame) -> pd.Series:
    """Materially stronger than the six (the registered display rule): a
    higher edge AND a higher gross expectancy than the best of the six, AND
    at least as many walk-forward years positive."""
    best_edge, best_gross = six["edge"].max(), six["gross"].max()
    best_years = six["walk_forward"].map(years_positive).max()
    return (
        (c["edge"] > best_edge)
        & (c["gross"] > best_gross)
        & (c["walk_forward"].map(years_positive) >= best_years)
    )


# --- running a slice ----------------------------------------------------------


def run(
    conn,
    name: str,
    slice_name: str,
    log_path: Path = BATCH_LOG,
    out: Path = OUT,
    reports: Path = REPORTS,
) -> Path:
    """Discover or validate for a batch, once each; never the holdout."""
    if slice_name not in ("discover", "validate"):
        raise ValueError(
            f"a batch runs discover or validate, not '{slice_name}': the holdout "
            "is spent, and new candidates go to the forward paper-trading ledger"
        )
    from ..data import universe
    from ..patterns import fingerprint as fpm
    from . import forward_returns as fr

    proto = load_protocol()
    block, reg = proto["batches"][name], proto["registered"]
    log = read_batch_log(log_path)
    check_frozen(proto, name, log)
    check_once(log, name, slice_name)
    hyps = batch_vocabulary(proto, name)
    if slice_name == "validate":
        hyps = discover_survivors(log, name, hyps)
    start, end, before = _slice(proto, slice_name)

    if block.get("featureset") == "structural":
        from .. import structural

        build, fs = structural.expected(conn)  # its own fingerprint, same build
    else:
        build, fs = fpm.expected(conn)
    columns = sorted(
        {h.trigger for h in hyps}
        | {c for x in all_conditions(proto, block).values() for c in x}
        | {reg["regime"]}
    )
    fp = fpm.load(build, fs, columns=columns, end=end)
    rt = fr.load(build, end=end)
    uni = universe.tiers(conn, "2012-01-01", end)
    v = validated(fp, gross(rt), uni, before=before)
    res = evaluate(v, hyps, proto, start, end)
    # Information only: net at the provisional cost, same occurrences.
    info = evaluate(
        validated(fp, rt, uni, before=before), hyps, proto, start, end, pvalues=False
    )
    res["net_expectancy"] = info["expectancy"].to_numpy()
    six = None
    if slice_name == "discover":
        res["survived"] = discover_verdict(res, block)
    else:
        d = log[(log["batch"] == name) & (log["slice"] == "discover")]
        res["discover_edge"] = (
            res["hypothesis"].map(d.set_index("hypothesis")["edge"]).to_numpy()
        )
        res["survived"] = holds(res["discover_edge"], res, block)
        years = range(int(reg["slices"]["discover"]["start"][:4]), int(end[:4]) + 1)
        gross_rt = gross(rt)
        res["walk_forward"] = walk_forward(fp, gross_rt, uni, hyps, proto, years)
        # The six holdout ACCEPTs on the SAME gross basis, for the comparison
        # (recomputed here; not a test, nothing is logged for them).
        six_h = [
            h for h in vocabulary(proto) if h.id in set(_accepted_ids(read_log(LOG)))
        ]
        fp6 = fpm.load(
            build,
            fs,
            columns=sorted(
                {h.trigger for h in six_h}
                | {c for x in reg["conditions"].values() for c in x}
                | {reg["regime"]}
            ),
            end=end,
        )
        six = evaluate(
            validated(fp6, gross_rt, uni, before=before), six_h, proto, start, end
        )
        six["walk_forward"] = walk_forward(fp6, gross_rt, uni, six_h, proto, years)
        for other in block.get("stronger_than", []):
            if other != "six":
                six = pd.concat(
                    [six, earlier_candidates(other, out)], ignore_index=True
                )

    run_id = append(res, name, slice_name, proto, build, log_path)
    d = Path(out) / run_id.replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    res.to_parquet(d / "results.parquet", index=False)
    path = Path(reports) / f"batch-{name}-{slice_name}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(report(res, name, slice_name, proto, v.manifest, run_id, six)) + "\n",
        encoding="utf-8",
    )
    return path


def earlier_candidates(name: str, out: Path = OUT) -> pd.DataFrame:
    """Another batch's paper-trading candidates, from its stored validate
    results (the same gross basis), labelled with the batch name."""
    runs = sorted(Path(out).glob(f"{name}_validate-*/results.parquet"))
    if not runs:
        raise ValueError(f"no stored validate results for batch `{name}`")
    c = candidates(pd.read_parquet(runs[-1]))
    return c.assign(hypothesis=f"{name}: " + c["hypothesis"])


def tested_ever(proto: dict, name: str, log_path: Path = BATCH_LOG) -> int:
    """Every hypothesis ever tested: the registered run's, plus the full N of
    every batch that has run (an untestable one still counts), this one
    included."""
    ran = set(read_batch_log(log_path)["batch"]) | {name}
    registered = len(set(read_log(LOG)["hypothesis"]))
    return registered + sum(int(proto["batches"][b]["n"]) for b in ran)


def _accepted_ids(log: pd.DataFrame) -> list:
    last = _latest(log, "holdout")
    return list(last.loc[last["survived"].astype(str) == "True", "hypothesis"])


def report(res, name, slice_name, proto, manifest, run_id, six=None) -> list[str]:
    block, reg = proto["batches"][name], proto["registered"]
    n = int(block["n"])
    total = tested_ever(proto, name)
    net = " | NET PROVISIONAL" if manifest["net_provisional"] else ""
    lines = [
        f"{run_id} | BATCH {name} (hash {batch_hash(block)}) | {slice_name} "
        f"{_slice(proto, slice_name)[:2]} | purged before {manifest['before']} | "
        f"batch N = {n} (hypotheses ever tested: {total})",
        "CANDIDATE GENERATION, NOT CONFIRMATION: these slices were already looked "
        "at by the registered run; a survivor is at best a paper-trading candidate",
        f"hit = GROSS return > 0 (fee out of scope); net at the provisional cost "
        f"is information only{net}; liquid on t; two-sided; date-block bootstrap "
        f"({reg['bootstrap']['block_sessions']} sessions x "
        f"{reg['bootstrap']['resamples']})",
        f"run here: {len(res)} | testable (>= {reg['min_declustered']} "
        f"de-clustered): {int(res['testable'].sum())} | suspicious: "
        f"{int(res['suspicious'].sum())}",
    ]
    if slice_name == "discover":
        rule = block["discover"]
        lines.append(
            f"passed discovery (BH q={rule['fdr_q']} over N = {n}, |edge| >= "
            f"{rule['min_abs_edge']:.0%}): {int(res['survived'].sum())} "
            f"({int((res['survived'] & (res['edge'] > 0)).sum())} positive, "
            f"{int((res['survived'] & (res['edge'] < 0)).sum())} negative)"
        )
        shown = res[res["survived"]]
    else:
        cand = candidates(res)
        lines.append(
            f"discover survivors run: {len(res)} | HELD (same sign, gross exp > 0): "
            f"{int(res['survived'].sum())} | PAPER-TRADING CANDIDATES (held, edge > "
            f"0): {len(cand)}"
        )
        shown = res
    for _, r in shown.sort_values("edge", ascending=False).iterrows():
        tail = "  SUSPICIOUS" if r["suspicious"] else ""
        if slice_name == "validate":
            verdict = "HELD" if r["survived"] else "failed"
            tail = (
                f" | discover {r['discover_edge']:+.1%} -> {verdict} | walk-forward "
                f"{years_positive(r['walk_forward'])}/"
                f"{len(json.loads(r['walk_forward']))} years positive{tail}"
            )
        lines.append(
            f"  [N={n}] {r['hypothesis']}: {r['n_declustered']} de-cl. (n "
            f"{r['n_raw']}) hit {r['hit_rate']:.1%} vs base {r['base_rate']:.1%} "
            f"edge {r['edge']:+.1%} gross {r['gross']:+.2%} (net "
            f"{r['net_expectancy']:+.2%} info) p {r['p']:.4f}{tail}"
        )
    if six is not None:
        cand = candidates(res)
        lines += [
            "THE BENCHMARK, same validate slice, same GROSS basis (the six holdout "
            "ACCEPTs recomputed, plus any earlier batch's candidates; nothing "
            "logged). The best of each, then every one:"
        ]
        for label, g in six.groupby(
            six["hypothesis"].str.extract(r"^(\w+): ")[0].fillna("six")
        ):
            lines.append(
                f"  best of {label}: edge {g['edge'].max():+.1%} | gross "
                f"{g['gross'].max():+.2%} | years positive "
                f"{g['walk_forward'].map(years_positive).max()}"
            )
        for _, r in six.sort_values("edge", ascending=False).head(12).iterrows():
            lines.append(
                f"  {r['hypothesis']}: edge {r['edge']:+.1%} gross {r['gross']:+.2%}"
                f" | walk-forward {years_positive(r['walk_forward'])}/"
                f"{len(json.loads(r['walk_forward']))} years positive"
            )
        s = stronger(cand, six) if len(cand) else pd.Series(dtype=bool)
        lines.append(
            "MATERIALLY STRONGER than the best of the benchmark (higher edge AND "
            "higher gross AND at least as many years positive): "
            + (", ".join(cand.loc[s, "hypothesis"]) if s.any() else "NONE")
        )
    new = block.get("structural_conditions", {})
    if new:
        keep = res[res["survived"].astype(bool)]
        if slice_name == "validate":
            keep = candidates(res)
        parts = keep["hypothesis"].str.split("+").str[1:]
        counts = {c: int(parts.map(lambda x, c=c: c in x).sum()) for c in sorted(new)}
        lines.append(
            "BY STRUCTURAL CONDITION ("
            + ("passed discovery" if slice_name == "discover" else "candidates")
            + "): "
            + ", ".join(f"{c} {n}" for c, n in counts.items())
        )
    return lines


if __name__ == "__main__":
    import sys

    from ..data import db

    with db.connect() as conn:
        print(run(conn, sys.argv[1], sys.argv[2]))
