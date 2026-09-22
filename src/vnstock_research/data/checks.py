"""Data-quality checks that must pass before any data is used in research.

From the approved data model. Each check returns a Check with a severity:

  fail  -- the build is not promoted. Research keeps reading the last good one.
  warn  -- recorded and reported, but does not block. Used where the finding is
           real but expected (a delisted stock has gaps; a corporate action
           produces a legitimate move beyond the price limit).

The point is not to produce a clean bill of health. It is to make every known
defect a number Ben has seen, rather than a surprise that shows up later as a
pattern firing on a move that never happened.

Nothing here deletes data. A failing build is simply not promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# Market rules live in config, with the date each value took effect, because a
# backtest must apply the rule in force on the date it is testing (doc §7.5).
# Loaded here so the price-limit check uses the real limit rather than today's.
MARKET_RULES = (
    Path(__file__).resolve().parents[3] / "config" / "rules" / "market_rules.yaml"
)

# A trading day with fewer than this many symbols is not a real session.
MIN_SYMBOLS_PER_DAY = 20


@dataclass
class Check:
    name: str
    passed: bool
    severity: str  # 'fail' | 'warn'
    observed: str
    detail: dict


def limit_sql() -> str:
    """SQL for the daily price limit in force on a given row's date and exchange.

    Built from config rather than hard-coded: HOSE widened from 5% to 7% and HNX
    from 7% to 10% on 2013-01-15, inside our research window, so using today's
    limit would wrongly excuse two years of real violations and wrongly flag
    none of them.
    """
    rules = yaml.safe_load(MARKET_RULES.read_text())["price_limits"]
    cases = []
    for exchange, periods in rules.items():
        # Latest effective date first, so the first matching WHEN wins.
        for period in sorted(periods, key=lambda r: r["from"], reverse=True):
            cases.append(
                f"WHEN exchange = '{exchange}' AND trade_date >= "
                f"DATE '{period['from']}' THEN {period['limit']}"
            )
    return "CASE " + " ".join(cases) + " ELSE 0.07 END"


def tick_sql(price_col: str) -> str:
    """SQL for the tick size at a given price AND date, in thousands of VND.

    Date matters as much as price. HOSE cut its steps on 2016-09-12: before
    that a share under 50,000 VND moved in 100 VND jumps, so at 600 VND one
    tick was 16.7 percent of the price. A percentage limit check that ignores
    this reports thousands of phantom violations on cheap stocks in the early
    years -- which is exactly what the first version of this check did.
    """
    regimes = yaml.safe_load(MARKET_RULES.read_text())["tick_size"]
    cases = []
    for exchange, periods in regimes.items():
        # Latest regime first so the first matching WHEN wins.
        for regime in sorted(periods, key=lambda r: r["from"], reverse=True):
            for band in regime["bands"]:
                cond = (
                    f"exchange = '{exchange}' AND trade_date >= "
                    f"DATE '{regime['from']}'"
                )
                if band["under"] is not None:
                    cond += f" AND {price_col} < {band['under']}"
                cases.append(f"WHEN {cond} THEN {band['tick']}")
    return "CASE " + " ".join(cases) + " ELSE 0.1 END"


def first_day_limit_sql() -> str:
    """The wider band that applies on a first trading day or a resumption.

    Not a violation, a different rule: a newly listed share may move 20 percent
    on HOSE, 30 on HNX and 40 on UPCoM, and a security resuming after a long
    suspension comes back under the same band.
    """
    rules = yaml.safe_load(MARKET_RULES.read_text())["first_day_limits"]
    cases = [
        f"WHEN exchange = '{ex}' THEN {value}"
        for ex, value in rules.items()
        if ex != "resumption_after_sessions"
    ]
    return "CASE " + " ".join(cases) + " ELSE 0.20 END"


def resumption_sessions() -> int:
    rules = yaml.safe_load(MARKET_RULES.read_text())["first_day_limits"]
    return int(rules["resumption_after_sessions"])


def _one(cur, sql: str, params: tuple = ()) -> tuple:
    cur.execute(sql, params)
    return cur.fetchone()


def run_all(conn, build_id: int) -> list[Check]:
    checks: list[Check] = []
    with conn.cursor() as cur:
        # --- structural ----------------------------------------------------
        (n_raw,) = _one(cur, "SELECT count(*) FROM bar_raw")
        checks.append(
            Check(
                "bar_raw_not_empty",
                n_raw > 0,
                "fail",
                f"{n_raw:,} rows",
                {"rows": n_raw},
            )
        )

        (n_adj,) = _one(
            cur, "SELECT count(*) FROM bar_adjusted WHERE build_id = %s", (build_id,)
        )
        # Every raw bar with a factor must have produced exactly one adjusted
        # bar. A shortfall means the join dropped rows silently.
        (n_fac,) = _one(
            cur,
            "SELECT count(*) FROM adjustment_factor WHERE build_id = %s",
            (build_id,),
        )
        checks.append(
            Check(
                "adjusted_bars_match_factors",
                n_adj == n_fac,
                "fail",
                f"{n_adj:,} adjusted vs {n_fac:,} factors",
                {"adjusted": n_adj, "factors": n_fac},
            )
        )

        # --- the single most important adjustment check ---------------------
        # Traded value is invariant under adjustment: price x factor multiplied
        # by volume / factor is unchanged. If this fails, blocker G1 was done
        # wrong and every volume measure downstream is wrong with it.
        (n_bad_value,) = _one(
            cur,
            """
            SELECT count(*)
            FROM bar_adjusted a
            JOIN bar_raw r ON r.symbol = a.symbol AND r.trade_date = a.trade_date
            WHERE a.build_id = %s
              AND r.matched_volume > 0
              AND abs(a.close * a.matched_volume - r.close * r.matched_volume)
                  > 0.000001 * abs(r.close * r.matched_volume)
            """,
            (build_id,),
        )
        checks.append(
            Check(
                "traded_value_invariant_under_adjustment",
                n_bad_value == 0,
                "fail",
                f"{n_bad_value:,} rows where adjusted value != raw value",
                {"rows": n_bad_value},
            )
        )

        # --- factors --------------------------------------------------------
        # A factor above 1 would mean the adjusted price is HIGHER than what
        # actually traded, which no dividend or split produces.
        # Blocking only inside the research window. Data before 2012 is stored
        # but never measured on, so a pre-2012 oddity must be visible without
        # blocking a build that research would never touch.
        (n_gt1_window,) = _one(
            cur,
            "SELECT count(*) FROM adjustment_factor WHERE build_id = %s "
            "AND factor > 1.0001 AND trade_date >= DATE '2012-01-01'",
            (build_id,),
        )
        checks.append(
            Check(
                "factor_never_above_one_in_research_window",
                n_gt1_window == 0,
                "fail",
                f"{n_gt1_window:,} factors > 1 since 2012",
                {"rows": n_gt1_window},
            )
        )
        cur.execute(
            "SELECT count(*), count(DISTINCT symbol) FROM adjustment_factor "
            "WHERE build_id = %s AND factor > 1.0001",
            (build_id,),
        )
        n_gt1, n_gt1_sym = cur.fetchone()
        checks.append(
            Check(
                "factor_never_above_one_whole_history",
                n_gt1 == 0,
                "warn",
                f"{n_gt1:,} factors > 1 across {n_gt1_sym} symbol(s), all pre-2012",
                {"rows": n_gt1, "symbols": n_gt1_sym},
            )
        )

        # On a symbol's most recent day nothing is left to adjust for, so the
        # factor must be 1. A drift here means the two CafeF files disagree.
        (n_last_not_one,) = _one(
            cur,
            """
            SELECT count(*) FROM (
                SELECT DISTINCT ON (f.symbol) f.symbol, f.factor
                FROM adjustment_factor f
                WHERE f.build_id = %s
                ORDER BY f.symbol, f.trade_date DESC
            ) t WHERE abs(factor - 1) > 0.001
            """,
            (build_id,),
        )
        checks.append(
            Check(
                "factor_is_one_on_latest_day",
                n_last_not_one == 0,
                "warn",
                f"{n_last_not_one:,} symbols whose latest factor != 1",
                {"symbols": n_last_not_one},
            )
        )

        # --- calendar (blocker G14) -----------------------------------------
        (n_we,) = _one(
            cur,
            "SELECT count(*) FROM trading_day "
            "WHERE extract(isodow FROM trade_date) > 5",
        )
        checks.append(
            Check(
                "calendar_has_no_weekend_sessions",
                n_we == 0,
                "fail",
                f"{n_we} weekend sessions",
                {"rows": n_we},
            )
        )

        (n_idx_we,) = _one(
            cur,
            "SELECT count(*) FROM index_bar WHERE extract(isodow FROM trade_date) > 5",
        )
        checks.append(
            Check(
                "index_has_no_weekend_rows",
                n_idx_we == 0,
                "fail",
                f"{n_idx_we} weekend index rows",
                {"rows": n_idx_we},
            )
        )

        (n_thin,) = _one(
            cur,
            "SELECT count(*) FROM trading_day WHERE symbols_traded < %s",
            (MIN_SYMBOLS_PER_DAY,),
        )
        checks.append(
            Check(
                "sessions_have_a_plausible_number_of_symbols",
                n_thin == 0,
                "warn",
                f"{n_thin:,} exchange-days with < {MIN_SYMBOLS_PER_DAY} symbols",
                {"rows": n_thin, "threshold": MIN_SYMBOLS_PER_DAY},
            )
        )

        # --- price limits ----------------------------------------------------
        # A move beyond the limit in UNADJUSTED prices is the signature of a
        # corporate action. It is only suspicious when the factor did NOT change
        # on the same day -- that combination means either bad data or an event
        # nobody adjusted for.
        #
        # The comparison uses the limit IN FORCE on that date plus one tick, so
        # neither the 2013 rule change nor cheap-stock tick granularity produces
        # phantom violations.
        cur.execute(
            f"""
            WITH moves AS (
                SELECT r.symbol, r.trade_date, r.exchange, r.close,
                       lag(r.close) OVER w AS prev_close,
                       r.close / lag(r.close) OVER w - 1 AS move,
                       f.factor,
                       lag(f.factor) OVER w AS prev_factor,
                       row_number() OVER w AS n,
                       lag(r.trade_date) OVER w AS prev_date
                FROM bar_raw r
                JOIN adjustment_factor f
                  ON f.symbol = r.symbol AND f.trade_date = r.trade_date
                 AND f.build_id = %s
                WHERE r.trade_date >= DATE '2012-01-01'
                  -- Backfilled spans are ALREADY adjusted, so this test does
                  -- not apply to them: its premise is "an unadjusted price
                  -- gapped and no factor changed". An adjusted series has the
                  -- corporate-action gaps removed by construction, and at the
                  -- low prices a long adjustment produces (ACB's 2006 close
                  -- adjusts to a couple of thousand VND) two-decimal rounding
                  -- alone can push a legal 7 percent move past the limit.
                  -- (No stray per-cent signs in this comment: psycopg reads
                  -- them as parameter placeholders.) Including
                  -- them added 1,916 phantom violations.
                  AND NOT r.is_adjusted_source
                WINDOW w AS (PARTITION BY r.symbol ORDER BY r.trade_date)
            )
            SELECT count(*) FROM moves
            WHERE move IS NOT NULL AND prev_close > 0
              -- A first trading day and a resumption after a long suspension
              -- come under a WIDER band (20/30/40 percent), so they are not
              -- violations at all -- they are a different rule. 35 calendar
              -- days stands in for the 25-session threshold; the calendar
              -- table could give the exact count, but the classes either side
              -- of this boundary are already separated in the investigation.
              AND abs(move) > CASE
                    WHEN n <= 2
                      OR prev_date < trade_date - INTERVAL '35 days'
                    THEN ({first_day_limit_sql()})
                    ELSE ({limit_sql()})
                  END
                  + ({tick_sql("prev_close")}) / prev_close
              AND abs(factor - prev_factor) < 0.000001
            """,
            (build_id,),
        )
        (n_limit,) = cur.fetchone()
        checks.append(
            Check(
                "moves_beyond_price_limit_without_a_factor_change",
                n_limit == 0,
                "warn",
                f"{n_limit:,} symbol-days since 2012 (limit in force + 1 tick)",
                {"rows": n_limit},
            )
        )

        # Bars the source dated on a non-trading day and the loader moved back.
        # Real data with a wrong date, but worth watching: a rising count means
        # the publisher's dating is getting less reliable.
        (n_shift,) = _one(cur, "SELECT count(*) FROM bar_raw WHERE date_shifted")
        checks.append(
            Check(
                "bars_moved_off_a_weekend_date",
                n_shift == 0,
                "warn",
                f"{n_shift:,} bars were published on a weekend and moved back",
                {"rows": n_shift},
            )
        )

        # --- coverage ---------------------------------------------------------
        # Sessions a symbol missed while it was listed. Not automatically wrong
        # (suspensions happen) but a pattern spanning a hole measures a move over
        # the wrong number of days.
        cur.execute(
            """
            WITH cal AS (
                SELECT DISTINCT trade_date FROM trading_day
                WHERE trade_date >= DATE '2012-01-01'
            ),
            span AS (
                SELECT symbol, min(trade_date) lo, max(trade_date) hi
                FROM bar_raw WHERE trade_date >= DATE '2012-01-01'
                GROUP BY symbol HAVING count(*) > 250
            ),
            transfer_gap AS (
                -- The days between leaving one exchange and joining the next
                -- are a real non-trading period, not missing data (116 Class A
                -- symbols). Excused here so this check agrees with
                -- scripts/investigate_warnings.py instead of reporting a
                -- different number for the same thing.
                SELECT e1.symbol, e1.valid_to AS gap_from, e2.valid_from AS gap_to
                FROM symbol_exchange e1
                JOIN symbol_exchange e2
                  ON e2.symbol = e1.symbol AND e2.valid_from > e1.valid_to
            )
            SELECT count(*) FROM (
                SELECT s.symbol, count(*) AS missing
                FROM span s JOIN cal c ON c.trade_date BETWEEN s.lo AND s.hi
                LEFT JOIN bar_raw b
                       ON b.symbol = s.symbol AND b.trade_date = c.trade_date
                WHERE b.symbol IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM transfer_gap t
                      WHERE t.symbol = s.symbol
                        AND c.trade_date > t.gap_from AND c.trade_date < t.gap_to
                  )
                GROUP BY s.symbol HAVING count(*) > 20
            ) t
            """
        )
        (n_gappy,) = cur.fetchone()
        checks.append(
            Check(
                "symbols_with_many_missing_sessions",
                n_gappy == 0,
                "warn",
                f"{n_gappy:,} symbols missing > 20 sessions inside their listed range",
                {"symbols": n_gappy},
            )
        )

        # The index trades every session the market is open, so a session in
        # trading_day with no index row is a defect in OUR data, not a market
        # event. The regime measures already refuse to compute across one; this
        # makes the defect visible instead of merely routed around.
        cur.execute(
            """
            SELECT count(*) FROM (
                SELECT DISTINCT trade_date FROM trading_day
                WHERE trade_date >= DATE '2012-01-01'
            ) c
            LEFT JOIN index_bar b
                   ON b.trade_date = c.trade_date AND b.symbol = 'VNINDEX'
            WHERE b.trade_date IS NULL
            """
        )
        (n_missing_index,) = cur.fetchone()
        checks.append(
            Check(
                "index_covers_every_trading_session",
                n_missing_index == 0,
                "warn",
                f"{n_missing_index:,} sessions since 2012 have no VNINDEX row",
                {"rows": n_missing_index},
            )
        )

        # --- research window --------------------------------------------------
        (n_window, lo, hi) = _one(
            cur,
            "SELECT count(*), min(trade_date), max(trade_date) FROM bar_adjusted "
            "WHERE build_id = %s AND trade_date >= DATE '2012-01-01'",
            (build_id,),
        )
        checks.append(
            Check(
                "research_window_populated",
                n_window > 1_000_000,
                "fail",
                f"{n_window:,} rows, {lo} -> {hi}",
                {"rows": n_window, "from": str(lo), "to": str(hi)},
            )
        )

        # --- negotiated volume: absence must stay absence ---------------------
        # If this ever equals the bar count, someone has back-filled zeros and
        # destroyed the distinction between "no block trade" and "unknown".
        (n_deal,) = _one(cur, "SELECT count(*) FROM negotiated_volume")
        checks.append(
            Check(
                "negotiated_volume_is_sparse_not_backfilled",
                n_deal > 0,
                "warn",
                f"{n_deal:,} rows published by CafeF (absence = unknown)",
                {"rows": n_deal},
            )
        )

    return checks


def store(conn, build_id: int, checks: list[Check]) -> None:
    with conn.cursor() as cur:
        for c in checks:
            cur.execute(
                """
                INSERT INTO quality_check
                    (build_id, name, passed, severity, observed, detail)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (build_id, c.name, c.passed, c.severity, c.observed, _json(c.detail)),
            )
    conn.commit()


def _json(d: dict) -> str:
    import json

    return json.dumps(d, default=str)


def blocking_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.severity == "fail" and not c.passed]
