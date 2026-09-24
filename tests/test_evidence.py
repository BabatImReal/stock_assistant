"""Tests for the gate and the base rates (backtest/evidence.py, E2). One test
per rule; each fails if its rule is removed.

A synthetic world built directly as a fingerprint + returns pair: every hit
and every net return is chosen, so each number can be checked by hand.
Horizon k = 3; the reliability floor is 30 de-clustered occurrences.
"""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from vnstock_research.backtest import evidence as ev
from vnstock_research.backtest import forward_returns as fr
from vnstock_research.features.base import FLAG

from ._helpers import fails_with

K = 3


def world(symbols=("AAA", "BBB"), n=200, every=4, tier=1):
    """`hammer_shape` fires on every `every`-th row of each symbol, where net
    is +2%; elsewhere net is -1%. The sector measure is flagged on the first
    50 rows. Everything liquid in `tier`."""
    dates = list(pd.bdate_range("2015-01-01", periods=n).date)
    later = list(pd.bdate_range("2015-01-01", periods=n + 10).date)
    f, r = [], []
    for sym in symbols:
        fire = np.arange(n) % every == 0
        f.append(
            pd.DataFrame(
                {
                    "symbol": sym,
                    "trade_date": dates,
                    "hammer_shape": fire.astype(float),
                    "sector_change_20d": 0.01,
                    FLAG + "sector_change_20d": np.arange(n) < 50,
                }
            )
        )
        net = np.where(fire, 0.02, -0.01)
        r.append(
            pd.DataFrame(
                {
                    "symbol": sym,
                    "trade_date": dates,
                    f"ret_{K}": net + 0.004,
                    f"net_{K}": net,
                    f"mfe_{K}": np.where(fire, 0.05, 0.01),
                    f"mae_{K}": np.where(fire, -0.03, -0.02),
                    f"exit_offset_{K}": 4,
                    f"deferred_{K}": 0,
                    f"known_on_{K}": later[4 : n + 4],
                    f"reason_{K}": None,
                    f"upcom_{K}": False,
                    f"{FLAG}fill_{K}": False,
                }
            )
        )
    fp = SimpleNamespace(
        values=pd.concat(f, ignore_index=True),
        manifest={
            "build_id": 5,
            "flagged": ["sector_change_20d"],
            "featureset": "fs",
            "code": "c1",
        },
    )
    rt = SimpleNamespace(
        values=pd.concat(r, ignore_index=True),
        manifest={
            "build_id": 5,
            "horizons": [K],
            "net_provisional": True,
            "rules": "r",
            "code": "c2",
        },
    )
    uni = fp.values[["symbol", "trade_date"]].assign(tier=tier)
    return fp, rt, uni


def gate(fp=None, rt=None, uni=None, before=None):
    a, b, c = world()
    return ev.validated(fp or a, rt or b, c if uni is None else uni, before)


# --- the gate ---------------------------------------------------------------


def test_two_builds_are_refused():
    fp, rt, uni = world()
    rt.manifest["build_id"] = 6
    fails_with(ValueError, "build 5 to returns of build 6", ev.validated, fp, rt, uni)


def test_flagged_feature_values_are_blanked_and_the_flags_dropped():
    v = gate().values
    assert v["sector_change_20d"].iloc[:50].isna().all()
    assert v["sector_change_20d"].iloc[50:200].notna().all()
    assert not [c for c in v.columns if c.startswith(FLAG)]


def test_a_flagged_measure_without_its_flag_is_refused():
    fp, rt, uni = world()
    fp.values = fp.values.drop(columns=FLAG + "sector_change_20d")
    fails_with(KeyError, FLAG + "sector_change_20d", ev.validated, fp, rt, uni)


def test_a_validated_table_comes_only_from_the_gate():
    fails_with(TypeError, "only from validated", ev.Validated, pd.DataFrame(), {})


def test_an_outcome_with_flagged_fillability_is_blanked():
    fp, rt, uni = world()
    rt.values.loc[3, f"{FLAG}fill_{K}"] = True  # UPCoM or an undated exchange
    v = ev.validated(fp, rt, uni).values
    assert v.loc[3, f"reason_{K}"] == "fill_flagged"
    assert np.isnan(v.loc[3, f"net_{K}"]) and np.isnan(v.loc[3, f"ret_{K}"])


