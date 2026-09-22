"""Compare the same market data from two sources and report where they disagree.

Why this exists (CLAUDE.md, non-negotiable principles; doc §7.5):

    Every dataset is reconciled against a second source before use. Mismatches
    beyond tolerance are flagged and excluded until explained.

Agreement between CafeF and vnstock does not prove either is *true* — both
ultimately derive from the same exchange feeds. What it catches is the class of
error that actually happens in practice: a truncated download, a mis-parsed
column, a missing trading day, a corporate action adjusted by one source and
not the other. Those are silent failures. A pattern measured on a price series
with one wrong adjustment will fire on a move that never happened, and no amount
of validation discipline downstream (doc §8) will notice.

Two callers are planned, and the functions here are shaped for both:

(a) **Sample check after the full download** — a handful of symbols across every
    year, to prove the history is sound before any statistic is computed.
(b) **Daily check after each nightly update** — every stock, one day, which must
    be cheap enough to run unattended and must fail loudly.

Both reduce to the same operation: align two frames on (symbol, date), compare
the columns that should agree, and report what does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

# --- Tolerances --------------------------------------------------------------
#
# These are choices, and like every threshold in this project they are written
# down rather than buried in a function (doc §3.5).
#
# PRICE_TOLERANCE = 0.5%. Both sources publish prices in thousands of VND
# rounded to 2 decimals, so on a 10.00 stock one tick of rounding is already
# 0.1%. Two sources computing adjustment factors independently accumulate
# slightly different rounding over years of stock dividends. 0.5% absorbs that
# while still catching what matters: a missed corporate action moves a price by
# whole percent, usually much more.
#
# VOLUME_TOLERANCE = 1%, but a volume mismatch means something different from a
# price mismatch. Sources genuinely disagree on what volume *is* — whether it
# includes negotiated block trades and odd lots (doc §4.3). That is a definition
# difference, not an error, and it shows up as a consistent ratio rather than as
# scattered noise. So volume differences are reported and their median ratio is
# surfaced, rather than being treated as automatic grounds for exclusion.
PRICE_TOLERANCE = 0.005
VOLUME_TOLERANCE = 0.01

KEY = ["symbol", "date"]


@dataclass
class ReconResult:
    """What one reconciliation run found. Kept plain so it is easy to report."""

    left_name: str
    right_name: str
    column: str
    tolerance: float
    compared: int = 0  # rows present in BOTH sources
    matched: int = 0  # ... and agreeing within tolerance
    mismatches: pd.DataFrame = field(default_factory=pd.DataFrame)
    left_only: pd.DataFrame = field(default_factory=pd.DataFrame)
    right_only: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def match_rate(self) -> float:
        # A run with nothing to compare is not a 100% match, it is a failure to
        # compare. Returning 0.0 keeps that from reading as success.
        return self.matched / self.compared if self.compared else 0.0

    @property
    def median_ratio(self) -> float | None:
        """Median left/right ratio over the rows that disagreed.

        A systematic difference (one source including block trades, say) puts
        this near a constant. Scattered errors leave it near 1.0 with a wide
        spread, which is the more worrying pattern.
        """
        if self.mismatches.empty or "ratio" not in self.mismatches:
            return None
        return float(self.mismatches["ratio"].median())

    def summary_line(self) -> str:
        pct = f"{self.match_rate:.2%}"
        extra = ""
        if (r := self.median_ratio) is not None:
            extra = f", median ratio of the mismatches {r:.4f}"
        return (
            f"{self.column}: {self.matched}/{self.compared} within "
            f"{self.tolerance:.2%} ({pct}){extra}; "
            f"{len(self.left_only)} days only in {self.left_name}, "
            f"{len(self.right_only)} only in {self.right_name}"
        )


def normalise(
    df: pd.DataFrame,
    *,
    symbol: str | None = None,
    date_col: str = "date",
    rename: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Put a source's frame into the shape everything here expects.

    Sources arrive in different shapes — CafeF uses <Ticker>/<DTYYYYMMDD> with a
    BOM, vnstock uses time/open/.../volume — and normalising once at the edge
    keeps every function below free of source-specific special cases.
    """
    out = df.rename(columns=rename or {}).copy()
    if symbol is not None:
        out["symbol"] = symbol
    if date_col != "date":
        out = out.rename(columns={date_col: "date"})
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    return out.drop_duplicates(subset=KEY).sort_values(KEY).reset_index(drop=True)


