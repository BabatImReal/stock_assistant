"""Count v2 signal attrition on spent history, without using return magnitudes.

This is an accounting of model assumptions, not a simulated executable
portfolio. It uses the same point-in-time gate and period cutoffs as the v2
descriptive census; the return table is loaded, but no net/gross outcome is used.
"""

from __future__ import annotations

import pandas as pd

from vnstock_research import chart_research_v2 as chart
from vnstock_research.backtest import evidence
from vnstock_research.data import db, universe

PERIODS = (
    ("2012-2019", "2012-01-01", "2020-01-01"),
    ("2020-2023", "2020-01-01", "2024-01-01"),
)


def tally(events: pd.DataFrame, gated: pd.DataFrame, start: str, before: str):
    signals = events[
        events.signal_on.notna()
        & (pd.to_datetime(events.signal_on) >= pd.Timestamp(start))
        & (pd.to_datetime(events.signal_on) < pd.Timestamp(before))
    ].copy()
    signals["key_date"] = pd.to_datetime(signals.signal_on)
    known = gated[
        ["symbol", "trade_date", "reason_10", "deferred_10", "tier", *chart.SIGNALS]
    ].copy()
    known["key_date"] = pd.to_datetime(known.trade_date)
    joined = signals.merge(
        known.drop(columns="trade_date"),
        on=["symbol", "key_date"],
        how="left",
        validate="many_to_one",  # overlapping episodes share one stock-day
        indicator=True,
    )
    assert joined._merge.eq("both").all(), "event missing from gated stock-days"
    joined["flag"] = joined.apply(lambda row: row[f"{row.variant}__{row.side}"], axis=1)
    assert ~joined.flag.eq(0).any(), "confirmed event has no signal flag"
    observable = joined[joined.flag.eq(1)].copy()
    observable["reason"] = observable.reason_10.fillna("resolved")
    counts = observable.groupby(["side", "reason"]).size().rename("events")
    return {
        "confirmed": len(joined),
        "observable": len(observable),
        "unknown_history": int(joined.flag.isna().sum()),
        "liquid": int(observable.tier.notna().sum()),
        "resolved": int(observable.reason_10.isna().sum()),
        "resolved_deferred": int(
            observable.loc[observable.reason_10.isna(), "deferred_10"]
            .fillna(0)
            .gt(0)
            .sum()
        ),
        "reasons": counts,
    }


def main() -> None:
    with db.connect() as conn:
        events, flags, returns = chart.load_artifact(5)
        tiers = universe.tiers(conn, "2012-01-01", "2023-12-31")
    for label, start, before in PERIODS:
        gated = evidence.validated(flags, returns, tiers, before=before)
        result = tally(events, gated.values, start, before)
        print(label, {k: v for k, v in result.items() if k != "reasons"})
        print(result["reasons"].to_string())


if __name__ == "__main__":
    main()
