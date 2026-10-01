"""Reproducible, outcome-blind visual audit of the first chart pilot.

Only the event manifest and adjusted bars through each candidate/signal date
are read. No forward-return table is opened. This is a diagnostic, not a new
signal or a performance test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from vnstock_research import chart_research as chart
from vnstock_research import store
from vnstock_research.data import db
from vnstock_research.features import bars as bar_data

AUDIT_END = "2023-12-31"  # earlier viewed years; do not inspect later outcomes
OUT = Path(__file__).resolve().parents[1] / "data" / "reports" / "chart_audit_v1"


def sample(events: pd.DataFrame) -> pd.DataFrame:
    """Two each per variant×break side, one rejected late case per variant."""
    prior = events[pd.to_datetime(events["candidate_on"]) <= AUDIT_END].copy()
    prior["selection_hash"] = prior["episode_id"].map(
        lambda value: hashlib.sha256(str(value).encode()).hexdigest()
    )
    confirmed = prior[prior["signal_on"].notna()].copy()
    confirmed["sample_kind"] = "confirmed"
    selected = (
        confirmed.sort_values("selection_hash")
        .groupby(["variant", "side"], sort=True)
        .head(2)
    )
    late = prior[prior["state"] == "late_or_unobservable"].copy()
    late["sample_kind"] = "late"
    selected = pd.concat(
        [selected, late.sort_values("selection_hash").groupby("variant").head(1)],
        ignore_index=True,
    )
    return selected.sort_values(["variant", "sample_kind", "side", "selection_hash"])


def _anchors(event, frame):
    dates = [pd.Timestamp(d) for d in json.loads(event.anchor_dates)]
    indexes = [
        int(frame.index[pd.to_datetime(frame.trade_date) == d][0]) for d in dates
    ]
    return indexes, frame.loc[indexes, "close"].to_numpy("float64")


def _boundary(axis, event, frame, anchors, prices, end):
    if event.variant.startswith("double_"):
        axis.axhline(prices[1], color="#8159a8", linestyle="--", linewidth=1)
        axis.axhline(
            max(prices[0], prices[2])
            if event.variant == "double_top"
            else min(prices[0], prices[2]),
            color="#8159a8",
            linestyle=":",
            linewidth=1,
        )
        return
    first_high = prices[0] > prices[1]
    for kind in (0, 1):
        chosen = [i for i in range(len(anchors)) if i % 2 == kind]
        x0, x1 = anchors[chosen[0]], anchors[chosen[-1]]
        y0, y1 = prices[chosen[0]], prices[chosen[-1]]
        xs = list(range(x0, end + 1))
        ys = [y0 * (y1 / y0) ** ((x - x0) / (x1 - x0)) for x in xs]
        axis.plot(
            xs,
            ys,
            color="#b44b55" if (kind == 0) == first_high else "#4272a6",
            linestyle="--",
            linewidth=1,
        )


def render(selected: pd.DataFrame, output: Path = OUT) -> list[Path]:
    # matplotlib already exists in this environment; this audit helper does
    # not add it to the research pipeline's runtime dependencies.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True, exist_ok=True)
    chosen = selected.drop(columns=["trade_date"], errors="ignore")
    chosen.to_csv(output / "sample.csv", index=False)
    paths = []
    with db.connect() as conn:
        for variant, rows in chosen.groupby("variant", sort=True):
            fig, axes = plt.subplots(2, 3, figsize=(17, 9), constrained_layout=True)
            for axis, event in zip(
                axes.flat, rows.itertuples(index=False), strict=False
            ):
                frame = bar_data.load(conn, event.symbol, build=5)
                date_index = pd.Index(pd.to_datetime(frame.trade_date))
                endpoint = pd.Timestamp(
                    event.signal_on if pd.notna(event.signal_on) else event.candidate_on
                )
                end = int(date_index.get_loc(endpoint))
                start = max(
                    0, int(date_index.get_loc(pd.Timestamp(event.formation_start))) - 10
                )
                anchors, prices = _anchors(event, frame)
                # No price after the recorded signal/candidate is shown.
                axis.plot(
                    range(start, end + 1),
                    frame.close.iloc[start : end + 1],
                    color="#222222",
                )
                axis.scatter(anchors, prices, color="#df9925", s=30, zorder=3)
                _boundary(axis, event, frame, anchors, prices, end)
                axis.axvline(
                    int(date_index.get_loc(pd.Timestamp(event.candidate_on))),
                    color="#4272a6",
                    alpha=0.6,
                )
                if pd.notna(event.signal_on):
                    axis.axvline(
                        end,
                        color="#38916b" if event.side == "up" else "#b44b55",
                        linewidth=2,
                    )
                axis.set_xlim(start, end + 1)
                axis.set_title(
                    f"{event.symbol} {event.sample_kind} {event.side or ''}\n"
                    f"{event.formation_start} → {endpoint.date()}",
                    fontsize=10,
                )
                axis.grid(alpha=0.2)
            for axis in list(axes.flat)[len(rows) :]:
                axis.set_visible(False)
            fig.suptitle(
                f"{variant} — closes only through event date; no returns", fontsize=14
            )
            path = output / f"{variant}.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            paths.append(path)
    return paths


def main() -> None:
    root = (
        store.PROCESSED
        / "chart_research"
        / f"5_{chart.rules_hash()}_{chart.code_hash()}"
    )
    basis = {
        "build_id": 5,
        "chart_rules": chart.rules_hash(),
        "chart_code": chart.code_hash(),
        "source_code": chart.source_code_hash(),
    }
    events, _ = store.load(root / "events", "chart events", "5", basis, end=AUDIT_END)
    selected = sample(events)
    assert len(selected) == 25, "the stratified audit sample is incomplete"
    for path in render(selected):
        print(path)


if __name__ == "__main__":
    main()
