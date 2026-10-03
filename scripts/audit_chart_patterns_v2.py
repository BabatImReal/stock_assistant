"""Fixed, outcome-blind v2 chart roster and causal replay.

The loader opens only the v2 event table; neither sample selection nor chart
rendering reads forward returns. This audit cannot certify tradeability.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
from scripts.audit_chart_patterns import AUDIT_END, render, sample

from vnstock_research import chart_research_v2 as chart
from vnstock_research import store
from vnstock_research.data import db
from vnstock_research.features import bars

OUT = Path(__file__).resolve().parents[1] / "data" / "reports" / "chart_audit_v2"


def replay(selected: pd.DataFrame, conn) -> None:
    """Prove each selected event is unchanged when future bars are hidden."""
    for event in selected.itertuples(index=False):
        frame = bars.load(conn, event.symbol, build=5)
        endpoint = pd.Timestamp(
            event.signal_on if pd.notna(event.signal_on) else event.candidate_on
        )
        truncated = frame[pd.to_datetime(frame.trade_date) <= endpoint]
        found = chart.detect(truncated)
        same = found[found.episode_id == event.episode_id]
        assert len(same) == 1, event.episode_id
        actual = same.iloc[0]
        assert pd.Timestamp(actual.candidate_on) == pd.Timestamp(event.candidate_on)
        if pd.notna(event.signal_on):
            assert pd.Timestamp(actual.signal_on) == pd.Timestamp(event.signal_on)
            assert actual.side == event.side
        else:
            assert pd.isna(actual.signal_on)
            assert actual.state == event.state


def main() -> None:
    root = (
        store.PROCESSED
        / "chart_research_v2"
        / f"5_{chart.rules_hash()}_{chart.code_hash()}"
    )
    events, _ = store.load(
        root / "events", "chart v2 events", "5", chart._basis(5), end=AUDIT_END
    )
    selected = sample(events)
    assert len(selected) == 25, "the stratified v2 sample is incomplete"
    with db.connect() as conn:
        replay(selected, conn)
    for path in render(selected, OUT):
        print(path)
    digest = hashlib.sha256((OUT / "sample.csv").read_bytes()).hexdigest()
    print(f"sample SHA-256: {digest}")


if __name__ == "__main__":
    main()
