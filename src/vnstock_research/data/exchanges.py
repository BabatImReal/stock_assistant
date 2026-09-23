"""Which exchange a symbol was on, on each date, and whether that is KNOWN.

Per-exchange rules need the exchange in force on the date: HOSE +-7%, HNX
+-10%, UPCoM +-15% (config/rules/market_rules.yaml). `bar_raw.exchange` is the
exchange CafeF FILED a row under, which for some symbols is today's exchange
stamped on their whole history (DPG, and the vnstock backfills such as ACB).

Only DATED evidence counts (migration 009, decision 2026-09-23):
  1. cafef_transfer: both spans of a CafeF-documented transfer (G4 Class A).
     These are observed trading, filed per exchange, so they come first.
  2. kbs_listing: KBS says the symbol has been on its current exchange since
     listing_date. KBS answers of OTC or empty carry no usable date and give
     no row.
A date covered by neither is UNKNOWN. The filed exchange is borrowed so the
arithmetic can still run, and `exchange_unknown` is True. Every per-exchange
result on such a date is flagged and quarantined (features.base
`quarantine_flagged`), the same gate as sector labels.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import db

KBS_CACHE = db.REPO / "data" / "raw" / "kbs_listing"
EXCHANGES = {"HOSE": "HOSE", "HNX": "HNX", "UPCOM": "UPCOM", "UPCoM": "UPCOM"}
SPAN_COLUMNS = ["symbol", "exchange", "valid_from", "valid_to", "source"]


def kbs_rows(cache: Path = KBS_CACHE) -> pd.DataFrame:
    """One open-ended span per symbol whose KBS answer names a listed exchange
    and a parseable listing_date."""
    rows = []
    for f in sorted(cache.glob("*.json")):
        r = json.loads(f.read_text())
        ex = EXCHANGES.get(r.get("exchange", ""))
        day = pd.to_datetime(r.get("listing_date", ""), format="%d/%m/%Y",
                             errors="coerce")
        if ex and not pd.isna(day):
            rows.append((r["symbol"], ex, day.date(), None, "kbs_listing"))
    return pd.DataFrame(rows, columns=SPAN_COLUMNS)


def cafef_transfer_rows(conn) -> pd.DataFrame:
    """Every CafeF span of a symbol CafeF files under more than one exchange."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT symbol, exchange, valid_from, valid_to, 'cafef_transfer'
            FROM symbol_exchange
            WHERE source = 'cafef' AND symbol IN (
                SELECT symbol FROM symbol_exchange WHERE source = 'cafef'
                GROUP BY symbol HAVING count(DISTINCT exchange) > 1)
            """
        )
        return pd.DataFrame(cur.fetchall(), columns=SPAN_COLUMNS)


def rebuild(conn, cache: Path = KBS_CACHE) -> dict[str, int]:
    """Re-derive exchange_membership from its two sources, and commit."""
    spans = pd.concat([cafef_transfer_rows(conn), kbs_rows(cache)], ignore_index=True)
    spans = spans[spans["symbol"].str.fullmatch(r"[A-Z]{3}")]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE exchange_membership")
        cur.executemany(
            "INSERT INTO exchange_membership VALUES (%s,%s,%s,%s,%s)",
            [tuple(r) for r in spans.itertuples(index=False)],
        )
    conn.commit()
    return spans["source"].value_counts().to_dict()


def load(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(SPAN_COLUMNS)} FROM exchange_membership")
        return pd.DataFrame(cur.fetchall(), columns=SPAN_COLUMNS)


def resolve(spans: pd.DataFrame, symbol: str, dates, filed) -> pd.DataFrame:
    """The exchange on each date, and whether it is known (see the module doc).

    `filed` is the exchange the rows were filed under (bar_raw.exchange),
    borrowed where nothing is known, never trusted on its own.
    """
    d = pd.Index(pd.to_datetime(pd.Series(dates)).dt.date, name="trade_date")
    known = pd.Series(np.nan, index=d, dtype=object)
    own = spans[spans["symbol"] == symbol]
    for src in ("cafef_transfer", "kbs_listing"):  # observed trading first
        for r in own[own["source"] == src].itertuples():
            covers = (d >= r.valid_from) & (
                True if pd.isna(r.valid_to) else d <= r.valid_to
            )
            known = known.where(~(covers & known.isna().to_numpy()), r.exchange)
    borrowed = pd.Series(np.asarray(filed, dtype=object), index=d)
    return pd.DataFrame(
        {"exchange": known.fillna(borrowed), "exchange_unknown": known.isna()}
    )


# The same resolution in SQL, for the gate: a LATERAL join on bar_raw alias `r`
# yielding `xm.exchange` (NULL = unknown). cafef_transfer outranks kbs_listing.
RESOLVE_JOIN_SQL = """
LEFT JOIN LATERAL (
    SELECT m.exchange FROM exchange_membership m
    WHERE m.symbol = r.symbol AND r.trade_date >= m.valid_from
      AND (m.valid_to IS NULL OR r.trade_date <= m.valid_to)
    ORDER BY (m.source = 'cafef_transfer') DESC
    LIMIT 1
) xm ON true
"""