def reconcile_column(
    left: pd.DataFrame,
    right: pd.DataFrame,
    column: str,
    *,
    tolerance: float,
    left_name: str = "left",
    right_name: str = "right",
) -> ReconResult:
    """Compare one column of two normalised frames on (symbol, date).

    Relative difference, not absolute: a 100 VND gap means nothing on a 200,000
    VND stock and everything on a 3,000 VND one, and this market contains both.
    """
    lcols = [*KEY, column]
    rcols = [*KEY, column]
    merged = left[lcols].merge(
        right[rcols], on=KEY, how="outer", suffixes=("_l", "_r"), indicator=True
    )

    both = merged[merged["_merge"] == "both"].copy()
    lv, rv = both[f"{column}_l"], both[f"{column}_r"]

    # Guard the denominator. A zero on one side is not a rounding disagreement —
    # it is a missing value dressed up as a number (a suspended day, an empty
    # cell), so it is always a mismatch rather than a division by zero.
    denom = rv.abs()
    both["ratio"] = lv / rv.where(rv != 0)
    both["rel_diff"] = ((lv - rv).abs() / denom.where(denom != 0)).fillna(float("inf"))

    ok = both["rel_diff"] <= tolerance
    keep = [*KEY, f"{column}_l", f"{column}_r", "rel_diff", "ratio"]
    mismatches = both.loc[~ok, keep]

    return ReconResult(
        left_name=left_name,
        right_name=right_name,
        column=column,
        tolerance=tolerance,
        compared=len(both),
        matched=int(ok.sum()),
        mismatches=mismatches.sort_values("rel_diff", ascending=False).reset_index(
            drop=True
        ),
        left_only=merged.loc[merged["_merge"] == "left_only", KEY].reset_index(
            drop=True
        ),
        right_only=merged.loc[merged["_merge"] == "right_only", KEY].reset_index(
            drop=True
        ),
    )


def reconcile(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    left_name: str = "left",
    right_name: str = "right",
    price_columns: tuple[str, ...] = ("close",),
    volume_columns: tuple[str, ...] = ("volume",),
    price_tolerance: float = PRICE_TOLERANCE,
    volume_tolerance: float = VOLUME_TOLERANCE,
) -> list[ReconResult]:
    """Reconcile every column of interest. This is the entry point both callers use.

    Caller (a), the post-download sample check, passes several symbols and years.
    Caller (b), the nightly check, passes every symbol for a single date. Neither
    needs a different code path — only a different slice of data.
    """
    results = []
    for col in price_columns:
        if col in left and col in right:
            results.append(
                reconcile_column(
                    left,
                    right,
                    col,
                    tolerance=price_tolerance,
                    left_name=left_name,
                    right_name=right_name,
                )
            )
    for col in volume_columns:
        if col in left and col in right:
            results.append(
                reconcile_column(
                    left,
                    right,
                    col,
                    tolerance=volume_tolerance,
                    left_name=left_name,
                    right_name=right_name,
                )
            )
    return results


def sample_by_year(
    df: pd.DataFrame, *, per_year: int = 20, seed: int = 0
) -> pd.DataFrame:
    """Take a fixed sample of rows from every year present.

    For caller (a). Checking the whole history against a rate-limited reference
    source is not practical, and not necessary: errors of the kind this catches
    cluster in time (a bad download covers a period, an adjustment error starts
    at an event). Sampling every year is what makes sure no year goes unlooked-at
    — which matters because results are reported year by year anyway (doc §8.1,
    regime change).
    """
    if df.empty:
        return df
    years = pd.to_datetime(df["date"]).dt.year
    return (
        df.groupby(years, group_keys=False)
        .apply(lambda g: g.sample(min(per_year, len(g)), random_state=seed))
        .sort_values(KEY)
        .reset_index(drop=True)
    )


def missing_trading_days(
    df: pd.DataFrame, calendar: set[date], *, symbol: str
) -> list[date]:
    """Trading days the market was open but this symbol has no row for.

    The calendar comes from the index, which trades every session by definition.
    A gap is not automatically an error — a stock can be suspended, or not yet
    listed — so this reports rather than judges. What it protects against is the
    silent version: a pattern that spans a hole in the data is measuring a move
    that did not happen over the days it thinks it did.
    """
    have = set(df.loc[df["symbol"] == symbol.upper(), "date"])
    if not have:
        return []
    # Only days inside the symbol's own listed range; before it listed, absence
    # is expected and reporting it would bury the real gaps in noise.
    lo, hi = min(have), max(have)
    return sorted(d for d in calendar if lo <= d <= hi and d not in have)


def write_report(results: list[ReconResult], path: Path, *, title: str) -> Path:
    """Write a plain-text report and the mismatch rows beside it.

    Reports go to data/reports/, which is git-ignored: they are evidence about a
    particular download, not source code, and they will be regenerated nightly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [title, "=" * len(title), ""]
    for res in results:
        lines.append(res.summary_line())
        if not res.mismatches.empty:
            lines.append("  worst rows:")
            lines += [
                "    " + line
                for line in res.mismatches.head(10).to_string(index=False).splitlines()
            ]
        lines.append("")
        if not res.mismatches.empty:
            csv = path.with_name(f"{path.stem}-{res.column}-mismatches.csv")
            res.mismatches.to_csv(csv, index=False)
            lines.append(f"  full list: {csv.name}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