def test_an_outcome_outside_the_liquid_universe_is_blanked():
    fp, rt, uni = world()
    uni = uni.drop(index=[7])
    v = ev.validated(fp, rt, uni).values
    assert v.loc[7, f"reason_{K}"] == "not_liquid"
    assert np.isnan(v.loc[7, f"net_{K}"])


def test_only_outcomes_known_strictly_before_the_query_day_count():
    fp, rt, uni = world()
    t = rt.values["trade_date"].iloc[100]
    v = ev.validated(fp, rt, uni, before=t).values
    assert (pd.to_datetime(v["trade_date"]) < pd.Timestamp(t)).all()
    a = v[v["symbol"] == "AAA"]
    # Row 95's outcome resolves 4 sessions later, on row 99: known before t.
    assert a[f"net_{K}"].iloc[95] == pytest.approx(-0.01)
    # Row 96 resolves ON t: not yet known when the question is asked.
    assert a[f"reason_{K}"].iloc[96] == "not_yet_known"
    assert np.isnan(a[f"net_{K}"].iloc[96])


def test_the_returns_own_reason_survives_the_gate_g20_included():
    """A window across a G20 factor defect was blanked by the generator; the
    gate keeps it blank and keeps its reason."""
    bars = pd.DataFrame(
        {
            "symbol": "AAA",
            "trade_date": list(pd.bdate_range("2015-01-01", periods=12).date),
            "matched_volume": 1000.0,
            "gap_before": 0,
            "excluded": False,
            "date_shifted": False,
            "exchange": "HOSE",
            "exchange_unknown": False,
            "factor_break": False,
        }
    )
    for col in ("open", "high", "low", "close"):
        bars[col] = bars["raw_" + col] = 20.0
    bars.loc[3, "factor_break"] = True
    out = fr.outcomes(bars, list(bars["trade_date"]), ks=(K,))
    fp, rt, uni = world(symbols=("AAA",), n=12)
    rt.values = out
    v = ev.validated(fp, rt, uni).values
    assert v.loc[0, f"reason_{K}"] == "factor_break"
    assert np.isnan(v.loc[0, f"net_{K}"])


# --- the numbers ------------------------------------------------------------


def numbers(v=None, symbol="AAA", **kw):
    return ev.evidence(v or gate(), {"hammer_shape": 1}, K, symbol, **kw)


def test_a_hit_is_a_positive_net_return_not_a_positive_gross_one():
    fp, rt, uni = world()
    fired = rt.values["symbol"].eq("AAA") & (np.arange(len(rt.values)) % 4 == 0)
    rt.values.loc[fired, f"net_{K}"] = -0.001  # gross still +0.3%
    e = numbers(ev.validated(fp, rt, uni))
    assert e.levels[0].hit_rate == 0.0


def test_the_base_rate_is_every_eligible_day_at_the_same_level():
    # AAA: 50 of its 200 days fire (net +2%), 150 do not (net -1%).
    e = numbers()
    stock = e.levels[0]
    assert (stock.hit_rate, stock.base_rate, stock.base_n) == (1.0, 0.25, 200)


def test_a_day_the_condition_could_not_be_judged_is_not_in_the_base():
    fp, rt, uni = world()
    fp.values.loc[1:10, "hammer_shape"] = np.nan  # 10 AAA days, 2 of them firing
    stock = numbers(ev.validated(fp, rt, uni)).levels[0]
    assert stock.base_n == 190 and stock.base_rate == pytest.approx(48 / 190)
    assert stock.drops.get("condition_unknown") == 10


def test_the_edge_is_the_hit_rate_minus_the_base_rate():
    stock = numbers().levels[0]
    assert stock.edge == pytest.approx(stock.hit_rate - stock.base_rate)


def test_repeats_within_k_sessions_count_once():
    # Firing every day: windows overlap, so one counted occurrence per k + 1.
    fp, rt, uni = world(every=1, n=40)
    stock = numbers(ev.validated(fp, rt, uni)).levels[0]
    assert stock.n_raw == 40 and stock.n_declustered == 10


