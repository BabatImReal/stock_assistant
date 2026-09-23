"""Which sector each symbol belongs to, on each date (doc §5.4).

Source: vnstock VCI's ICB listing (decision 2026-09-23). KBS is only a rough
cross-check, printed by scripts/snapshot_industry.py.

THE SECTOR RULE: ICB level 2, with ONE documented exception.
  Level 2 "Basic resources" (1700) mixes steel with paper, wood and mining. The
  doc names steel as a group that moves together, so steel (level 4, 1757) is
  split out as its own sector. The rest of basic resources stays 1700. That is
  the only manual adjustment (Ben, 2026-09-23). Every other group is exactly
  ICB level 2, and none may be hand-adjusted.

THE DATING RULE, and why it is a hard gate:
  ICB is published as CURRENT membership only. Each fetch is stored as a dated
  snapshot (migration 007), and a date uses the latest snapshot on or before
  it. A date BEFORE a symbol's first snapshot can only borrow its earliest
  labels. That is look-ahead in the label: a company is classified by what it
  became. Those rows are marked `labels_current = True`, and every sector value
  built on them is flagged and quarantined from validated results
  (features/base.py `quarantine_flagged`). With the first snapshot on
  2026-09-23, all history before it is flagged. Dated membership accrues only
  from now on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASIC_RESOURCES = "1700"  # ICB level 2
STEEL = "1757"  # ICB level 4, "Thép và sản phẩm thép" (Iron & steel)

SOURCE = "vnstock:vci"


def sector_id(icb_l2: pd.Series, icb_l4: pd.Series) -> pd.Series:
    """ICB level 2, except steel split out of basic resources (the ONE exception)."""
    steel = (icb_l2 == BASIC_RESOURCES) & (icb_l4 == STEEL)
    return icb_l2.where(~steel, STEEL)


def load_labels(conn, source: str = SOURCE) -> pd.DataFrame:
    """Every snapshot: symbol, sector, sector_name, snapshot_date."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, snapshot_date, icb_l2, icb_l2_name, icb_l4, icb_l4_name "
            "FROM symbol_industry WHERE source = %s",
            (source,),
        )
        df = pd.DataFrame(
            cur.fetchall(),
            columns=[
                "symbol",
                "snapshot_date",
                "icb_l2",
                "icb_l2_name",
                "icb_l4",
                "icb_l4_name",
            ],
        )
    if df.empty:
        raise RuntimeError(
            "no industry snapshot; run scripts/snapshot_industry.py first"
        )
    df["sector"] = sector_id(df["icb_l2"], df["icb_l4"])
    df["sector_name"] = df["icb_l2_name"].where(
        df["sector"] != STEEL, df["icb_l4_name"]
    )
    return df[["symbol", "sector", "sector_name", "snapshot_date"]]


def panel(labels: pd.DataFrame, calendar) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(sector, labels_current): sessions x symbols.

    sector: the latest snapshot on or before each date; before a symbol's
      first snapshot, its earliest one (borrowed, so flagged).
    labels_current: True where the label was borrowed, i.e. the date is before
      the symbol's first snapshot. A symbol with no snapshot at all has no
      sector (NaN) and is simply not a member of anything.
    """
    cal = pd.Index(calendar, name="trade_date")
    wide = labels.pivot(index="snapshot_date", columns="symbol", values="sector")
    grid = wide.reindex(wide.index.union(cal)).sort_index()
    sector = grid.ffill().bfill().reindex(cal)
    first = labels.groupby("symbol")["snapshot_date"].min().reindex(sector.columns)
    current = pd.DataFrame(
        np.less.outer(cal.to_numpy(), first.to_numpy()),
        index=cal,
        columns=sector.columns,
    )
    return sector, current


def assign(symbol: str, dates, labels: pd.DataFrame) -> pd.DataFrame:
    """One symbol's sector and labels_current on each of `dates`."""
    own = labels[labels["symbol"] == symbol]
    if own.empty:
        return pd.DataFrame(
            {"sector": np.nan, "labels_current": True},
            index=pd.Index(dates, name="trade_date"),
        )
    sector, current = panel(own, dates)
    return pd.DataFrame({"sector": sector[symbol], "labels_current": current[symbol]})


def fetch_vci() -> pd.DataFrame:
    """Today's ICB membership from vnstock VCI: one row per 3-letter symbol,
    with level 2 and level 4 codes and names."""
    from vnstock import Listing

    raw = Listing(source="vci").symbols_by_industries()
    raw = raw[raw["symbol"].str.fullmatch(r"[A-Z]{3}")]
    out = {}
    for level in (2, 4):
        lv = raw[raw["icb_level"] == level].drop_duplicates("symbol")
        out[f"icb_l{level}"] = lv.set_index("symbol")["icb_code"].astype(str)
        out[f"icb_l{level}_name"] = lv.set_index("symbol")["icb_name"]
    df = pd.DataFrame(out).dropna()
    df.index.name = "symbol"
    return df.reset_index()


def write_snapshot(conn, snap: pd.DataFrame, day, source: str = SOURCE) -> int:
    """Store `snap` as the snapshot dated `day`; return that day's row count.

    Idempotent per day: re-running on the same date writes nothing new, so the
    nightly job can call it every run. The caller commits.
    """
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO symbol_industry (symbol, snapshot_date, source, "
            "icb_l2, icb_l2_name, icb_l4, icb_l4_name) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            [
                (r.symbol, day, source, r.icb_l2, r.icb_l2_name, r.icb_l4,
                 r.icb_l4_name)
                for r in snap.itertuples()
            ],
        )
        cur.execute(
            "SELECT count(*) FROM symbol_industry "
            "WHERE snapshot_date = %s AND source = %s",
            (day, source),
        )
        return cur.fetchone()[0]


def current_groups(labels: pd.DataFrame) -> pd.Series:
    """symbol -> sector from the LATEST snapshot, for the doc §7.1 small-sample
    fallback (this stock -> its sector -> whole market).

    NOTE: these are CURRENT labels. Pooling history by them classifies each
    company by what it is now (decision 2026-09-23). Allowed for the fallback,
    but every pooled statistic must say it pooled on current labels.
    """
    latest = labels.sort_values("snapshot_date").groupby("symbol").tail(1)
    return latest.set_index("symbol")["sector"]
