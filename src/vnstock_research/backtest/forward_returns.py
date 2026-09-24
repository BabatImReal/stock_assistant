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
adjusted series. They come from `data.checks.limit_prices` (B1): the ONE
definition, shared with the gate, with the tick rounding and the first-day /
resumption band. The limit is the one for the exchange the symbol was on THAT
DAY (data/exchanges.py). The reference is the previous close ADJUSTED for any
corporate action between the two days, as the exchange sets it on an ex-date.

Every fillability result is FLAGGED, and must pass `quarantine_flagged`
(decision 2026-09-23), where it rests on something we cannot see:
  - the exchange is not dated (the filed one is borrowed);
  - the exchange is UPCoM, whose reference is (to be verified) the previous
    session's AVERAGE price, which we do not store (ruling A9).

WHAT IS STORED (`outcomes`, one row per signal day t, columns per horizon k):
gross and net return, MFE/MAE, the exit, `known_on` = the date the outcome
actually resolved (after any deferral), and when there is no outcome, the
REASON. No outcome is blank, never 0: a zero would read as "flat" when the
truth is "unknowable".

Returns are reported gross AND net. Net subtracts a broker fee on both sides
plus the 0.1 percent sale tax, which is charged on the sale whether or not the
trade made money -- so a loser pays it too, and it cannot be netted off a gain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .. import store
from ..data import checks
from ..features.base import FLAG

CONFIG = Path(__file__).resolve().parents[3] / "config" / "rules"
MARKET_RULES = CONFIG / "market_rules.yaml"
COSTS = CONFIG / "costs.yaml"
PATTERNS = CONFIG / "patterns.yaml"

# How far the exit may be pushed when the intended day closes at the floor.
# Beyond this the setup is simply untradeable and is dropped rather than held
# indefinitely on the hope of an exit.
MAX_EXIT_DEFERRAL = 5


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


# The per-exchange results of `fillability`; each carries FLAG + name.
FILLABILITY = ("limit", "entry_at_ceiling", "exit_at_floor")


def reference(bars: pd.DataFrame) -> pd.Series:
    """The RAW reference price each day: the previous close, ADJUSTED for any
    corporate action between the two days (ruling A9).

    On an ex-date the exchange lowers the reference by the action, so a raw
    previous close would put the ceiling too high and miss a real limit-up.
    adj(t-1) / factor(t), with factor = adjusted / raw close, is exactly the
    previous close in today's raw terms; on an ordinary day it is the raw
    previous close.
    """
    return bars["close"].shift(1) * bars["raw_close"] / bars["close"]


def fillability(bars: pd.DataFrame) -> pd.DataFrame:
    """G3's two fillability tests, per row of one symbol's bars.

    bars: trade_date, open, close (RAW prices, consecutive sessions), exchange
    and exchange_unknown (data.exchanges.resolve); optionally `reference` (the
    raw reference price, default the previous raw close) and `gap_before` (the
    sessions skipped, for the resumption band).
      limit             the limit applied that day (the first-day band on a
                        resumption)
      entry_at_ceiling  this row OPENS at the ceiling: a buy here is rejected
      exit_at_floor     this row CLOSES at the floor: an exit here is deferred
    NaN where there is no reference (the first row). FLAGGED (FLAG + name)
    where the exchange is not dated, or is UPCoM (see the module docstring).
    """
    ref = (
        bars["reference"]
        if "reference" in bars
        else bars["close"].astype("float64").shift(1)
    ).astype("float64")
    skipped = bars["gap_before"] if "gap_before" in bars else 0
    first = np.asarray(skipped >= checks.resumption_sessions(), dtype=bool)
    first = np.broadcast_to(first, len(bars))
    limits = checks.limit_prices(ref, bars["exchange"], bars["trade_date"], first)
    # Judged only with a reference AND limits: an exchange missing from the
    # tick table gives no limits, and "not at the ceiling" is not knowable then.
    known = (
        (ref > 0).to_numpy()
        & limits["ceiling"].notna().to_numpy()
        & limits["floor"].notna().to_numpy()
    )
    ceiling = checks.at_ceiling(bars["open"], limits)
    floor = checks.at_floor(bars["close"], limits)
    out = pd.DataFrame(
        {
            "limit": np.where(known, limits["rate"], np.nan),
            "entry_at_ceiling": np.where(known, ceiling, np.nan),
            "exit_at_floor": np.where(known, floor, np.nan),
        },
        index=bars.index,
    )
    flagged = bars["exchange_unknown"].to_numpy(bool) | (
        bars["exchange"].to_numpy(object) == "UPCOM"
    )
    for name in FILLABILITY:
        out[FLAG + name] = flagged
    return out


