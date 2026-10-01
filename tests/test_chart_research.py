"""The small causal chart pilot must fail if pivots look ahead or span gaps."""

import numpy as np
import pandas as pd

from vnstock_research import chart_research as chart

from ._helpers import frame


def shaped(points, n=65):
    xs, ys = zip(*points, strict=True)
    close = np.interp(np.arange(n), xs, ys)
    return frame(n=n, close=close)


def double_bottom():
    return shaped(
        [(0, 105), (10, 95), (20, 110), (34, 95.5), (39, 99), (42, 112), (64, 115)]
    )


def triangle():
    return shaped(
        [
            (0, 90),
            (10, 105),
            (18, 90),
            (26, 101),
            (34, 93),
            (42, 97),
            (44, 95.5),
            (45, 100),
            (64, 105),
        ]
    )


def confirmed(bars, variant):
    out = chart.detect(bars)
    return out[(out["variant"] == variant) & out["signal_on"].notna()]


def test_double_bottom_is_known_only_after_second_low_and_neckline_break():
    bars = double_bottom()
    assert confirmed(bars.iloc[:35], "double_bottom").empty
    assert confirmed(bars.iloc[:42], "double_bottom").empty
    hit = confirmed(bars.iloc[:43], "double_bottom").iloc[0]
    assert hit["candidate_on"] == bars.trade_date.iloc[36]
    assert hit["signal_on"] == bars.trade_date.iloc[42]
    assert hit["side"] == "up"
    assert hit["anchor_confirmed_on"][-1] == bars.trade_date.iloc[36]


def test_future_prices_cannot_rewrite_a_past_signal():
    bars = double_bottom()
    early = confirmed(bars.iloc[:43], "double_bottom").iloc[0]
    bars.loc[43:, "close"] = 50.0
    later = confirmed(bars, "double_bottom").iloc[0]
    assert (early["candidate_on"], early["signal_on"], early["side"]) == (
        later["candidate_on"],
        later["signal_on"],
        later["side"],
    )


def test_triangle_records_the_observed_break_side():
    bars = triangle()
    assert confirmed(bars.iloc[:45], "symmetric_triangle").empty
    hit = confirmed(bars.iloc[:46], "symmetric_triangle").iloc[0]
    assert hit["candidate_on"] == bars.trade_date.iloc[44]
    assert hit["signal_on"] == bars.trade_date.iloc[45]
    assert hit["side"] == "up"


def test_mirrored_double_top_breaks_down():
    bars = double_bottom()
    bars["close"] = 200 - bars["close"]
    hit = confirmed(bars, "double_top").iloc[0]
    assert hit["side"] == "down"
    assert hit["signal_on"] == bars.trade_date.iloc[42]


def test_triangle_variants_are_geometry_not_predicted_break_side():
    cfg = chart.rules()
    ascending = [
        ("high", 10, 100.0),
        ("low", 18, 90.0),
        ("high", 26, 100.0),
        ("low", 34, 94.0),
        ("high", 42, 100.0),
    ]
    descending = [
        ("high", 10, 110.0),
        ("low", 18, 90.0),
        ("high", 26, 106.0),
        ("low", 34, 90.0),
        ("high", 42, 102.0),
    ]
    assert chart._triangle_candidate(ascending, cfg)["variant"] == "ascending_triangle"
    assert (
        chart._triangle_candidate(descending, cfg)["variant"] == "descending_triangle"
    )


def test_break_before_last_pivot_is_known_is_late_not_a_signal():
    bars = double_bottom()
    bars.loc[35:36, "close"] = [112.0, 113.0]
    out = chart.detect(bars)
    late = out[out.variant == "double_bottom"].iloc[0]
    assert late["state"] == "late_or_unobservable"
    assert pd.isna(late["signal_on"])


def test_failure_is_dated_later_without_erasing_the_signal():
    bars = double_bottom()
    bars.loc[47, "close"] = 95.0
    hit = confirmed(bars, "double_bottom").iloc[0]
    assert hit["signal_on"] == bars.trade_date.iloc[42]
    assert hit["failure_on"] == bars.trade_date.iloc[47]


def test_a_gap_inside_geometry_makes_the_shape_unavailable():
    bars = double_bottom()
    bars.loc[30, "gap_before"] = 2
    assert confirmed(bars, "double_bottom").empty


def test_prior_trend_never_reads_across_a_gap():
    bars = shaped(
        [
            (0, 120),
            (60, 110),
            (80, 95),
            (90, 110),
            (104, 95.5),
            (109, 99),
            (112, 112),
            (139, 115),
        ],
        n=140,
    )
    bars.loc[70, "gap_before"] = 2
    hit = confirmed(bars, "double_bottom").iloc[0]
    assert hit["prior_trend"] == "unknown"


def test_signal_frame_marks_unobservable_history_unknown_not_false():
    bars = double_bottom()
    signals = chart.signal_frame(bars, chart.detect(bars), eligible_history=40)
    assert np.isnan(signals["double_bottom"].iloc[38])
    assert signals["double_bottom"].iloc[41] == 0.0
    assert signals["double_bottom"].iloc[42] == 1.0


