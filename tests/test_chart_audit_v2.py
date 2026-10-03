"""A v2 visual roster must contribute cases not already shown in v1."""

import pandas as pd
from scripts.audit_chart_patterns import sample
from scripts.audit_chart_patterns_v2 import new_sample


def test_v2_sample_excludes_the_fixed_v1_roster():
    rows = []
    for side in ("up", "down"):
        for i in range(4):
            rows.append(
                {
                    "episode_id": f"double_top:{side}:{i}",
                    "variant": "double_top",
                    "side": side,
                    "state": f"confirmed_{side}",
                    "candidate_on": "2020-01-01",
                    "signal_on": "2020-01-02",
                }
            )
    for i in range(2):
        rows.append(
            {
                "episode_id": f"double_top:late:{i}",
                "variant": "double_top",
                "side": None,
                "state": "late_or_unobservable",
                "candidate_on": "2020-01-01",
                "signal_on": None,
            }
        )
    events = pd.DataFrame(rows)
    selected = new_sample(events, events)
    assert len(selected) == 5
    assert set(selected.episode_id).isdisjoint(sample(events).episode_id)
