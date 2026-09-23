"""Checks that need the live database.

These exist because of a specific failure: bar_raw.date_shifted was added,
populated in the loader, and never actually written -- the edit adding it to the
COPY column list did not apply, and every row silently stayed false. Nothing
caught it, because no check asserted the flag was ever true.

CLAUDE.md now requires every fix to be proven by something that fails without
it. That is what these are.

Skipped cleanly when no database is reachable, so the normal test run does not
depend on Docker being up.
"""

import pytest

from vnstock_research.data import checks, db


@pytest.fixture(scope="module")
def conn():
    try:
        connection = db.connect()
    except Exception as e:  # noqa: BLE001 - any connection problem means skip
        pytest.skip(f"no database: {type(e).__name__}")
    yield connection
    connection.close()


def test_date_shifted_flag_is_actually_written(conn):
    """The regression test for the invisible-repair bug.

    Fails if the loader moves bars off a non-trading date without recording it.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM bar_raw WHERE date_shifted")
        (shifted,) = cur.fetchone()
    assert shifted > 0, (
        "no bar is flagged date_shifted. Either the source published none, or "
        "the loader is repairing dates without recording it -- which is the bug "
        "this test exists to catch."
    )


def test_no_bar_survives_on_a_weekend(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM bar_raw WHERE extract(isodow FROM trade_date) > 5"
        )
        (weekend,) = cur.fetchone()
    assert weekend == 0


def test_shifted_bars_are_excluded_by_the_research_default(conn):
    # config says research excludes them; this proves the flag can actually
    # express that, i.e. the two sets are different.
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM bar_raw")
        (total,) = cur.fetchone()
        cur.execute("SELECT count(*) FROM bar_raw WHERE NOT date_shifted")
        (research,) = cur.fetchone()
    assert research < total


def test_price_limit_sql_uses_the_rule_in_force(conn):
    # The 2013-01-15 widening sits inside the research window, so a check built
    # on today's limits would be wrong for 2012.
    sql = checks.limit_sql()
    assert "2013-01-15" in sql
    assert "0.05" in sql  # the pre-2013 HOSE limit
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {sql}".replace("exchange", "'HOSE'").replace(
                "trade_date", "DATE '2012-06-01'"
            )
        )
        (limit_2012,) = cur.fetchone()
    assert float(limit_2012) == 0.05


def test_calendar_matches_bar_raw(conn):
    """trading_day is DERIVED from bar_raw; it must never drift from it.

    Found 2026-09-23: verify_date_shifts.py deleted bar_raw rows and
    backfill_transfers.py inserted some, and neither re-derived the calendar.
    That left 2025-05-02 -- a public holiday -- in trading_day with no bar behind
    it, inflating gap_before by one for every symbol whose bars straddle it.
    """
    with conn.cursor() as cur:
        cur.execute(checks.CALENDAR_DRIFT_SQL)
        (drift,) = cur.fetchone()
    assert drift == 0, f"{drift} exchange-days differ; run db.rebuild_trading_day"


def test_the_liquid_set_on_the_latest_session_all_traded_that_session(conn):
    """liquid_symbols() is the ONE definition (data/universe.py) applied to the
    latest session. Liquid implies tradeable that day; an empty set would mean
    the config or the window broke."""
    from vnstock_research.features import bars

    liquid = bars.liquid_symbols(conn)
    assert liquid
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol FROM bar_raw WHERE matched_volume > 0 "
            "AND NOT date_shifted "
            "AND trade_date = (SELECT max(trade_date) FROM trading_day)"
        )
        traded = {r[0] for r in cur.fetchall()}
    assert set(liquid) <= traded
