"""Write a dated ICB industry snapshot (doc §5.4, migration 007).

ICB membership is only published as CURRENT. The only way to get point-in-time
membership is to record it ourselves, dated, again and again. This script
writes one snapshot per run date. Re-running on the same date is a no-op.

It also prints the rough cross-check against KBS's own taxonomy (decision
2026-09-23: KBS is a cross-check only, never a source). Because the taxonomies
differ, agreement is a floor, not a mismatch count. What matters is that the
groups the doc names (banks, securities, real estate) line up.

Run:  uv run python scripts/snapshot_industry.py [--dry-run]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd  # noqa: E402

from vnstock_research.data import db, sectors  # noqa: E402


def fetch_vci() -> pd.DataFrame:
    """One row per 3-letter symbol: ICB level 2 and 4 codes and names."""
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


def kbs_cross_check(snap: pd.DataFrame) -> None:
    from vnstock import Listing

    kbs = Listing(source="kbs").symbols_by_industries().drop_duplicates("symbol")
    m = kbs.merge(snap, on="symbol")
    modal = m.groupby("industry_name")["icb_l2"].agg(lambda s: s.value_counts().iloc[0])
    print(
        f"KBS cross-check: {len(m)} symbols in both; "
        f"{modal.sum() / len(m):.1%} share their KBS industry's modal ICB L2"
    )
    for name in ("Ngân hàng", "Chứng khoán", "Bất động sản"):
        g = m[m["industry_name"] == name]["icb_l2"]
        if len(g):
            print(f"  {name}: {g.value_counts().iloc[0]}/{len(g)} in one ICB L2 group")


def main() -> None:
    dry = "--dry-run" in sys.argv
    db.load_env()
    snap = fetch_vci()
    today = date.today()
    snap["sector"] = sectors.sector_id(snap["icb_l2"], snap["icb_l4"])
    print(
        f"VCI ICB: {len(snap):,} 3-letter symbols; "
        f"{snap['sector'].nunique()} sectors (ICB L2, steel split out)"
    )
    kbs_cross_check(snap)

    with db.connect() as conn:
        ours = {r[0] for r in conn.execute("SELECT symbol FROM symbol").fetchall()}
        active = {
            r[0]
            for r in conn.execute(
                "SELECT symbol FROM symbol WHERE is_active"
            ).fetchall()
        }
        have = set(snap["symbol"])
        print(
            f"coverage: {len(ours & have):,}/{len(ours):,} of our symbols; "
            f"{len(active & have):,}/{len(active):,} active"
        )
        if dry:
            print("dry run: nothing written")
            return
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO symbol_industry (symbol, snapshot_date, source, "
                "icb_l2, icb_l2_name, icb_l4, icb_l4_name) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                [
                    (
                        r.symbol,
                        today,
                        sectors.SOURCE,
                        r.icb_l2,
                        r.icb_l2_name,
                        r.icb_l4,
                        r.icb_l4_name,
                    )
                    for r in snap.itertuples()
                ],
            )
            cur.execute(
                "SELECT count(*) FROM symbol_industry "
                "WHERE snapshot_date = %s AND source = %s",
                (today, sectors.SOURCE),
            )
            (n,) = cur.fetchone()
        conn.commit()
        print(f"snapshot {today}: {n:,} rows stored")


if __name__ == "__main__":
    main()
