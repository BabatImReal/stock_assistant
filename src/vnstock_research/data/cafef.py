"""Reading CafeF's bulk files.

Everything specific to CafeF's format lives here, so the loader above it deals
in plain frames. Three things about these files are not obvious and are the
reason this module exists:

1. **UTF-8 BOM.** Read with `utf-8-sig` or the first column name silently
   becomes '\\ufeff<Ticker>' and every lookup on it fails confusingly.
2. **AmiBroker headers mean nothing in the CC_/NN_ files.** Every file carries
   `<Ticker>,<DTYYYYMMDD>,<Open>,<High>,<Low>,<Close>,<Volume>[,<OI>]`
   regardless of what it holds. In `NN_*`, `<High>` is matched volume and
   `<Low>` is negotiated volume -- established by matching values against
   CafeF's per-stock page, 20/20 exact, not by reading the header.
3. **Prices are in thousands of VND.**
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RAW = REPO / "data" / "raw" / "cafef"

# The research universe: 3-letter tickers only. CafeF's HOSE file has 2,535
# symbols but only 474 are stocks -- the rest are covered warrants (CACB2101).
TICKER_RE = re.compile(r"^[A-Z]{3}$")

EXCHANGE_FILES = {
    "HOSE": ("CafeF.HSX.Upto*.csv", "CafeF.RAW_HSX.Upto*.csv"),
    "HNX": ("CafeF.HNX.Upto*.csv", "CafeF.RAW_HNX.Upto*.csv"),
    "UPCOM": ("CafeF.UPCOM.Upto*.csv", "CafeF.RAW_UPCOM.Upto*.csv"),
}
NN_FILES = {
    "HOSE": "CafeF.NN_HSX.Upto*.csv",
    "HNX": "CafeF.NN_HNX.Upto*.csv",
    "UPCOM": "CafeF.NN_UPCOM.Upto*.csv",
}
INDEX_FILE = "CafeF.INDEX.Upto*.csv"
# The nightly EOD file: CafeF.INDEX.<dd.mm.yyyy>.csv (a digit, never "Upto").
DAILY_INDEX_FILE = "CafeF.INDEX.[0-9]*.csv"


def latest_dir() -> Path:
    """The most recent downloaded CafeF publication."""
    days = sorted(p for p in RAW.glob("*/") if p.is_dir())
    if not days:
        raise FileNotFoundError(
            f"No CafeF download found under {RAW}. "
            "Run: uv run python scripts/probe_free_sources.py"
        )
    return days[-1]


def read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"<DTYYYYMMDD>": str})
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]
    df["symbol"] = df["ticker"].astype(str).str.upper().str.strip()
    df["trade_date"] = pd.to_datetime(df["dtyyyymmdd"], format="%Y%m%d").dt.date
    return df.drop(columns=["ticker", "dtyyyymmdd"])


def _one(day: Path, pattern: str) -> Path:
    matches = sorted(day.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"{pattern} not found in {day}")
    return matches[0]


def stocks(day: Path) -> pd.DataFrame:
    """Unadjusted bars joined to their adjusted close, for every exchange.

    The unadjusted file is the base because it is the permanent record: it is
    what actually traded. The adjusted close rides along only so the factor can
    be computed from the pair.

    The two files do not contain identical row sets (the HNX pair differs by a
    few hundred rows), so the join is LEFT from raw: a raw row with no adjusted
    partner keeps its bar and gets no factor, which the loader reports rather
    than silently dropping.
    """
    frames = []
    for exchange, (adj_pat, raw_pat) in EXCHANGE_FILES.items():
        adj = read_csv(_one(day, adj_pat))[["symbol", "trade_date", "close"]]
        adj = adj.rename(columns={"close": "adj_close"})
        raw = read_csv(_one(day, raw_pat))

        raw = raw[raw["symbol"].str.match(TICKER_RE)]
        adj = adj[adj["symbol"].str.match(TICKER_RE)]

        df = raw.merge(adj, on=["symbol", "trade_date"], how="left")
        df["exchange"] = exchange
        df["source_file"] = _one(day, raw_pat).name
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    return out[
        [
            "symbol",
            "trade_date",
            "exchange",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adj_close",
            "source_file",
        ]
    ]


def negotiated(day: Path) -> pd.DataFrame:
    """Block-trade volume from NN_<Low>, with NN_<High> kept for verification.

    Only rows CafeF actually published are returned. A symbol-day with no row
    here means UNKNOWN, and the loader must not invent a zero for it: NN
    coverage falls to 46% of HSX stock-days in 2024.
    """
    frames = []
    for exchange, pattern in NN_FILES.items():
        df = read_csv(_one(day, pattern))
        df = df[df["symbol"].str.match(TICKER_RE)]
        df = df.rename(columns={"low": "deal_volume", "high": "matched_check"})
        df["exchange"] = exchange
        df["source_file"] = _one(day, pattern).name
        frames.append(
            df[["symbol", "trade_date", "deal_volume", "matched_check", "source_file"]]
        )
    return pd.concat(frames, ignore_index=True)


def index_bars(day: Path, pattern: str = INDEX_FILE) -> pd.DataFrame:
    """Index history, with weekend rows rejected at the door.

    The file carries rows dated Saturday 2026-02-07 and Sunday 2026-03-08 with
    entirely plausible values, on which no stock traded (blocker G14). They are
    dropped here rather than stored and filtered later, so nothing downstream
    can accidentally treat them as sessions.
    """
    df = read_csv(_one(day, pattern))
    weekday = pd.to_datetime(df["trade_date"]).dt.dayofweek
    df = df[weekday < 5]
    return df[["symbol", "trade_date", "open", "high", "low", "close", "volume"]]
