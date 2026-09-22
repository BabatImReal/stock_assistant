"""How many symbols are affected by exchange transfers (blocker G4)?

There are two distinct cases, and only one of them needs a backfill:

  Class A - CafeF kept both spans, split across two exchange files. ACG trades
            on UPCOM to 2022-09-27 and on HOSE from 2022-10-10. Nothing is
            missing; the two spans just need stitching into one history.

  Class B - CafeF dropped the pre-transfer span entirely. ACB exists only in the
            HOSE file from 2020-12-14, and its nine years on HNX are in no bulk
            file at all. These are the ones that need the vnstock backfill.

Class A is free to count: a symbol appearing in more than one exchange file.
Class B leaves no trace in CafeF - the evidence is simply absent - so it can
only be found by asking a source that has the missing years. For each candidate
we ask vnstock for a window ENDING just before the symbol's first CafeF date. If
that window has trading, the company was already listed and CafeF is missing it.

Resumable: every answer is cached, so an interrupted run costs nothing to redo.

Run:  uv run python scripts/count_exchange_transfers.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "cafef"
CACHE = REPO / "data" / "raw" / "transfer_check"
REPORTS = REPO / "data" / "reports"

# 1.1s ~ 55 requests/minute, just inside the 60/min the registered community
# tier allows. Unregistered is 20/min and aborts rather than backing off.
DELAY = 1.1
MIN_ROWS = 250  # ignore symbols with too little history to be worth repairing
FIRST_YEAR = 2009  # before this, "started late" is not informative


def load_env() -> None:
    """Read .env without adding a dependency for four lines of parsing."""
    env = REPO / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def cafef_spans() -> pd.DataFrame:
    day = sorted(RAW.glob("*/"))[-1]
    rows = []
    for exchange, pattern in (
        ("HOSE", "CafeF.HSX.Upto*.csv"),
        ("HNX", "CafeF.HNX.Upto*.csv"),
        ("UPCOM", "CafeF.UPCOM.Upto*.csv"),
    ):
        df = pd.read_csv(
            next(day.glob(pattern)), encoding="utf-8-sig", dtype={"<DTYYYYMMDD>": str}
        )
        df.columns = [c.strip().strip("<>").lower() for c in df.columns]
        df = df[df["ticker"].astype(str).str.fullmatch(r"[A-Z]{3}")]
        g = df.groupby("ticker").agg(
            first=("dtyyyymmdd", "min"),
            last=("dtyyyymmdd", "max"),
            n=("dtyyyymmdd", "size"),
        )
        g["exchange"] = exchange
        rows.append(g.reset_index())
    return pd.concat(rows, ignore_index=True)


def traded_before(symbol: str, before: pd.Timestamp) -> dict:
    """Did this symbol trade in the three years before its first CafeF date?"""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{symbol}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    from vnstock import Quote

    lo = (before - pd.DateOffset(years=3)).date()
    hi = (before - pd.Timedelta(days=1)).date()
    result: dict
    try:
        time.sleep(DELAY)
        df = Quote(source="vci", symbol=symbol).history(
            start=str(lo), end=str(hi), interval="1D"
        )
        if df is None or df.empty:
            result = {"symbol": symbol, "rows": 0, "earliest": None, "error": None}
        else:
            result = {
                "symbol": symbol,
                "rows": int(len(df)),
                "earliest": str(pd.to_datetime(df["time"]).min().date()),
                "error": None,
            }
    except Exception as e:  # noqa: BLE001 - a counting script reports, it does not raise
        result = {
            "symbol": symbol,
            "rows": 0,
            "earliest": None,
            "error": f"{type(e).__name__}: {str(e)[:120]}",
        }
    cache.write_text(json.dumps(result))
    return result


def main() -> None:
    load_env()
    key = os.environ.get("VNSTOCK_API_KEY", "").strip()
    print(f"VNSTOCK_API_KEY present: {'yes (60/min)' if key else 'no (20/min)'}")

    spans = cafef_spans()
    counts = spans["ticker"].value_counts()
    class_a = sorted(counts[counts > 1].index)
    print(f"3-letter symbols: {spans['ticker'].nunique():,}")
    print(f"Class A (CafeF kept both spans, needs stitching only): {len(class_a)}")

    # Candidates for class B: a late start, and enough history to be worth it.
    spans["first_dt"] = pd.to_datetime(spans["first"], format="%Y%m%d")
    cand = spans[
        (spans["first_dt"].dt.year >= FIRST_YEAR)
        & (spans["n"] >= MIN_ROWS)
        & (~spans["ticker"].isin(class_a))
    ].copy()
    # A symbol's earliest CafeF appearance is what we test against.
    cand = cand.sort_values("first_dt").drop_duplicates("ticker", keep="first")
    print(f"Class B candidates to check against vnstock: {len(cand):,}")

    results = []
    for i, row in enumerate(cand.itertuples(), 1):
        r = traded_before(row.ticker, row.first_dt)
        r.update(
            exchange=row.exchange,
            cafef_first=str(row.first_dt.date()),
            cafef_rows=row.n,
        )
        results.append(r)
        if i % 100 == 0:
            found = sum(1 for x in results if x["rows"] > 0)
            print(f"  {i}/{len(cand)} checked, {found} transfers so far", flush=True)

    res = pd.DataFrame(results)
    transfers = res[res["rows"] > 0].copy()
    errors = res[res["error"].notna()]

    print()
    print(f"Class B (pre-transfer history MISSING from CafeF): {len(transfers)}")
    print(f"  errors / unchecked: {len(errors)}")
    if not transfers.empty:
        transfers["missing_days"] = (
            pd.to_datetime(transfers["cafef_first"])
            - pd.to_datetime(transfers["earliest"])
        ).dt.days
        print(f"  by exchange: {transfers['exchange'].value_counts().to_dict()}")
        print("\n  worst gaps (most history missing):")
        for r in transfers.nlargest(15, "missing_days").itertuples():
            print(
                f"    {r.symbol:<5} {r.exchange:<6} CafeF starts {r.cafef_first}"
                f"  vnstock has from {r.earliest}"
                f"  ~{r.missing_days / 365:.1f} years missing"
            )

    REPORTS.mkdir(parents=True, exist_ok=True)
    res.to_csv(REPORTS / "g4-transfer-check.csv", index=False)
    pd.Series(class_a).to_csv(
        REPORTS / "g4-class-a-symbols.csv", index=False, header=["symbol"]
    )
    print(f"\nwritten to {(REPORTS / 'g4-transfer-check.csv').relative_to(REPO)}")


if __name__ == "__main__":
    main()
