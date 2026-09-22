"""Blocker G12: is CafeF's bulk volume already matched-only?

Doc §4.3 and CLAUDE.md make it non-negotiable that money flow uses MATCHED
volume (khop lenh) and never negotiated block volume (thoa thuan), because a
single pre-agreed deal can make a quiet day look like accumulation.

The Phase 3 probe established that no CafeF *bulk* file carries the split. But
that is not the same as the bulk volume being wrong. CafeF's per-stock history
page does publish both numbers, so the question can be settled by measurement
instead of by choosing an expensive workaround:

    for stock-days with a LARGE negotiated deal, does the bulk file's volume
    equal matched-only, or matched + deal?

Those days are the only ones where the two answers differ enough to tell apart,
which is why the test deliberately hunts for them rather than sampling at random.

If bulk == matched-only, G12 closes and the principle is already satisfied.
If bulk == matched + deal, a backfill of the split is needed and Ben sees the
plan before anything is built.

Run:  uv run python scripts/probe_matched_vs_deal.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "cafef"
OUT = REPO / "data" / "raw" / "cafef_pricehistory"
REPORTS = REPO / "data" / "reports"

# Note the host: s.cafef.vn 301-redirects here AND DROPS THE QUERY STRING, so a
# redirect-following client silently asks for nothing and gets
# "symbol is null or empty". Use the canonical URL directly.
API = "https://cafef.vn/du-lieu/ajax/pagenew/datahistory/pricehistory.ashx"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128"
DELAY = 2.0

# Liquid large caps, biased towards names that actually see block trades.
SYMBOLS = [
    "VNM",
    "HPG",
    "FPT",
    "SSI",
    "ACB",
    "VIC",
    "VHM",
    "STB",
    "MBB",
    "TCB",
    "VPB",
    "MSN",
    "SHB",
    "EIB",
    "NVL",
    "HDB",
]
PAGE_SIZE = 20  # the endpoint caps here regardless of what is asked for
MAX_PAGES = 4  # ~63 trading days is all it serves

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def fetch_history(symbol: str) -> pd.DataFrame:
    """All the per-stock history the endpoint will give for one symbol.

    Cached on disk: this is a probe, and re-running it should cost CafeF nothing.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / f"{symbol}.json"
    if cache.exists():
        rows = json.loads(cache.read_text())
    else:
        rows = []
        for page in range(1, MAX_PAGES + 1):
            time.sleep(DELAY)
            r = requests.get(
                API,
                params={
                    "Symbol": symbol,
                    "StartDate": "",
                    "EndDate": "",
                    "PageIndex": page,
                    "PageSize": PAGE_SIZE,
                },
                headers={"User-Agent": UA},
                timeout=60,
            )
            r.raise_for_status()
            chunk = (r.json().get("Data") or {}).get("Data") or []
            if not chunk:
                break
            rows += chunk
        cache.write_text(json.dumps(rows, ensure_ascii=False))

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["Ngay"], format="%d/%m/%Y").dt.date
    df["symbol"] = symbol
    return df.rename(
        columns={
            "KhoiLuongKhopLenh": "matched",
            "KLThoaThuan": "deal",
            "GiaDongCua": "close",
            "GiaDieuChinh": "adj_close",
        }
    )[["symbol", "date", "close", "adj_close", "matched", "deal"]]


def load_bulk() -> pd.DataFrame:
    """The bulk adjusted OHLCV rows already downloaded by the Phase 3 probe."""
    day = sorted(RAW.glob("*/"))[-1]
    frames = []
    for csv in day.glob("CafeF.*.Upto*.csv"):
        name = csv.name.upper()
        if any(tag in name for tag in ("CC_", "NN_", "RAW_", "INDEX")):
            continue
        df = pd.read_csv(csv, encoding="utf-8-sig", dtype={"<DTYYYYMMDD>": str})
        df.columns = [c.strip().strip("<>").lower() for c in df.columns]
        frames.append(df)
    bulk = pd.concat(frames, ignore_index=True)
    bulk["date"] = pd.to_datetime(bulk["dtyyyymmdd"], format="%Y%m%d").dt.date
    bulk["symbol"] = bulk["ticker"].astype(str).str.upper().str.strip()
    say(f"bulk file: {day.name}, {len(bulk):,} rows")
    return bulk[["symbol", "date", "close", "volume"]].rename(
        columns={"volume": "bulk_volume", "close": "bulk_close"}
    )


