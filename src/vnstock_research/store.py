"""Storing a derived table: Parquet split by year, plus a manifest.

Shared by the fingerprint (patterns/fingerprint.py) and the forward returns
(backtest/forward_returns.py), so both refuse a stale table the same way. That
is the trading_day lesson: a stored derivative silently drifted from the data
it came from, and nothing noticed until a check compared the two.

The manifest records what the table was built from (the caller's `expect`
keys: the adjustment build, a hash of the code, and whatever else the table
depends on) plus every file's sha256. `load` refuses, loudly:
  - no table stored for these keys;
  - a manifest whose keys disagree with the caller's (a folder copied or
    renamed to look current is still judged by what it says it was built from);
  - a file changed since it was written.
The manifest is deleted FIRST on a rewrite and written LAST, so a rewrite
that dies half-way leaves nothing loadable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PKG = Path(__file__).resolve().parent
PROCESSED = PKG.parents[1] / "data" / "processed"
MANIFEST = "manifest.json"
KEYS = ["symbol", "trade_date"]


def code_hash(parts, pkg: Path = PKG) -> str:
    """sha256 over every .py file under `parts` (package-relative folders or
    files). A fixed rule whose parameters did not change would otherwise keep
    serving the values it computed before the fix."""
    h = hashlib.sha256()
    for part in parts:
        path = pkg / part
        for f in [path] if path.is_file() else sorted(path.rglob("*.py")):
            h.update(str(f.relative_to(pkg)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def files_hash(paths) -> str:
    """sha256 over config files (name and bytes), e.g. the market rules."""
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).name.encode())
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(values: pd.DataFrame, d: Path, manifest: dict) -> Path:
    """One Parquet file per year of `trade_date`, then the manifest LAST."""
    d.mkdir(parents=True, exist_ok=True)
    (d / MANIFEST).unlink(missing_ok=True)
    files = {}
    years = pd.to_datetime(values["trade_date"]).dt.year
    for year, part in values.groupby(years, sort=True):
        path = d / f"{year}.parquet"
        part.to_parquet(path, index=False)
        files[str(year)] = {"rows": len(part), "sha256": _sha(path)}
    manifest = {
        **manifest,
        "columns": list(values.columns),
        "rows": len(values),
        "symbols": int(values["symbol"].nunique()),
        "files": files,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (d / MANIFEST).write_text(json.dumps(manifest, indent=1, default=str))
    return d


def load(
    d: Path,
    what: str,
    label: str,
    expect: dict,
    columns=None,
    start=None,
    end=None,
) -> tuple[pd.DataFrame, dict]:
    """(values, manifest) of the table in `d`, sorted by symbol then date.

    `columns` narrows what is read. A column that has a flag in the manifest's
    `flag_for` ALWAYS brings its flag, so a flagged value can never be read
    without the flag that quarantines it.
    """
    if not (d / MANIFEST).exists():
        stored = sorted(p.parent.name for p in d.parent.glob(f"*/{MANIFEST}"))
        raise FileNotFoundError(
            f"no {what} for {label} (stored: {', '.join(stored) or 'none'}); "
            f"run {what}.build"
        )
    man = json.loads((d / MANIFEST).read_text())
    stale = [
        f"{key} stored {man.get(key)} != current {now}"
        for key, now in expect.items()
        if man.get(key) != now
    ]
    if stale:
        raise ValueError(f"stale {what} in {d.name}: {'; '.join(stale)}. Rebuild it.")

    cols = None
    if columns is not None:
        want = [c for c in columns if c not in KEYS]
        flags = man.get("flag_for", {})
        want = list(dict.fromkeys(want + [flags[c] for c in want if c in flags]))
        cols = KEYS + want

    lo = pd.Timestamp(start) if start is not None else None
    hi = pd.Timestamp(end) if end is not None else None
    parts = []
    for year, meta in man["files"].items():
        if (lo is not None and int(year) < lo.year) or (
            hi is not None and int(year) > hi.year
        ):
            continue
        path = d / f"{year}.parquet"
        if _sha(path) != meta["sha256"]:
            raise ValueError(
                f"{d.name}/{path.name} changed since it was written. Rebuild it."
            )
        parts.append(pd.read_parquet(path, columns=cols))
    values = (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(columns=cols or man["columns"])
    )
    dates = pd.to_datetime(values["trade_date"])
    keep = pd.Series(True, index=values.index)
    if lo is not None:
        keep &= dates >= lo
    if hi is not None:
        keep &= dates <= hi
    # Files are split by year; hand the rows back one stock's history at a time.
    values = values[keep].sort_values(KEYS, kind="stable").reset_index(drop=True)
    return values, man
