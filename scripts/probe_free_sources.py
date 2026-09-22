"""Phase 3 probe: find out what the free data sources actually give us.

Doc §7.5, "Data source decision (updated 2026-09-22)". SSI FastConnect is paused
because registration costs money, so the research phase runs on:

  PRIMARY    CafeF bulk files  (cafef.vn/du-lieu/du-lieu-download.chn)
  REFERENCE  vnstock free community tier, used only to verify CafeF

The point of a probe is to replace assumptions with facts BEFORE a schema is
designed. Published field lists and real files differ, so nothing here trusts a
documented column name: it reads what arrived and reports it.

What it answers:
  A. CafeF  - which files, what columns, how far back, how complete, which
              exchanges, any delisted symbols, the per-day adjustment factors,
              missing trading days, and whether matched vs negotiated volume
              (doc §4.3) exists anywhere in the bulk files.
  B. vnstock - which source, adjusted or unadjusted, and the same five symbols.
  C. Reconciliation - CafeF against vnstock, via the reusable functions in
              vnstock_research.data.reconcile.

Politeness: one request at a time, a delay between them, files cached on disk so
a re-run downloads nothing. CafeF is a free service doing us a favour.

Run:  uv run python scripts/probe_free_sources.py
"""

from __future__ import annotations

import io
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import reconcile  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "cafef"
REPORTS = REPO / "data" / "reports"
PAGE = "https://cafef.vn/du-lieu/du-lieu-download.chn"

# A real browser UA. Not a disguise — CafeF simply returns nothing useful to a
# bare urllib default, and identifying as a normal client is the polite default.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128"
DELAY = 2.0  # seconds between requests

SYMBOLS = ["VNM", "HPG", "FPT", "SSI", "ACB"]
START = "2012-01-01"

# The five "Upto" (full-history) files Ben asked for. The keys are roles, not
# file names: the names carry a date that changes daily, so they are discovered
# from the page rather than hard-coded (see discover_links).
WANTED = {
    "stocks_adjusted": r"CafeF\.SolieuGD\.Upto(\d{8})\.zip",
    "stocks_unadjusted": r"CafeF\.SolieuGD\.Raw\.Upto(\d{8})\.zip",
    "index": r"CafeF\.Index\.Upto(\d{8})\.zip",
    "ccnn_stocks": r"CafeF\.CCNN\.Upto(\d{8})\.zip",
    "ccnn_index": r"CafeF\.CCNN\.Index\.Upto(\d{8})\.zip",
}

out: list[str] = []


def say(line: str = "") -> None:
    """Print as we go and keep a copy, so the report is also written to disk."""
    print(line, flush=True)
    out.append(line)


def get(url: str, *, binary: bool = False):
    time.sleep(DELAY)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    return r.content if binary else r.text


# --------------------------------------------------------------------------
# A. CafeF
# --------------------------------------------------------------------------


def discover_links() -> tuple[str, dict[str, str]]:
    """Find the latest-date link for each wanted file by parsing the page.

    The date is never hard-coded: the page lists many days, and we take the most
    recent one that has ALL five files. Taking the newest date per file
    independently would risk mixing days, and a stock file from one day
    reconciled against an index file from another would produce phantom missing
    days.
    """
    html = get(PAGE)
    hrefs = re.findall(r'href="(https://[^"]+\.zip)"', html)

    by_date: dict[str, dict[str, str]] = {}
    for href in hrefs:
        name = href.rsplit("/", 1)[-1]
        for role, pattern in WANTED.items():
            if m := re.fullmatch(pattern, name):
                by_date.setdefault(m.group(1), {})[role] = href

    complete = {d: v for d, v in by_date.items() if len(v) == len(WANTED)}
    if not complete:
        raise SystemExit(f"No date on {PAGE} has all of {list(WANTED)}")

    # File dates are DDMMYYYY; sort by the real date, not the string.
    latest = max(complete, key=lambda d: datetime.strptime(d, "%d%m%Y"))
    return latest, complete[latest]


