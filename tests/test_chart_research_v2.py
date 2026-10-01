"""V2 must reject out-of-wall formation paths before looking at returns."""

import numpy as np
import pandas as pd

from vnstock_research import chart_research as v1
from vnstock_research import chart_research_v2 as v2

from ._helpers import frame
from .test_chart_research import shaped


def test_formation_containment_rejects_a_candidate_v1_would_keep(monkeypatch):
    cfg = v1.rules()
    cfg["pivot_separation"] = 1
    close = np.full(20, 9.0)
    close[[2, 6, 10]] = 10.0
    close[[4, 8]] = 8.0
    close[5] = 11.0  # outside the eventual upper wall, before last anchor
    bars = frame(n=len(close), close=close)
    pivots = {
        4: ("high", 2, 10.0),
        6: ("low", 4, 8.0),
        8: ("high", 6, 10.0),
        10: ("low", 8, 8.0),
        12: ("high", 10, 10.0),
    }

    def candidate(known, config):
        if len(known) < 5:
            return None
        return {
            "variant": "symmetric_triangle",
            "family": "triangle",
            "anchors": tuple(known[-5:]),
            "start": 2,
            "end": 10,
            "expiry": 20,
            "upper": lambda i: 10.0,
            "lower": lambda i: 8.0,
            "prior_trend": "not_required",
        }

    monkeypatch.setattr(v1, "_pivot", lambda prices, t, radius: pivots.get(t))
    monkeypatch.setattr(v1, "_level_candidate", lambda *args: None)
    monkeypatch.setattr(v1, "_triangle_candidate", candidate)
    assert len(v1.detect(bars, cfg)) == 1
    assert v2.detect(bars, cfg).empty


def long_double_bottom():
    bars = shaped(
        [
            (0, 105),
            (130, 105),
            (140, 95),
            (150, 110),
            (164, 95.5),
            (169, 99),
            (172, 112),
            (199, 115),
        ],
        n=200,
    )
    for name in ("raw_open", "raw_high", "raw_low", "raw_close"):
        bars[name] = bars[name[4:]]
    bars["date_shifted"] = False
    bars["exchange_unknown"] = False
    return bars


def test_contained_signal_is_one_hot_and_early_history_is_unknown():
    bars = long_double_bottom()
    episodes = v2.detect(bars)
    hit = episodes[(episodes.variant == "double_bottom") & episodes.signal_on.notna()]
    assert len(hit) == 1
    assert hit.iloc[0]["side"] == "up"
    signal = v2.signal_frame(bars, episodes)
    assert pd.isna(signal["double_bottom__up"].iloc[123])
    assert signal["double_bottom__up"].iloc[172] == 1.0
    assert signal["double_bottom__down"].iloc[172] == 0.0
    assert (
        v2.rules()["registered_trial_count"] == len(v2.SIGNALS) * len(v2.HORIZONS) == 40
    )


def test_v2_artifact_reuses_v1_returns_without_rewriting_them(tmp_path):
    bars = long_double_bottom()
    calendar = list(bars.trade_date)
    old_events = v1.detect(bars)
    old_path = v1.write_artifact(
        old_events,
        v1.signal_frame(bars, old_events),
        v1.outcomes(bars, calendar),
        build_id=7,
        root=tmp_path / "v1",
    )
    before = (old_path / "returns" / "manifest.json").read_bytes()
    events = v2.detect(bars)
    v2.write_artifact(events, v2.signal_frame(bars, events), 7, root=tmp_path / "v2")
    loaded, fp, rt = v2.load_artifact(7, root=tmp_path / "v2", v1_root=tmp_path / "v1")
    assert len(loaded) == len(events)
    assert fp.manifest["v1_code"] == v1.code_hash()
    assert rt.manifest["horizons"] == [3, 5, 10, 20]
    assert (old_path / "returns" / "manifest.json").read_bytes() == before
    liquid = bars[["symbol", "trade_date"]].assign(tier=1)
    summary = v2.descriptive_market(fp, rt, liquid)
    assert len(summary) == 40  # the fixture begins in 2020, so only one slice exists
    assert set(summary.slice) == {"replication_seen"}
    assert set(summary.status) == {"DESCRIPTIVE_ONLY_SPENT_HISTORY"}
