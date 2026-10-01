"""The audit sample is fixed without looking at any forward return."""

import pandas as pd
from scripts.audit_chart_patterns import sample


def test_stratified_sample_is_stable_and_excludes_later_events():
    rows = []
    for variant in (
        "double_top",
        "double_bottom",
        "symmetric_triangle",
        "ascending_triangle",
        "descending_triangle",
    ):
        for side in ("up", "down"):
            for i in range(3):
                rows.append(
                    {
                        "episode_id": f"{variant}:{side}:{i}",
                        "variant": variant,
                        "side": side,
                        "state": f"confirmed_{side}",
                        "candidate_on": "2020-01-01",
                        "signal_on": "2020-01-02",
                    }
                )
        rows.append(
            {
                "episode_id": f"{variant}:late",
                "variant": variant,
                "side": None,
                "state": "late_or_unobservable",
                "candidate_on": "2020-01-01",
                "signal_on": None,
            }
        )
    rows.append(
        {
            "episode_id": "future",
            "variant": "double_top",
            "side": "up",
            "state": "confirmed_up",
            "candidate_on": "2024-01-01",
            "signal_on": "2024-01-02",
        }
    )
    events = pd.DataFrame(rows)
    first = sample(events)
    shuffled = sample(events.sample(frac=1, random_state=14))
    assert len(first) == 25
    assert (
        first.groupby(["variant", "sample_kind", "side"], dropna=False).size().max()
        == 2
    )
    assert "future" not in first.episode_id.tolist()
    assert first.episode_id.tolist() == shuffled.episode_id.tolist()