def test_research_artifact_is_versioned_and_loads_all_four_horizons(tmp_path):
    bars = double_bottom()
    for name in ("raw_open", "raw_high", "raw_low", "raw_close"):
        bars[name] = bars[name[4:]]
    bars["date_shifted"] = False
    bars["exchange_unknown"] = False
    events = chart.detect(bars)
    signals = chart.signal_frame(bars, events, eligible_history=40)
    returns = chart.outcomes(bars, list(bars.trade_date))
    chart.write_artifact(events, signals, returns, build_id=7, root=tmp_path)
    loaded_events, fp, rt = chart.load_artifact(7, root=tmp_path)
    assert len(loaded_events) == len(events)
    assert fp.manifest["build_id"] == rt.manifest["build_id"] == 7
    assert fp.manifest["source_code"] == rt.manifest["source_code"]
    assert rt.manifest["horizons"] == [3, 5, 10, 20]
    assert rt.manifest["net_provisional"] is True
    pd.testing.assert_frame_equal(rt.values, returns)


def test_long_outcome_stays_unknown_until_it_actually_resolves(tmp_path):
    from vnstock_research.backtest import evidence

    bars = double_bottom()
    for name in ("raw_open", "raw_high", "raw_low", "raw_close"):
        bars[name] = bars[name[4:]]
    bars["date_shifted"] = False
    bars["exchange_unknown"] = False
    chart.write_artifact(
        chart.detect(bars),
        chart.signal_frame(bars, chart.detect(bars), eligible_history=40),
        chart.outcomes(bars, list(bars.trade_date)),
        build_id=7,
        root=tmp_path,
    )
    _, fp, rt = chart.load_artifact(7, root=tmp_path)
    liquid = bars[["symbol", "trade_date"]].assign(tier=1)
    gated = evidence.validated(fp, rt, liquid, before=bars.trade_date.iloc[50])
    row = gated.values[gated.values.trade_date == bars.trade_date.iloc[42]].iloc[0]
    assert row["double_bottom"] == 1.0
    assert pd.isna(row["reason_3"])
    assert row["reason_20"] == "not_yet_known"
    assert np.isnan(row["net_20"])


def test_a_gap_inside_the_long_outcome_is_not_a_resolved_trade():
    bars = frame(n=32, close=20.0)
    for name in ("raw_open", "raw_high", "raw_low", "raw_close"):
        bars[name] = bars[name[4:]]
    bars["date_shifted"] = False
    bars["exchange_unknown"] = False
    bars.loc[15, "gap_before"] = 2
    out = chart.outcomes(bars, list(bars.trade_date))
    assert pd.isna(out["reason_3"].iloc[0])
    assert out["reason_20"].iloc[0] == "window_gap"


def test_research_files_do_not_enter_frozen_hash_scopes():
    from vnstock_research.backtest import forward_returns as fr
    from vnstock_research.patterns import fingerprint as fp

    assert "chart_research.py" not in fp.CODE_DIRS
    assert "chart_research.py" not in fr.CODE_DIRS
    assert chart.CONFIG not in (fr.MARKET_RULES, fr.COSTS, fr.PATTERNS)
    assert chart.rules()["registered_trial_count"] == (
        len(chart.rules()["variants"]) * len(chart.HORIZONS)
    )


def test_full_pilot_assembly_and_descriptive_base(tmp_path):
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
    events, signals, returns = chart.assemble([bars], list(bars.trade_date))
    assert signals["double_bottom"].iloc[172] == 1.0
    assert np.isnan(signals["double_bottom"].iloc[123])
    chart.write_artifact(events, signals, returns, build_id=7, root=tmp_path)
    _, fp, rt = chart.load_artifact(7, root=tmp_path)
    liquid = bars[["symbol", "trade_date"]].assign(tier=1)
    summary = chart.descriptive_market(fp, rt, liquid)
    assert set(summary.status) == {"DESCRIPTIVE_ONLY_SPENT_HISTORY"}
    assert set(summary.k) == {3, 5, 10, 20}
    assert summary[summary.variant == "double_bottom"].n_raw.max() >= 1


def test_signal_frame_uses_positions_even_if_bars_have_other_index_labels():
    bars = double_bottom().set_index(pd.Index(range(100, 165)))
    events = chart.detect(bars)
    signals = chart.signal_frame(bars, events, eligible_history=40)
    assert signals["double_bottom"].iloc[42] == 1.0


def test_four_horizon_research_uses_the_existing_return_core():
    from vnstock_research.backtest import forward_returns as fr

    bars = frame(n=32, close=20.0)
    for name in ("raw_open", "raw_high", "raw_low", "raw_close"):
        bars[name] = bars[name[4:]]
    bars["date_shifted"] = False
    bars["exchange_unknown"] = False
    full = fr.outcomes(bars, list(bars.trade_date), ks=chart.HORIZONS)
    old = fr.outcomes(bars, list(bars.trade_date), ks=(3, 5))
    assert chart.HORIZONS == (3, 5, 10, 20)
    assert chart.PRIMARY_HORIZON == 10
    for k in (3, 5):
        for name in ("ret", "net", "reason", "known_on"):
            pd.testing.assert_series_equal(full[f"{name}_{k}"], old[f"{name}_{k}"])
    assert full["exit_offset_20"].iloc[0] == 21
    assert full["known_on_20"].iloc[0] == bars.trade_date.iloc[21]
