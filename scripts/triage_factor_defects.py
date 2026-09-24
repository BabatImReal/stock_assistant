"""G20: triage every adjusted-series jump on a factor-change day.

Runs the detector (data/checks.py `factor_triage`) over every symbol of the
current build through the same loader the fingerprint and the returns use
(features/bars.py), and reports how many candidates are legitimate
(resumption, first day on a new exchange) and how many are genuine defects.
Defects are what bars.load marks `factor_break`: every window across one is
blanked like a gap.

Run:  uv run python scripts/triage_factor_defects.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import checks, db  # noqa: E402
from vnstock_research.features import bars  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def main() -> None:
    out = [f"G20 factor-defect triage   {datetime.now():%Y-%m-%d %H:%M}"]
    rows = []
    with db.connect() as conn:
        build = bars.current_build(conn)
        symbols = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
                "AND trade_date >= '2012-01-01' ORDER BY 1",
                (build,),
            ).fetchall()
        ]
        for _, frame in bars.load_many(conn, symbols, build=build):
            label = checks.factor_triage(frame)
            hit = label.notna()
            if hit.any():
                rows.append(
                    frame.loc[hit, ["symbol", "trade_date"]].assign(
                        label=label[hit].to_numpy()
                    )
                )
    found = pd.concat(rows, ignore_index=True)
    out.append(
        f"build {build}: adjusted move > {checks.JUMP_LIMITS:g}x the daily "
        f"limit on a factor-change day: {len(found):,} stock-days on "
        f"{found['symbol'].nunique():,} symbols"
    )
    for label, n in found["label"].value_counts().items():
        syms = found.loc[found["label"] == label, "symbol"].nunique()
        out.append(f"  {label:<14}{n:>7,}  ({syms:,} symbols)")
    defects = found[found["label"] == "defect"]
    out.append(
        "genuine defects by year: "
        + ", ".join(
            f"{y}: {n}"
            for y, n in pd.to_datetime(defects["trade_date"])
            .dt.year.value_counts()
            .sort_index()
            .items()
        )
    )
    print("\n".join(out))
    path = REPO / "data" / "reports" / f"g20-triage-{datetime.now():%Y%m%d-%H%M}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"written to {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
