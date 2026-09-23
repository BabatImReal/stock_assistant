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
arithmetic can still run, and `exchange_unknown` is True.

KBS listing_date is NOT always the date the symbol joined its current exchange:
for some it is the ORIGINAL listing date (measured 2026-09-23: 16 of the 95
CafeF-documented transfers with a KBS date carry a date years BEFORE the move;
HBC says UPCoM since 2006 but moved from HOSE in 2024). Two rules keep that from
dating pre-move history with today's exchange:
  A. A KBS span contradicted by CafeF's own filing (a CafeF row on/after
     listing_date under another exchange, not explained by a documented
     transfer) is DROPPED at rebuild. (MHL: filed HNX 2009-2023, KBS "UPCoM
     since 2009".)
  B. A vnstock BACKFILL row is never dated by KBS. It is pre-transfer by
     construction (G4 Class B = CafeF dropped the pre-transfer span), so a KBS
     date on or before it can only be the original listing date. (Found 3,136
     such rows on 17 symbols.)
Where CafeF transfer spans overlap (three stray one-day HOSE filings on
2015-09-01: PXL, VLF, VNA) the LONGER span wins.
What neither rule can catch: a transfer CafeF re-filed entirely under the new
exchange AND for which KBS reports the original date. The gate's price-limit
check on DATED rows is the tripwire for it (a move beyond the dated
exchange's limit). Every per-exchange
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
        day = pd.to_datetime(
            r.get("listing_date", ""), format="%d/%m/%Y", errors="coerce"
        )
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


# Rule A: KBS spans contradicted by CafeF's own filing.
CONTRADICTED_KBS_SQL = """
DELETE FROM exchange_membership k
WHERE k.source = 'kbs_listing' AND EXISTS (
    SELECT 1 FROM bar_raw r
    WHERE r.symbol = k.symbol AND r.source = 'cafef'
      AND r.trade_date >= k.valid_from AND r.exchange <> k.exchange
      AND NOT EXISTS (
          SELECT 1 FROM exchange_membership t
          WHERE t.symbol = k.symbol AND t.source = 'cafef_transfer'
            AND r.trade_date BETWEEN t.valid_from AND t.valid_to))
"""


def rebuild(conn, cache: Path = KBS_CACHE, commit: bool = True) -> dict[str, int]:
    """Re-derive exchange_membership from its two sources, drop KBS spans the
    CafeF filing contradicts (rule A), and commit (a test passes commit=False
    inside a rolled-back transaction)."""
    spans = pd.concat([cafef_transfer_rows(conn), kbs_rows(cache)], ignore_index=True)
    spans = spans[spans["symbol"].str.fullmatch(r"[A-Z]{3}")]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE exchange_membership")
        cur.executemany(
            "INSERT INTO exchange_membership VALUES (%s,%s,%s,%s,%s)",
            [tuple(r) for r in spans.itertuples(index=False)],
        )
        cur.execute(CONTRADICTED_KBS_SQL)
        dropped = cur.rowcount
    if commit:
        conn.commit()
    counts = spans["source"].value_counts().to_dict()
    counts["kbs_listing"] -= dropped
    counts["kbs_dropped_contradicted"] = dropped
    return counts


def load(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(SPAN_COLUMNS)} FROM exchange_membership")
        return pd.DataFrame(cur.fetchall(), columns=SPAN_COLUMNS)


def resolve(
    spans: pd.DataFrame, symbol: str, dates, filed, backfilled=None
) -> pd.DataFrame:
    """The exchange on each date, and whether it is known (see the module doc).

    `filed` is the exchange the rows were filed under (bar_raw.exchange),
    borrowed where nothing is known, never trusted on its own. `backfilled`
    marks vnstock backfill rows (bar_raw.source = 'vnstock'): never dated by
    KBS (rule B).
    """
    d = pd.Index(pd.to_datetime(pd.Series(dates)).dt.date, name="trade_date")
    known = pd.Series(np.nan, index=d, dtype=object)
    own = spans[spans["symbol"] == symbol].copy()
    # Observed trading first; among overlapping CafeF spans, the longest.
    own["_len"] = [
        (pd.Timestamp(t) - pd.Timestamp(f)).days if not pd.isna(t) else 10**6
        for f, t in zip(own["valid_from"], own["valid_to"], strict=True)
    ]
    bf = (
        np.zeros(len(d), bool)
        if backfilled is None
        else np.asarray(backfilled, dtype=bool)
    )
    for src in ("cafef_transfer", "kbs_listing"):
        for r in (
            own[own["source"] == src].sort_values("_len", ascending=False).itertuples()
        ):
            covers = (d >= r.valid_from) & (
                True if pd.isna(r.valid_to) else d <= r.valid_to
            )
            if src == "kbs_listing":
                covers = covers & ~bf
            known = known.where(~(covers & known.isna().to_numpy()), r.exchange)
    borrowed = pd.Series(np.asarray(filed, dtype=object), index=d)
    return pd.DataFrame(
        {"exchange": known.fillna(borrowed), "exchange_unknown": known.isna()}
    )


# The same resolution in SQL, for the gate: a LATERAL join on bar_raw alias `r`
# yielding `xm.exchange` (NULL = unknown). cafef_transfer outranks kbs_listing,
# the longer CafeF span wins an overlap, and a backfill row is never dated by
# KBS (rule B). Kept in step with `resolve` by a live test.
RESOLVE_JOIN_SQL = """
LEFT JOIN LATERAL (
    SELECT m.exchange FROM exchange_membership m
    WHERE m.symbol = r.symbol AND r.trade_date >= m.valid_from
      AND (m.valid_to IS NULL OR r.trade_date <= m.valid_to)
      AND NOT (m.source = 'kbs_listing' AND r.source = 'vnstock')
    ORDER BY (m.source = 'cafef_transfer') DESC,
             coalesce(m.valid_to - m.valid_from, 1000000) DESC
    LIMIT 1
) xm ON true
"""
