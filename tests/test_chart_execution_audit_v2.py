"""The execution ledger keeps overlapping events and unknown history distinct."""

import pandas as pd
from scripts.audit_chart_execution_v2 import tally

from vnstock_research.chart_research_v2 import SIGNALS


def test_tally_keeps_two_patterns_on_one_stock_day():
    events = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "variant": "double_top",
                "side": "up",
                "signal_on": "2019-01-02",
            },
            {
                "symbol": "AAA",
                "variant": "symmetric_triangle",
                "side": "down",
                "signal_on": "2019-01-02",
            },
            {
                "symbol": "BBB",
                "variant": "double_bottom",
                "side": "up",
                "signal_on": "2019-01-03",
            },
        ]
    )
    gated = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "trade_date": "2019-01-02",
                "reason_10": None,
                "deferred_10": 1,
                "tier": 2,
            },
            {
                "symbol": "BBB",
                "trade_date": "2019-01-03",
                "reason_10": "not_liquid",
                "deferred_10": None,
                "tier": None,
            },
        ]
    )
    for name in SIGNALS:
        gated[name] = float("nan")
    gated.loc[0, ["double_top__up", "symmetric_triangle__down"]] = 1.0
    result = tally(events, gated, "2012-01-01", "2020-01-01")
    assert (result["confirmed"], result["observable"], result["unknown_history"]) == (
        3,
        2,
        1,
    )
    assert result["resolved"] == result["resolved_deferred"] == 2
    assert result["reasons"].loc[("up", "resolved")] == 1
    assert result["reasons"].loc[("down", "resolved")] == 1