def check_nn_carries_the_split(big: pd.DataFrame) -> None:
    """Second question: do the bulk NN_ files already hold the split?

    The Phase 3 probe concluded no bulk file carried it, reading the AmiBroker
    headers at face value. That was wrong. Those headers are reused to carry
    different quantities, and lining the values up against the known matched and
    deal numbers from the per-stock page identifies them properly:

        NN_<High> = matched volume,  NN_<Low> = negotiated volume.

    If that holds across history, the split is available for the whole period
    from files we already download, and no scraping is needed at all.
    """
    say("")
    say("-- Do the bulk NN_ files already carry the split? --")
    day = sorted(RAW.glob("*/"))[-1]
    nn = pd.concat(
        [
            pd.read_csv(p, encoding="utf-8-sig", dtype={"<DTYYYYMMDD>": str})
            for p in day.glob("CafeF.NN_H*.Upto*.csv")
        ],
        ignore_index=True,
    )
    nn.columns = [c.strip().strip("<>").lower() for c in nn.columns]
    nn["date"] = pd.to_datetime(nn["dtyyyymmdd"], format="%Y%m%d").dt.date
    nn["symbol"] = nn["ticker"].astype(str).str.upper().str.strip()

    chk = big.merge(nn[["symbol", "date", "high", "low"]], on=["symbol", "date"])
    say(
        f"  NN_<Low>  == negotiated volume : "
        f"{(chk['low'] == chk['deal']).sum()}/{len(chk)}"
    )
    say(
        f"  NN_<High> == matched volume    : "
        f"{(chk['high'] == chk['matched']).sum()}/{len(chk)}"
    )

    # Alignment across history, and how complete the coverage is. Exactness where
    # a row exists is not the same as a row existing for every stock-day.
    ohlcv = pd.read_csv(
        day / "CafeF.HSX.Upto21.09.2026.csv",
        encoding="utf-8-sig",
        dtype={"<DTYYYYMMDD>": str},
    )
    ohlcv.columns = [c.strip().strip("<>").lower() for c in ohlcv.columns]
    ohlcv["yr"] = ohlcv["dtyyyymmdd"].str[:4]
    nn["yr"] = nn["dtyyyymmdd"].str[:4]
    j = ohlcv[["ticker", "dtyyyymmdd", "yr", "volume"]].merge(
        nn[["ticker", "dtyyyymmdd", "high", "low"]], on=["ticker", "dtyyyymmdd"]
    )
    say("  by year on HSX: alignment where a row exists, and row coverage")
    counts = ohlcv.groupby("yr").size()
    for yr in [str(y) for y in range(2012, 2027)]:
        d = j[j["yr"] == yr]
        if d.empty:
            continue
        say(
            f"    {yr}  NN_<High>==volume {(d['high'] == d['volume']).mean():6.1%}"
            f"   rows {len(d):>7,}/{counts.get(yr, 0):>7,}"
            f" = {len(d) / counts.get(yr, 1):5.0%}"
            f"   days with a deal {(d['low'] > 0).mean():5.1%}"
        )


def main() -> None:
    say("G12 test: is CafeF bulk volume matched-only?")
    say(f"{datetime.now():%Y-%m-%d %H:%M}")
    say("")

    bulk = load_bulk()

    per_stock = [f for s in SYMBOLS if not (f := fetch_history(s)).empty]
    hist = pd.concat(per_stock, ignore_index=True)
    say(
        f"per-stock history: {len(hist):,} rows, "
        f"{hist['date'].min()} -> {hist['date'].max()}"
    )

    m = hist.merge(bulk, on=["symbol", "date"], how="inner")
    m["matched_plus_deal"] = m["matched"] + m["deal"]
    m["deal_share"] = m["deal"] / m["matched_plus_deal"]
    say(f"overlapping stock-days: {len(m):,}")

    # The whole test rests on days where the two candidate answers are far apart.
    big = m[(m["deal"] > 0) & (m["deal_share"] >= 0.05)].copy()
    big = big.sort_values("deal_share", ascending=False).head(20)
    say(f"stock-days with a large negotiated deal (>=5% of total): {len(big)}")
    say("")

    if big.empty:
        say("NO large-deal days in the window -- test inconclusive, widen it.")
        return

    eq_matched = (big["bulk_volume"] == big["matched"]).sum()
    eq_total = (big["bulk_volume"] == big["matched_plus_deal"]).sum()

    say(
        f"{'symbol':<7}{'date':<12}{'bulk':>12}{'matched':>12}{'deal':>12}"
        f"{'m+d':>13}{'deal%':>8}  verdict"
    )
    for _, r in big.iterrows():
        if r["bulk_volume"] == r["matched"]:
            verdict = "MATCHED-ONLY"
        elif r["bulk_volume"] == r["matched_plus_deal"]:
            verdict = "matched+deal"
        else:
            verdict = "neither"
        say(
            f"{r['symbol']:<7}{str(r['date']):<12}{r['bulk_volume']:>12,.0f}"
            f"{r['matched']:>12,.0f}{r['deal']:>12,.0f}"
            f"{r['matched_plus_deal']:>13,.0f}{r['deal_share']:>7.1%}  {verdict}"
        )

    say("")
    say(f"bulk == matched-only   : {eq_matched}/{len(big)}")
    say(f"bulk == matched + deal : {eq_total}/{len(big)}")
    say("")
    if eq_matched == len(big):
        say("VERDICT: CafeF bulk volume IS matched-only (khop lenh).")
        say("G12 CLOSES -- doc §4.3 is already satisfied by the primary source.")
        say("No scraper and no backfill of the split are needed for volume.")
    elif eq_total == len(big):
        say("VERDICT: CafeF bulk volume INCLUDES negotiated deals.")
        say("G12 stays open -- a backfill of the split is required.")
    else:
        say("VERDICT: neither consistently. Investigate before relying on volume.")

    check_nn_carries_the_split(big)

    REPORTS.mkdir(parents=True, exist_ok=True)
    big.to_csv(REPORTS / "g12-large-deal-days.csv", index=False)
    (REPORTS / "g12-matched-vs-deal.txt").write_text("\n".join(out), encoding="utf-8")
    say(f"\nwritten to {(REPORTS / 'g12-matched-vs-deal.txt').relative_to(REPO)}")


if __name__ == "__main__":
    main()