def valid_horizons(entry_date, horizons: tuple[int, ...] = (3, 5)) -> list[int]:
    """The requested horizons that are actually sellable in this era."""
    floor_k = earliest_sell_offset(entry_date)
    return [k for k in horizons if k >= floor_k]


# --- the generator (B2) ------------------------------------------------------

# Why an outcome is blank, in the order they are met walking forward from t.
REASONS = (
    "pending",  # the market calendar ends before the outcome resolves
    "data_ends",  # the stock's rows end first while the market goes on (G11)
    "no_next_session",  # the stock's next row comes after a trading gap
    "window_gap",  # a trading gap inside the window (CLAUDE.md)
    "window_excluded",  # an excluded row on t .. exit
    "not_tradeable",  # entry or exit day: no matched volume, or date-shifted
    "not_sellable",  # k below the entry era's earliest-sell offset
    "entry_at_ceiling",  # t+1 opened at the ceiling: no fill (G3)
    "exit_floor_unresolved",  # still at the floor after MAX_EXIT_DEFERRAL
)
# The outcome columns, per horizon k: `<name>_<k>`.
OUTCOME = ("ret", "net", "mfe", "mae")


def horizons() -> tuple[int, ...]:
    cfg = yaml.safe_load(PATTERNS.read_text())["horizons"]
    return tuple(int(k) for k in cfg["forward_days"])


def _sell_offsets(dates) -> np.ndarray:
    """earliest_sell_offset for every date at once."""
    d = pd.to_datetime(pd.Series(dates)).dt.strftime("%Y-%m-%d").to_numpy()
    eras = settlement_eras()
    out = np.full(len(d), int(eras[0]["earliest_sell_offset"]))
    for era in eras:
        out = np.where(d >= era["from"], int(era["earliest_sell_offset"]), out)
    return out


