"""Fetch each symbol's KBS listing_date: the date it joined its CURRENT exchange.

Exchange membership is only partly dated in our data (open-questions, "exchange
is the CURRENT exchange"). KBS `Company(symbol).overview()` carries
`listing_date` for the exchange a symbol is on now. Where that date equals the
symbol's first bar, the symbol never moved. Where it is later, the symbol joined
its current exchange on that date, and was somewhere else before
(DPG: HOSE from 2018-05-22).

Resumable: every answer, including "no data", is cached per symbol, so an
interrupted run costs nothing to redo. The cache feeds the DB table
`exchange_membership` (data/exchanges.py `load_kbs_cache`, migration 009).

Run:  uv run python scripts/fetch_listing_dates.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import db  # noqa: E402

CACHE = db.REPO / "data" / "raw" / "kbs_listing"
# 1.1 s is about 55 requests/minute, inside the 60/min the registered
# community tier allows (the same pacing as count_exchange_transfers.py).
DELAY = 1.1


def fetch(symbol: str) -> dict:
    from vnstock import Company

    try:
        o = Company(symbol=symbol, source="kbs").overview()
        if o is None or o.empty:
            return {"symbol": symbol, "error": "empty overview"}
        return {
            "symbol": symbol,
            "exchange": str(o["exchange"].iloc[0]),
            "listing_date": str(o["listing_date"].iloc[0]),
        }
    except Exception as e:  # noqa: BLE001 - "no data" is an answer, cached
        return {"symbol": symbol, "error": f"{type(e).__name__}: {e}"[:200]}


def main() -> None:
    db.load_env()
    CACHE.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn:
        symbols = [r[0] for r in conn.execute(
            "SELECT symbol FROM symbol ORDER BY symbol").fetchall()]
    todo = [s for s in symbols if not (CACHE / f"{s}.json").exists()]
    print(f"{len(symbols)} symbols; {len(todo)} to fetch", flush=True)
    for i, s in enumerate(todo, 1):
        (CACHE / f"{s}.json").write_text(json.dumps(fetch(s)))
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
        time.sleep(DELAY)
    print("done", flush=True)


if __name__ == "__main__":
    main()
