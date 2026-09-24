"""The layered fingerprint (doc §3.6): every stock-day described by every
enabled measure at once.

Real charts are layered: a hammer, a volume spike and a support level can all
fire on one day. So the unit of analysis is not "did pattern X fire" but the
whole row: one row per (symbol, trade_date), one column per enabled measure
(every pattern, anatomy numeric and feature), plus the `flag__` column of every
measure whose value can rest on a borrowed sector label.

What this module deliberately does NOT do:

- **It computes nothing itself.** Each symbol's row block is exactly what
  `features.compute()` returned for that symbol, stacked (`assemble`). Every
  guard -- no look-ahead, no window across a gap or an excluded day, matched
  volume only, NaN meaning unknown, the sector flags -- comes along because it
  is the same code path, not a second copy of it.
- **It never hand-types a column description.** `schema()` reads them from the
  registries: group (the module that registered it), type, doc section, the
  lookback evaluated with this feature set's own parameters, and the first
  paragraph of the measure's docstring.
- **It never matches on direction.** A pattern may carry its traditional
  bullish/bearish label, but only in the schema, for the report to show both
  sides (doc §3.6). The label is a hypothesis (doc §3), so it is not a column
  and `query` cannot read it.

STORAGE (P8): Parquet split by year under
data/processed/fingerprint/<build_id>_<featureset>/, plus manifest.json. The
manifest records the adjustment build, the FeatureSet fingerprint, a hash of
the code that computes measures, and each file's sha256. `load` refuses a
stored fingerprint that disagrees with any of them. That is the trading_day
lesson: a stored derivative silently drifted from the data it came from, and
nothing noticed until a check compared the two.

Encode / neighbours (the G5 analog search) are T6, not here.
"""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .. import store
from ..features.base import (
    FLAG,
    MARKET_REGISTRY,
    REGISTRY,
    SECTOR_REGISTRY,
    FeatureSet,
    boolean_from,
    compute,
    featureset,
    load_config,
)

PKG = Path(__file__).resolve().parents[1]
ROOT = store.PROCESSED / "fingerprint"
MANIFEST = store.MANIFEST
KEYS = store.KEYS

# The code a stored value depends on: the measures, their helpers (tick
# floors, universe, sector labels, exchanges), the bars loader and the storage
# code. A change to a rule that leaves its parameters alone does not change the
# FeatureSet fingerprint, so without this a fixed bug would keep serving the
# old values.
CODE_DIRS = ("data", "features", "patterns", "store.py")


def code_hash() -> str:
    return store.code_hash(CODE_DIRS, PKG)


# --- schema: generated from the registries ----------------------------------


def _registered(name: str):
    for registry, reg in (
        ("symbol", REGISTRY),
        ("market", MARKET_REGISTRY),
        ("sector", SECTOR_REGISTRY),
    ):
        if name in reg:
            return reg[name], registry
    raise KeyError(f"measure '{name}' is not registered")


def _description(fn) -> str:
    """The first paragraph of the measure's docstring, on one line."""
    first = (fn.__doc__ or "").strip().split("\n\n")[0]
    return " ".join(first.split())


def schema(fs: FeatureSet) -> pd.DataFrame:
    """One row per stored column (keys excluded), in stored order."""
    rows, flag_rows = [], []
    for name in fs.measures:
        m, registry = _registered(name)
        entry = {
            "column": name,
            "group": m.fn.__module__.rsplit(".", 1)[1],
            "registry": registry,
            "kind": m.kind,
            "doc_ref": m.doc_ref,
            "lookback": int(m.lookback(fs.params[name])),
            "reads_volume": m.reads_volume,
            "flagged": name in fs.flagged,
            "direction": m.direction,
            "description": _description(m.fn),
        }
        rows.append(entry)
        if name in fs.flagged:
            flag_rows.append(
                {
                    **entry,
                    "column": FLAG + name,
                    "kind": "flag",
                    "flagged": False,
                    "direction": None,
                    "description": f"True where {name} rests on a borrowed "
                    f"(pre-snapshot) label; the gate (backtest.evidence) "
                    f"blanks {name} there.",
                }
            )
    return pd.DataFrame(rows + flag_rows)


# --- build ------------------------------------------------------------------


def assemble(frames, config: dict, market=None, sector=None):
    """compute() on each symbol's bars, stacked. Returns (values, FeatureSet).

    Nothing is added to or changed in what compute() returned: the keys go in
    front, the columns are put in stored order. No fill, no normalisation
    across rows or symbols -- either would let one row see another.
    """
    parts, fs = [], None
    for bars in frames:
        values, fs = compute(bars, config, market=market, sector=sector)
        values.insert(0, "trade_date", bars["trade_date"].to_numpy())
        values.insert(0, "symbol", bars["symbol"].to_numpy())
        parts.append(values)
    order = KEYS + list(fs.measures) + [FLAG + n for n in fs.flagged]
    return pd.concat(parts, ignore_index=True)[order], fs