def fetch(role: str, url: str, day: Path) -> list[Path]:
    """Download one zip if we do not already have it, and unzip it."""
    day.mkdir(parents=True, exist_ok=True)
    marker = day / f".{role}.done"
    if marker.exists():
        say(f"  {role}: already downloaded, reusing")
    else:
        say(f"  {role}: downloading {url.rsplit('/', 1)[-1]} ...")
        blob = get(url, binary=True)
        (day / url.rsplit("/", 1)[-1]).write_bytes(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            z.extractall(day)
        marker.touch()
    return sorted(p for p in day.glob("*.csv") if role_of(p.name) == role)


def role_of(csv_name: str) -> str | None:
    """Map an extracted CSV back to the role it came from.

    CafeF's inner file names differ from the zip names (HSX/HNX/UPCOM split,
    CC_/NN_ prefixes), so this is pattern matching, not string slicing.
    """
    n = csv_name.upper()
    if n.startswith("CAFEF.CC_INDEX") or n.startswith("CAFEF.NN_INDEX"):
        return "ccnn_index"
    if n.startswith("CAFEF.CC") or n.startswith("CAFEF.NN"):
        return "ccnn_stocks"
    if "INDEX" in n:
        return "index"
    if ".RAW." in n or "RAW" in n:
        return "stocks_unadjusted"
    return "stocks_adjusted"


def read_csv(path: Path) -> pd.DataFrame:
    """Read a CafeF CSV into a normalised frame.

    The files are AmiBroker/MetaStock import format: a UTF-8 BOM, then headers
    wrapped in angle brackets (<Ticker>,<DTYYYYMMDD>,...). utf-8-sig strips the
    BOM; without it the first column name silently becomes '﻿<Ticker>' and
    every lookup on it fails in a confusing way.
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"<DTYYYYMMDD>": str})
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]
    return df


def describe_file(path: Path, df: pd.DataFrame) -> None:
    say(f"\n  FILE {path.name}  ({path.stat().st_size / 1e6:.1f} MB)")
    say(f"    columns : {list(df.columns)}")
    say(f"    rows    : {len(df):,}")
    if "dtyyyymmdd" in df:
        d = pd.to_datetime(df["dtyyyymmdd"], format="%Y%m%d", errors="coerce")
        say(f"    dates   : {d.min().date()} -> {d.max().date()}")
    if "ticker" in df:
        say(f"    symbols : {df['ticker'].nunique():,}")


def to_prices(df: pd.DataFrame, exchange: str | None = None) -> pd.DataFrame:
    """CafeF OHLCV frame -> the (symbol, date, open..volume) shape reconcile wants."""
    out_df = df.rename(columns={"ticker": "symbol", "dtyyyymmdd": "date"}).copy()
    out_df["date"] = pd.to_datetime(out_df["date"], format="%Y%m%d").dt.date
    out_df["symbol"] = out_df["symbol"].astype(str).str.upper().str.strip()
    if exchange:
        out_df["exchange"] = exchange
    return out_df


def exchange_of(csv_name: str) -> str:
    n = csv_name.upper()
    for tag in ("HSX", "HOSE", "HNX", "UPCOM"):
        if tag in n:
            return "HOSE" if tag in ("HSX", "HOSE") else tag
    return "?"


def section_a(day_dir: Path, links: dict[str, str]) -> dict[str, pd.DataFrame]:
    say("\n" + "=" * 78)
    say("A. CAFEF BULK FILES")
    say("=" * 78)

    frames: dict[str, list[pd.DataFrame]] = {}
    for role, url in links.items():
        say(f"\n{role}")
        for csv in fetch(role, url, day_dir):
            df = read_csv(csv)
            describe_file(csv, df)
            df["_file"] = csv.name
            df["_exchange"] = exchange_of(csv.name)
            frames.setdefault(role, []).append(df)

    return {k: pd.concat(v, ignore_index=True) for k, v in frames.items()}


def report_coverage(adj: pd.DataFrame) -> None:
    say("\n-- Coverage of the adjusted stock file --")
    p = to_prices(adj)
    say(f"  rows {len(p):,}   symbols {p['symbol'].nunique():,}")
    say(f"  dates {min(p['date'])} -> {max(p['date'])}")

    per_ex = p.groupby("_exchange")["symbol"].nunique().sort_values(ascending=False)
    say("  symbols per exchange:")
    for ex, n in per_ex.items():
        say(f"    {ex:<6} {n:,}")

    # Delisted candidates: a symbol whose last row is long before the file's last
    # date. This is evidence, not proof — a long suspension looks identical — but
    # it answers the question that matters for survivorship bias (blocker G11):
    # does this file contain anything that is no longer trading?
    last_day = max(p["date"])
    last_seen = p.groupby("symbol")["date"].max()
    for cutoff_days, label in ((365, "over a year"), (30, "over a month")):
        stale = last_seen[
            last_seen < (pd.Timestamp(last_day) - pd.Timedelta(days=cutoff_days)).date()
        ]
        say(f"  symbols last traded {label} ago: {len(stale):,}")
    oldest = last_seen.sort_values().head(8)
    say("  earliest-stopping symbols (delisted candidates):")
    for sym, d in oldest.items():
        say(f"    {sym:<8} last row {d}")


def report_adjustment(adj: pd.DataFrame, raw: pd.DataFrame) -> None:
    """adjusted close / unadjusted close per day = the corporate-action factor.

    This is what blocker G1 needs. The factor is a step function: flat between
    events, and it steps at each stock dividend or rights issue. Volume has to be
    divided by the same factor, which the doc never says (open-questions G1).
    """
    say("\n-- Adjustment factors (adjusted close / unadjusted close) --")
    a = to_prices(adj)[["symbol", "date", "close"]].rename(columns={"close": "adj"})
    u = to_prices(raw)[["symbol", "date", "close"]].rename(columns={"close": "unadj"})
    m = a.merge(u, on=["symbol", "date"])

    for sym in SYMBOLS:
        s = m[m["symbol"] == sym].sort_values("date")
        if s.empty:
            say(f"  {sym}: not found in one of the two files")
            continue
        s = s[s["unadj"] > 0].copy()
        s["factor"] = (s["adj"] / s["unadj"]).round(6)
        steps = s[s["factor"].ne(s["factor"].shift())].iloc[1:]  # drop first row
        say(
            f"  {sym}: {len(s):,} days, factor {s['factor'].min():.4f} .. "
            f"{s['factor'].max():.4f}, {len(steps)} changes"
        )
        for _, row in steps.tail(6).iterrows():
            say(f"      {row['date']}  factor -> {row['factor']:.6f}")


def report_missing_days(adj: pd.DataFrame, index: pd.DataFrame) -> None:
    """Trading days each symbol is missing, measured against the VN-Index calendar."""
    say("\n-- Missing trading days vs the VN-Index calendar (2012-01-01 onwards) --")
    idx = to_prices(index)
    vn = idx[idx["symbol"].str.contains("VNINDEX", na=False)]
    cutoff = pd.Timestamp(START).date()
    calendar = {d for d in vn["date"] if d >= cutoff}
    say(f"  VN-Index sessions since {START}: {len(calendar):,}")
    if calendar:
        say(f"  VN-Index range: {min(calendar)} -> {max(calendar)}")

    p = to_prices(adj)
    p = p[p["date"] >= cutoff]
    for sym in SYMBOLS:
        missing = reconcile.missing_trading_days(p, calendar, symbol=sym)
        s = p[p["symbol"] == sym]
        if s.empty:
            say(f"  {sym}: no rows")
            continue
        say(
            f"  {sym}: {len(s):,} rows, {min(s['date'])} -> {max(s['date'])}, "
            f"{len(missing)} missing sessions"
        )
        if missing:
            say(f"      first few: {[str(d) for d in missing[:6]]}")


def report_matched_vs_deal(frames: dict[str, pd.DataFrame]) -> None:
    """Does anything here separate matched (khớp lệnh) from negotiated (thỏa thuận)?

    This decides whether the money-flow layer (doc §4.3, a non-negotiable
    principle) has data behind it from the primary source.
    """
    say("\n-- Matched vs negotiated volume, and foreign flow --")
    for role, df in frames.items():
        say(f"  {role}: columns {list(df.columns)}")
    say("")
    say("  The CafeF bulk files use the AmiBroker import header")
    say("  (<Ticker>,<DTYYYYMMDD>,<Open>,<High>,<Low>,<Close>,<Volume>[,<OI>])")
    say("  for EVERY file, including the cung-cau/nuoc-ngoai ones, which reuse")
    say("  those column names to carry entirely different quantities. So the")
    say("  question cannot be answered from the header - only from the values.")


def probe_ccnn_semantics(frames: dict[str, pd.DataFrame], adj: pd.DataFrame) -> None:
    """Work out what the CC_ and NN_ columns actually hold, by comparing values.

    Nothing documents these files. The only honest way to name the columns is to
    line them up against a quantity we already know - the traded volume from the
    OHLCV file on the same symbol and day - and see which one matches.
    """
    say("\n-- What the cung-cau / nuoc-ngoai columns actually contain --")
    ccnn = frames.get("ccnn_stocks")
    if ccnn is None or ccnn.empty:
        say("  no ccnn_stocks data")
        return

    price = to_prices(adj)
    for kind in ("CC", "NN"):
        sub = ccnn[ccnn["_file"].str.upper().str.contains(f"CAFEF.{kind}")]
        if sub.empty:
            continue
        p = to_prices(sub)
        sample = p[p["symbol"] == "VNM"].sort_values("date").tail(3)
        say(f"\n  {kind}_ file, VNM, last 3 rows:")
        for _, r in sample.iterrows():
            say(
                f"    {r['date']}  open={r['open']:,.0f} high={r['high']:,.0f} "
                f"low={r['low']:,.0f} close={r['close']:,.0f} "
                f"volume={r['volume']:,.0f}"
                + (f" oi={r['oi']:,.0f}" if "oi" in r else "")
            )
        vol = price[(price["symbol"] == "VNM")][["date", "volume"]].rename(
            columns={"volume": "ohlcv_volume"}
        )
        j = sample.merge(vol, on="date", how="left")
        for _, r in j.iterrows():
            say(
                f"    {r['date']}  OHLCV volume for comparison = "
                f"{r['ohlcv_volume']:,.0f}"
            )


# --------------------------------------------------------------------------
# B. vnstock
# --------------------------------------------------------------------------


def chunks(start: str, end: str, *, years: int = 4) -> list[tuple[str, str]]:
    """Split a date range into windows short enough for the free tier.

    The community edition truncates a single daily request to the most recent
    8 years WITHOUT failing - it returns a short frame and a warning. That is the
    dangerous kind of limit, because the caller sees plausible data and concludes
    the history does not exist. 4-year windows stay well clear of it.
    """
    lo = pd.Timestamp(start)
    stop = pd.Timestamp(end)
    windows = []
    while lo < stop:
        hi = min(lo + pd.DateOffset(years=years) - pd.Timedelta(days=1), stop)
        windows.append((str(lo.date()), str(hi.date())))
        lo = hi + pd.Timedelta(days=1)
    return windows


def section_b() -> dict[str, pd.DataFrame]:
    say("\n" + "=" * 78)
    say("B. VNSTOCK (free community tier, reference source)")
    say("=" * 78)

    import os

    key = os.environ.get("VNSTOCK_API_KEY", "").strip()
    say(f"\n  VNSTOCK_API_KEY in environment: {'yes' if key else 'no (not required)'}")

    from vnstock import Quote

    say("  Quote(source=...) default is KBS; the docs do not state whether prices")
    say("  are adjusted, so that is determined below by comparison, not assumed.")

    # Probe each source with a SHORT window. Asking for the full range here
    # would trip the community tier's 8-year limiter, and once it has fired it
    # caps every later call in the same process - which silently turns the
    # chunked fetch below back into "only the last 8 years". Found the hard way.
    probe_start = str((pd.Timestamp.today() - pd.Timedelta(days=60)).date())
    data: dict[str, pd.DataFrame] = {}
    for src in ("vci", "kbs"):
        try:
            df = Quote(source=src, symbol="VNM").history(
                start=probe_start, end=str(pd.Timestamp.today().date()), interval="1D"
            )
            say(f"  source {src}: OK, {len(df):,} rows, columns {list(df.columns)}")
            data[f"probe_{src}"] = df
        except Exception as e:  # noqa: BLE001 - a probe reports failures, it does not raise
            say(f"  source {src}: FAILED {type(e).__name__}: {str(e)[:120]}")

    say("")
    say("  NOTE: the community edition caps daily OHLCV at 8 years, and the cap")
    say("  is STATEFUL: once a too-long request has fired it, every later call")
    say("  in the same process is truncated to the last 8 years - with no error,")
    say("  just a short frame. That reads as 'there is no history before 2018'.")
    say("  Chunked requests in a clean process reach 2011, so all fetches below")
    say("  use 4-year windows and nothing above asks for a long range.")

    source = "vci" if "probe_vci" in data else next(iter(data), None)
    if source is None:
        say("  no vnstock source worked; reconciliation will be skipped")
        return {}
    source = source.replace("probe_", "")
    say(f"\n  using source '{source}' for the five symbols")

    frames = {}
    today = str(pd.Timestamp.today().date())
    for sym in SYMBOLS:
        parts = []
        for lo, hi in chunks(START, today):
            # 4s, not 1s: UNREGISTERED ("Guest") access is 20 requests/minute,
            # not the 60/min the community tier gets. Exceeding it aborts the
            # run outright rather than backing off, so the delay is the cheap
            # insurance. Registering for a free VNSTOCK_API_KEY raises it to 60.
            time.sleep(4.0)
            try:
                parts.append(
                    Quote(source=source, symbol=sym).history(
                        start=lo, end=hi, interval="1D"
                    )
                )
            except Exception as e:  # noqa: BLE001
                say(f"    {sym} {lo}..{hi}: FAILED {type(e).__name__}: {str(e)[:90]}")
        if not parts:
            say(f"    {sym}: no data")
            continue
        df = reconcile.normalise(
            pd.concat(parts, ignore_index=True), symbol=sym, date_col="time"
        )
        frames[sym] = df
        say(f"    {sym}: {len(df):,} rows, {df['date'].min()} -> {df['date'].max()}")
    return frames


# --------------------------------------------------------------------------
# C. Reconciliation
# --------------------------------------------------------------------------


def section_c(
    adj: pd.DataFrame, raw: pd.DataFrame, vn: dict[str, pd.DataFrame]
) -> None:
    say("\n" + "=" * 78)
    say("C. RECONCILIATION: CafeF vs vnstock")
    say("=" * 78)
    if not vn:
        say("  skipped - no vnstock data")
        return

    ref = reconcile.normalise(pd.concat(vn.values(), ignore_index=True))
    cutoff = pd.Timestamp(START).date()

    for label, cafef in (("adjusted", adj), ("unadjusted", raw)):
        p = to_prices(cafef)
        p = p[p["symbol"].isin(SYMBOLS) & (p["date"] >= cutoff)]
        p = reconcile.normalise(p)

        say(f"\n-- CafeF {label} vs vnstock --")
        results = reconcile.reconcile(
            p, ref, left_name=f"cafef-{label}", right_name="vnstock"
        )
        for res in results:
            say("  " + res.summary_line())
        path = reconcile.write_report(
            results,
            REPORTS / f"reconcile-cafef-{label}-vs-vnstock.txt",
            title=f"CafeF {label} vs vnstock, {START} to today, {SYMBOLS}",
        )
        say(f"  report: {path.relative_to(REPO)}")

        # Per symbol, so a single bad symbol cannot hide behind four good ones.
        for sym in SYMBOLS:
            sub_l, sub_r = p[p["symbol"] == sym], ref[ref["symbol"] == sym]
            if sub_l.empty or sub_r.empty:
                continue
            r = reconcile.reconcile_column(
                sub_l, sub_r, "close", tolerance=reconcile.PRICE_TOLERANCE
            )
            say(f"    {sym:<5} close {r.matched:,}/{r.compared:,} = {r.match_rate:.2%}")


def main() -> None:
    say(f"Free-source probe, {datetime.now():%Y-%m-%d %H:%M}")
    say(f"raw files -> {RAW.relative_to(REPO)}")
    say(f"reports   -> {REPORTS.relative_to(REPO)}")

    date_tag, links = discover_links()
    say(f"\nLatest complete CafeF date on the page: {date_tag} (DDMMYYYY)")
    day_dir = RAW / datetime.strptime(date_tag, "%d%m%Y").strftime("%Y-%m-%d")

    frames = section_a(day_dir, links)
    adj, raw = frames["stocks_adjusted"], frames["stocks_unadjusted"]

    report_coverage(adj)
    report_adjustment(adj, raw)
    report_missing_days(adj, frames["index"])
    report_matched_vs_deal(frames)
    probe_ccnn_semantics(frames, adj)

    vn = section_b()
    section_c(adj, raw, vn)

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"probe-free-sources-{datetime.now():%Y%m%d-%H%M}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    say(f"\nFull probe log written to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
