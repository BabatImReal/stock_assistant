"""Tradeable forward returns (blocker G3, definition approved by Ben 2026-09-22).

The document measures 3 and 5 days forward from the signal day. That is not a
number anyone can trade, and measuring it would flatter every statistic built on
it. The approved definition:

    signal    at the CLOSE of day t
    entry     at the OPEN of day t+1      -- the first price available after the
                                             signal, so the signal day's close is
                                             never an entry price (doc §8.1)
    return_k  close(t+1+k) / open(t+1) - 1
    k         must be at least the earliest-sell offset for the ERA of the entry
              date. k = 3 and k = 5 are valid in every era.

Settlement has three eras, and the middle one is the trap: moving to "T+2
settlement" in January 2016 did NOT make shares sellable on T+2, because
settlement landed at 16:30, after the market closed. The earliest sell stayed
T+3 until August 2022 moved settlement before 13:00. All three are in
config/rules/market_rules.yaml.

Two fillability rules, because a price you could not have traded at is not a
return:

  ENTRY  rejected outright when day t+1 OPENS AT THE CEILING. Nobody fills a buy
         at the ceiling -- there are no sellers. The funnel can pick another day,
         so a rejected entry costs an observation rather than distorting one.
  EXIT   when the exit day CLOSES AT THE FLOOR, the position could not have been
         sold that day, so the exit moves to the next session that does not
         close at the floor, up to a cap. The move is flagged, because a
         stretched holding period is a real cost and must be visible.

Ceiling and floor are judged on the RAW (unadjusted) prices, since that is what
the exchange applies limits to, while the return itself is computed on the
adjusted series. The limit is the one for the exchange the symbol was on THAT
DAY (data/exchanges.py). Where that exchange is not dated, the filed one is
borrowed and every fillability result is FLAGGED; the backtest must pass them
through `quarantine_flagged` (decision 2026-09-23), exactly like sector values.

Returns are reported gross AND net. Net subtracts a broker fee on both sides
plus the 0.1 percent sale tax, which is charged on the sale whether or not the
trade made money -- so a loser pays it too, and it cannot be netted off a gain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from ..features.base import FLAG

CONFIG = Path(__file__).resolve().parents[3] / "config" / "rules"
MARKET_RULES = CONFIG / "market_rules.yaml"
COSTS = CONFIG / "costs.yaml"

# How far the exit may be pushed when the intended day closes at the floor.
# Beyond this the setup is simply untradeable and is dropped rather than held
# indefinitely on the hope of an exit.
MAX_EXIT_DEFERRAL = 5

# Prices are in thousands of VND with two decimals, so "at the ceiling" needs a
# small tolerance rather than exact equality.
LIMIT_EPSILON = 0.0015


@dataclass(frozen=True)
class Costs:
    broker_fee_rate: float
    sale_tax_rate: float
    provisional: bool

    @property
    def round_trip(self) -> float:
        """Total cost of a flat round trip, as a fraction of the entry price."""
        return 2 * self.broker_fee_rate + self.sale_tax_rate


def load_costs() -> Costs:
    cfg = yaml.safe_load(COSTS.read_text())
    return Costs(
        broker_fee_rate=float(cfg["fees"]["broker_fee_rate"]),
        sale_tax_rate=float(cfg["taxes"]["sale_tax_rate"]),
        provisional=bool(cfg["fees"].get("broker_fee_provisional", True)),
    )


def settlement_eras() -> list[dict]:
    eras = yaml.safe_load(MARKET_RULES.read_text())["settlement"]["eras"]
    return sorted(eras, key=lambda e: e["from"])


def earliest_sell_offset(entry_date) -> int:
    """Smallest k for which close(t+1+k) is a price we could have sold at.

    Chosen by the era of the ENTRY date, not the signal date: the settlement
    clock starts when the trade happens.
    """
    offset = settlement_eras()[0]["earliest_sell_offset"]
    for era in settlement_eras():
        if str(entry_date) >= era["from"]:
            offset = era["earliest_sell_offset"]
    return int(offset)


def net_return(gross: float, costs: Costs) -> float:
    """Gross return after fees and the sale tax.

    Modelled on the traded amounts rather than as a flat subtraction: the buy
    fee is paid on the entry value and the sell fee plus tax on the exit value,
    which is slightly different from 'gross minus round_trip' whenever the trade
    moved at all.
    """
    exit_multiple = 1.0 + gross
    proceeds = exit_multiple * (1 - costs.broker_fee_rate - costs.sale_tax_rate)
    outlay = 1.0 + costs.broker_fee_rate
    return proceeds / outlay - 1.0


def is_at_ceiling(raw_price: float, prev_raw_close: float, limit: float) -> bool:
    if prev_raw_close <= 0:
        return False
    return raw_price >= prev_raw_close * (1 + limit) - LIMIT_EPSILON


def is_at_floor(raw_price: float, prev_raw_close: float, limit: float) -> bool:
    if prev_raw_close <= 0:
        return False
    return raw_price <= prev_raw_close * (1 - limit) + LIMIT_EPSILON


def limit_in_force(exchange: str, day, default: float = 0.07) -> float:
    """The daily limit for `exchange` on `day` (market_rules.yaml, the same table
    data/checks.py `limit_sql` reads)."""
    periods = yaml.safe_load(MARKET_RULES.read_text())["price_limits"].get(exchange, [])
    for period in sorted(periods, key=lambda r: r["from"], reverse=True):
        if str(day) >= period["from"]:
            return float(period["limit"])
    return default


# The per-exchange results of `fillability`; each carries FLAG + name.
FILLABILITY = ("limit", "entry_at_ceiling", "exit_at_floor")


def fillability(bars: pd.DataFrame) -> pd.DataFrame:
    """G3's two fillability tests, per row of one symbol's RAW bars.

    bars: trade_date, open, close (RAW prices, consecutive sessions), exchange
    and exchange_unknown (data.exchanges.resolve).
      limit             the limit for that day's exchange
      entry_at_ceiling  this row OPENS at the ceiling: a buy here is rejected
      exit_at_floor     this row CLOSES at the floor: an exit here is deferred
    NaN on the first row (no previous close). Every result on a row whose
    exchange is not dated is flagged (FLAG + name): the limit itself may be the
    wrong one, e.g. +-7% applied to a stock that was really on HNX's +-10%.
    """
    prev = bars["close"].astype("float64").shift(1)
    pairs = zip(bars["exchange"], bars["trade_date"], strict=True)
    limit = pd.Series([limit_in_force(e, d) for e, d in pairs], index=bars.index)
    known_prev = prev > 0
    ceiling = bars["open"] >= prev * (1 + limit) - LIMIT_EPSILON
    floor = bars["close"] <= prev * (1 - limit) + LIMIT_EPSILON
    out = pd.DataFrame(
        {
            "limit": limit,
            "entry_at_ceiling": ceiling.astype("float64").where(known_prev),
            "exit_at_floor": floor.astype("float64").where(known_prev),
        }
    )
    flagged = bars["exchange_unknown"].to_numpy(bool)
    for name in FILLABILITY:
        out[FLAG + name] = flagged
    return out


def valid_horizons(entry_date, horizons: tuple[int, ...] = (3, 5)) -> list[int]:
    """The requested horizons that are actually sellable in this era."""
    floor_k = earliest_sell_offset(entry_date)
    return [k for k in horizons if k >= floor_k]