def outcomes(bars: pd.DataFrame, calendar, ks=None, costs=None) -> pd.DataFrame:
    """The forward outcome of a signal at the close of every row of `bars`.

    bars: ONE symbol, oldest first, as features.bars.load returns it (adjusted
    open/high/low/close, raw_*, exchange, gap_before in sessions, excluded,
    matched_volume, date_shifted). calendar: every market session, oldest
    first; its end is where "not known yet" begins.

    For a signal on row i and horizon k, walking forward:
      entry  row i+1: the NEXT session (no gap), tradeable, not opening at the
             ceiling; k must be sellable in the entry's settlement era;
      hold   rows i+2 .. i+k: no gap, not excluded;
      exit   row i+1+k: tradeable; if it closes at the floor the exit moves
             to the next session, up to MAX_EXIT_DEFERRAL times.
    The first obstacle met is the row's reason (REASONS). Otherwise:
      ret_k   close(exit) / open(entry) - 1 on ADJUSTED prices (G3)
      net_k   after both fees and the sale tax (PROVISIONAL fee, costs.yaml)
      mfe_k / mae_k  highest high / lowest low over entry .. exit vs the entry
      exit_offset_k  sessions from t to the exit; deferred_k  sessions pushed
      known_on_k     the date the outcome resolved: the ACTUAL exit, after any
                     deferral (for a blank one, the row that decided it)
      flag__fill_k   a fillability judgement it rests on is flagged (exchange
                     not dated, or UPCoM); upcom_k  one of them was on UPCoM
    """
    ks = ks or horizons()
    costs = costs or load_costs()
    n = len(bars)
    fill = fillability(
        bars.assign(
            open=bars["raw_open"], close=bars["raw_close"], reference=reference(bars)
        )
    )
    session = pd.Index(calendar).get_indexer(bars["trade_date"])
    n_cal = len(calendar)
    gap = (bars["gap_before"].to_numpy() > 0).tolist()
    excluded = bars["excluded"].to_numpy(bool).tolist()
    shifted = (
        bars["date_shifted"].to_numpy(bool)
        if "date_shifted" in bars
        else np.zeros(n, bool)
    )
    tradeable = ((bars["matched_volume"].to_numpy() > 0) & ~shifted).tolist()
    at_ceiling = (fill["entry_at_ceiling"].to_numpy() == 1.0).tolist()
    at_floor = (fill["exit_at_floor"].to_numpy() == 1.0).tolist()
    # A judgement we could not make (no limits) quarantines the row like a
    # flagged one: "not at the ceiling" is then not known.
    flagged = (
        fill[FLAG + "entry_at_ceiling"].to_numpy(bool)
        | fill["entry_at_ceiling"].isna().to_numpy()
    )
    upcom = bars["exchange"].to_numpy(object) == "UPCOM"
    sell = _sell_offsets(bars["trade_date"]).tolist()
    dates = list(bars["trade_date"])
    o, h, lo, c = (
        bars[x].to_numpy("float64") for x in ("open", "high", "low", "close")
    )

    def resolve(i: int, k: int):
        """(reason, exit_row, decided_row) for the signal on row i."""

        def missing(m):
            # Row i+m does not exist: either the market has not got there yet,
            # or the stock stopped trading while the market went on.
            return ("pending" if session[i] + m >= n_cal else "data_ends"), None, None

        if excluded[i]:
            return "window_excluded", None, i
        e = i + 1
        if e >= n:
            return missing(1)
        if gap[e]:
            return "no_next_session", None, e
        if excluded[e]:
            return "window_excluded", None, e
        if not tradeable[e]:
            return "not_tradeable", None, e
        if k < sell[e]:
            return "not_sellable", None, e
        if at_ceiling[e]:
            return "entry_at_ceiling", None, e
        for m in range(2, 2 + k + MAX_EXIT_DEFERRAL):
            j = i + m
            if j >= n:
                return missing(m)
            if gap[j]:
                return "window_gap", None, j
            if excluded[j]:
                return "window_excluded", None, j
            if m < 1 + k:
                continue  # holding: only the window rules apply
            if not tradeable[j]:
                return "not_tradeable", None, j
            if not at_floor[j]:
                return None, j, j
        return "exit_floor_unresolved", None, i + 1 + k + MAX_EXIT_DEFERRAL

    out = pd.DataFrame(
        {
            "symbol": bars["symbol"].to_numpy(),
            "trade_date": bars["trade_date"].to_numpy(),
        }
    )
    for k in ks:
        cols = {name: np.full(n, np.nan) for name in OUTCOME}
        offset = pd.array([None] * n, dtype="Int64")
        deferred = pd.array([None] * n, dtype="Int64")
        known_on, reason = [None] * n, [None] * n
        flag, on_upcom = np.zeros(n, bool), np.zeros(n, bool)
        for i in range(n):
            why, x, decided = resolve(i, k)
            reason[i] = why
            known_on[i] = dates[decided] if decided is not None else None
            if x is None:
                continue
            e = i + 1
            cols["ret"][i] = c[x] / o[e] - 1.0
            cols["mfe"][i] = h[e : x + 1].max() / o[e] - 1.0
            cols["mae"][i] = lo[e : x + 1].min() / o[e] - 1.0
            offset[i], deferred[i] = x - i, x - (i + 1 + k)
            # The judged rows: the entry, and every exit attempt.
            judged = [e, *range(i + 1 + k, x + 1)]
            flag[i], on_upcom[i] = flagged[judged].any(), upcom[judged].any()
        cols["net"] = net_return(cols["ret"], costs)
        for name in OUTCOME:
            out[f"{name}_{k}"] = cols[name]
        out[f"exit_offset_{k}"] = offset
        out[f"deferred_{k}"] = deferred
        out[f"known_on_{k}"] = known_on
        out[f"reason_{k}"] = reason
        out[f"upcom_{k}"] = on_upcom
        out[f"{FLAG}fill_{k}"] = flag
    return out


# --- storage (Parquet by year + manifest, shared with the fingerprint) -------

ROOT = store.PROCESSED / "returns"
# The code an outcome depends on: this module, the limit function and loaders
# (data/), the bars frame (features/) and the storage code.
CODE_DIRS = ("backtest", "data", "features", "store.py")


def rules_hash() -> str:
    """The rule files an outcome depends on: limits, ticks, settlement, costs,
    horizons. Changing any of them makes a stored table stale."""
    return store.files_hash([MARKET_RULES, COSTS, PATTERNS])


def code_hash() -> str:
    return store.code_hash(CODE_DIRS)


@dataclass(frozen=True)
class Returns:
    values: pd.DataFrame
    manifest: dict


def write(values: pd.DataFrame, build_id: int, root: Path = ROOT) -> Path:
    costs, ks = load_costs(), horizons()
    manifest = {
        "build_id": build_id,
        "rules": rules_hash(),
        "code": code_hash(),
        "horizons": list(ks),
        "max_exit_deferral": MAX_EXIT_DEFERRAL,
        "reasons": list(REASONS),
        "costs": {
            "broker_fee_rate": costs.broker_fee_rate,
            "sale_tax_rate": costs.sale_tax_rate,
        },
        # Every NET number is stamped with this until Ben confirms his fee.
        "net_provisional": costs.provisional,
        "flag_for": {f"{name}_{k}": f"{FLAG}fill_{k}" for k in ks for name in OUTCOME},
    }
    return store.write(values, root / f"{build_id}_{rules_hash()}", manifest)