def test_the_first_level_with_enough_declustered_occurrences_is_used():
    # AAA alone: 50 raw, 50 de-clustered (every 4th day, k = 3): enough.
    assert numbers().chosen.level == "stock"
    # 20 occurrences on AAA (every 10th of 200 days): too few -> its tier.
    fp, rt, uni = world(every=10)
    e = numbers(ev.validated(fp, rt, uni))
    assert (e.levels[0].n_declustered, e.chosen.level) == (20, "tier")
    # 50 raw occurrences but only 25 de-clustered (every 2nd day, k = 3):
    # the floor counts de-clustered ones.
    fp, rt, uni = world(every=2, n=100)
    e = numbers(ev.validated(fp, rt, uni))
    assert (e.levels[0].n_raw, e.levels[0].n_declustered) == (50, 25)
    assert e.chosen.level == "tier"


def test_below_the_floor_at_the_tier_the_market_is_used():
    fp, rt, uni = world(every=10)
    uni.loc[uni["symbol"] == "BBB", "tier"] = 2  # AAA's tier holds only AAA
    e = numbers(ev.validated(fp, rt, uni))
    assert e.chosen.level == "market" and e.sufficient


def test_too_few_even_for_the_market_is_said_so():
    fp, rt, uni = world(every=20, symbols=("AAA",))
    e = numbers(ev.validated(fp, rt, uni))
    assert not e.sufficient and e.chosen.level == "market"


def test_the_tier_is_the_stocks_tier_as_of_its_latest_liquid_day():
    fp, rt, uni = world(every=10)
    uni.loc[(uni["symbol"] == "AAA") & (uni.index % 200 >= 150), "tier"] = 2
    uni.loc[uni["symbol"] == "BBB", "tier"] = 2
    tier = numbers(ev.validated(fp, rt, uni)).levels[1]
    assert tier.group == "2"


def test_every_level_reports_expectancy_wins_losses_and_excursions():
    fp, rt, uni = world()
    fired = rt.values.index[rt.values["symbol"].eq("AAA")][::4]
    rt.values.loc[fired[:10], f"net_{K}"] = -0.05  # 10 losers among 50
    rt.values.loc[fired[:10], f"ret_{K}"] = -0.046
    rt.values.loc[fired[0], f"mae_{K}"] = -0.08
    s = numbers(ev.validated(fp, rt, uni)).levels[0]
    assert s.hit_rate == pytest.approx(0.8)
    assert s.expectancy == pytest.approx((40 * 0.02 - 10 * 0.05) / 50)
    assert (s.avg_win, s.avg_loss) == pytest.approx((0.02, -0.05))
    assert s.gross_mean == pytest.approx((40 * 0.024 - 10 * 0.046) / 50)
    assert (s.mfe_mean, s.mae_worst) == pytest.approx((0.05, -0.08))
    assert s.mae_mean == pytest.approx((49 * -0.03 - 0.08) / 50)


def test_every_level_counts_its_dropped_rows_by_reason():
    fp, rt, uni = world()
    rt.values.loc[[2, 3], f"reason_{K}"] = "window_gap"
    rt.values.loc[[2, 3], f"net_{K}"] = np.nan
    rt.values.loc[5, f"{FLAG}fill_{K}"] = True
    rt.values.loc[205, f"{FLAG}fill_{K}"] = True  # BBB: not this stock's
    e = numbers(ev.validated(fp, rt, uni))
    s = e.levels[0]
    assert s.drops["window_gap"] == 2 and s.drops["fill_flagged"] == 1
    assert e.levels[-1].drops["fill_flagged"] == 2  # the market level


def test_net_numbers_carry_the_provisional_stamp():
    e = numbers()
    assert e.net_provisional
    assert "PROVISIONAL" in ev.stamp(e)


def test_the_sector_is_shown_beside_labelled_exploratory_never_used():
    e = numbers(sectors={"AAA": "8300", "BBB": "8300"})
    assert e.sector.exploratory and e.sector.level == "sector"
    assert "sector" not in [x.level for x in e.levels]
    assert "EXPLORATORY" in ev.stamp(e)


def test_the_period_limits_every_number():
    e = numbers(start="2015-06-01", end="2015-09-30")
    assert e.period[0] >= "2015-06-01" and e.period[1] <= "2015-09-30"
    assert e.levels[0].base_n < 200


def test_evidence_takes_only_a_validated_table():
    fp, rt, uni = world()
    fails_with(
        TypeError, "only a Validated", ev.evidence, fp, {"hammer_shape": 1}, K, "AAA"
    )