def write(
    values: pd.DataFrame, fs: FeatureSet, build_id: int, root: Path = ROOT
) -> Path:
    """One Parquet file per year, then the manifest LAST (store.write)."""
    manifest = {
        "build_id": build_id,
        "featureset": fs.fingerprint,
        "code": code_hash(),
        "measures": list(fs.measures),
        "params": fs.params,
        "flagged": list(fs.flagged),
        "flag_for": {n: FLAG + n for n in fs.flagged},
        "schema": schema(fs).to_dict("records"),
    }
    return store.write(values, root / f"{build_id}_{fs.fingerprint}", manifest)


def build(conn, root: Path = ROOT, start: str = "2012-01-01") -> Path:
    """The whole fingerprint for the current promoted build: every symbol."""
    from ..features import bars, breadth, market, sector

    build_id = bars.current_build(conn)
    frames = {
        "index": market.load_default(conn, start),
        "breadth": breadth.load(conn, start, build=build_id),
    }
    sec = sector.load(conn, start, build=build_id)
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
            "AND trade_date >= %s ORDER BY 1",
            (build_id, start),
        ).fetchall()
    ]
    # ponytail: ~20 min single-threaded, and compute() redoes the market and
    # sector values per symbol (~0.12 s of ~0.7 s each). Parallelise, or
    # precompute them once, if a rebuild ever becomes a nightly step.
    values, fs = assemble(
        (f for _, f in bars.load_many(conn, symbols, start=start, build=build_id)),
        load_config(),
        frames,
        sec,
    )
    return write(values, fs, build_id, root)


# --- load -------------------------------------------------------------------


@dataclass(frozen=True)
class Fingerprint:
    """A stored fingerprint as loaded. EXPLORATORY: flagged values are still
    in `values`, next to their flag columns. Validated statistics must go
    through the gate, `backtest.evidence.validated()`."""

    values: pd.DataFrame
    schema: pd.DataFrame
    manifest: dict


def expected(conn, config: dict | None = None) -> tuple[int, FeatureSet]:
    """What a fingerprint must have been built from to be current NOW: the
    promoted build and the FeatureSet of today's config and labels."""
    from ..data import sectors
    from ..features import bars, sector

    basis = sector.basis(sectors.load_labels(conn))
    return bars.current_build(conn), featureset(config or load_config(), basis)


def load(
    build_id: int,
    fs: FeatureSet,
    *,
    root: Path = ROOT,
    columns=None,
    start=None,
    end=None,
) -> Fingerprint:
    """The stored fingerprint for exactly this build and feature set.

    Usually `load(*expected(conn))`. Refuses, loudly, anything stale: no stored
    fingerprint for this pair, a manifest that disagrees with it or with the
    current code, or a file changed since it was written.

    `columns` narrows what is read; the flag column of every flagged measure
    asked for is ALWAYS read with it, so the gate can never be handed a
    flagged value without its flag.
    """
    values, man = store.load(
        root / f"{build_id}_{fs.fingerprint}",
        "fingerprint",
        f"build {build_id}, feature set {fs.fingerprint}",
        {"build_id": build_id, "featureset": fs.fingerprint, "code": code_hash()},
        columns,
        start,
        end,
    )
    return Fingerprint(values, pd.DataFrame(man["schema"]), man)


# --- query: exact combinations ----------------------------------------------

_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}
_CONDITION = re.compile(r"^\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass(frozen=True)
class Match:
    hit: pd.Series  # 1.0 all conditions hold, 0.0 judged and not, NaN unknown
    occurrences: int  # rows where the combination holds
    judged: int  # rows where every condition could be evaluated
    per_symbol: pd.Series  # occurrences by symbol (the §7.1 fallback floor)


def query(fp, conditions: dict) -> Match:
    """Rows where EVERY condition holds, with occurrence counts.

    A condition is a number (equality: `{"hammer_shape": 1}`) or a comparison
    with a FIXED number (`{"rvol": ">=1.5"}`). Each row is compared with the
    constant only, never with other rows: point in time by construction. A
    threshold derived from the data (a full-history percentile) is look-ahead,
    so anything but a fixed number is refused.

    Unknown never counts as false: a row where any condition's value is NaN is
    NaN in `hit` and outside `judged`, so it cannot sit in the denominator of
    a rate as a "did not fire".
    """
    values = fp.values
    cond = pd.Series(True, index=values.index)
    inputs = []
    for name, want in conditions.items():
        text = str(want)
        m = _CONDITION.match(text) or _CONDITION.match("==" + text)
        if m is None:
            raise ValueError(
                f"'{name}': {text!r} is not a comparison with a fixed number"
            )
        col = values[name]
        cond &= _OPS[m[1]](col, float(m[2]))
        inputs.append(col)
    hit = boolean_from(cond, *inputs)
    return Match(
        hit=hit,
        occurrences=int(hit.sum()),
        judged=int(hit.notna().sum()),
        per_symbol=hit.groupby(values["symbol"]).sum().astype("int64"),
    )


if __name__ == "__main__":
    from ..data import db

    with db.connect() as conn:
        print(build(conn))