def load(build_id: int, *, root: Path = ROOT, columns=None, start=None, end=None):
    """The stored outcomes of this build under TODAY's rules and code, or a
    loud refusal (store.load)."""
    values, man = store.load(
        root / f"{build_id}_{rules_hash()}",
        "returns",
        f"build {build_id}, rules {rules_hash()}",
        {"build_id": build_id, "rules": rules_hash(), "code": code_hash()},
        columns,
        start,
        end,
    )
    return Returns(values, man)


def join(fp, rt: Returns) -> pd.DataFrame:
    """Features and outcomes side by side on (symbol, trade_date). Refuses two
    different adjustment builds: the same date would carry prices from two
    adjustment policies. EXPLORATORY: nothing is quarantined here."""
    a, b = fp.manifest["build_id"], rt.manifest["build_id"]
    if a != b:
        raise ValueError(
            f"cannot join a fingerprint of build {a} to returns of build {b}"
        )
    return fp.values.merge(rt.values, on=store.KEYS, how="left", validate="one_to_one")


def build(conn, root: Path = ROOT, start: str = "2012-01-01") -> Path:
    """Every symbol's outcomes for the current promoted build."""
    from ..features import bars

    build_id = bars.current_build(conn)
    calendar = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT trade_date FROM trading_day WHERE trade_date >= %s "
            "ORDER BY 1",
            (start,),
        ).fetchall()
    ]
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM bar_adjusted WHERE build_id = %s "
            "AND trade_date >= %s ORDER BY 1",
            (build_id, start),
        ).fetchall()
    ]
    parts = [
        outcomes(f, calendar)
        for _, f in bars.load_many(conn, symbols, start=start, build=build_id)
    ]
    return write(pd.concat(parts, ignore_index=True), build_id, root)


def report(rt: Returns, liquid: pd.Series) -> list[str]:
    """No-outcome reasons per horizon, whole market and liquid ON t; the
    deferrals; the flagged share and UPCoM's share of the liquid outcomes.
    liquid: bool per row of rt.values (data.universe.liquid on each date)."""
    v, lines = rt.values, []
    stamp = (
        " (NET is PROVISIONAL: broker fee not confirmed)"
        if rt.manifest["net_provisional"]
        else ""
    )
    lines.append(
        f"build {rt.manifest['build_id']}, rules {rt.manifest['rules']}, "
        f"{len(v):,} stock-days ({int(liquid.sum()):,} liquid on t){stamp}"
    )
    for k in rt.manifest["horizons"]:
        state = v[f"reason_{k}"].fillna("resolved")
        lines.append(f"\nk = {k}           {'whole market':>22}{'liquid on t':>22}")
        for name in ("resolved", *REASONS):
            a, b = int((state == name).sum()), int((state[liquid] == name).sum())
            lines.append(
                f"  {name:<22}{a:>12,} {a / len(v):>7.2%}"
                f"{b:>13,} {b / max(liquid.sum(), 1):>7.2%}"
            )
        ok = liquid & (state == "resolved")
        deferred = v.loc[ok, f"deferred_{k}"].astype("int64")
        lines.append(
            f"  liquid resolved: {int(ok.sum()):,}; exit deferred "
            f"{int((deferred > 0).sum()):,} "
            f"(max {int(deferred.max()) if len(deferred) else 0} sessions)"
        )
        fl, up = v.loc[ok, f"{FLAG}fill_{k}"], v.loc[ok, f"upcom_{k}"]
        lines.append(
            f"  liquid resolved FLAGGED (quarantined): {int(fl.sum()):,} "
            f"= {fl.mean():.2%}; of which rest on UPCoM "
            f"(approximate reference, A9): {int(up.sum()):,} = {up.mean():.2%}"
        )
    return lines


if __name__ == "__main__":
    from datetime import datetime

    from ..data import db, universe

    with db.connect() as conn:
        path = build(conn)
        rt = load(int(path.name.split("_")[0]))
        panel = universe.liquid(conn, "2012-01-01")
    stacked = panel.stack()
    stacked = stacked[stacked]
    keys = pd.MultiIndex.from_arrays([rt.values["trade_date"], rt.values["symbol"]])
    liquid = pd.Series(keys.isin(stacked.index), index=rt.values.index)
    lines = [str(path), *report(rt, liquid)]
    print("\n".join(lines))
    out = (
        store.PROCESSED.parent / "reports" / f"returns-{datetime.now():%Y%m%d-%H%M}.txt"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
