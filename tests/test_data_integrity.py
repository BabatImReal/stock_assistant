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


def test_the_latest_industry_snapshot_labels_the_traded_market(conn):
    """Sector measures are only as good as the membership behind them. Nearly
    every symbol that traded on the latest session must have a label in the
    latest snapshot; a new listing between snapshots may briefly lack one."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), count(i.symbol) FROM (
                SELECT DISTINCT symbol FROM bar_raw
                WHERE matched_volume > 0
                  AND trade_date = (SELECT max(trade_date) FROM trading_day)
            ) t
            LEFT JOIN symbol_industry i ON i.symbol = t.symbol
             AND i.snapshot_date = (SELECT max(snapshot_date) FROM symbol_industry)
            """
        )
        traded, labelled = cur.fetchone()
    assert traded and labelled / traded >= 0.99


def _factors_above_one(cur) -> int:
    from vnstock_research.features.bars import current_build

    cur.execute(checks.FACTOR_ABOVE_ONE_SQL, {"build": current_build(cur.connection)})
    return cur.fetchone()[0]


def test_the_promoted_build_has_no_unexplained_factor_above_one(conn):
    """G17. A factor above 1 means an adjusted price HIGHER than what traded,
    which no dividend or split produces. The only exemption: backfill-seam
    rescale factors, tagged source='seam_rescale' AND sitting on a backfilled
    vnstock bar. Failed with 15,670 rows before the 2026-09-23 fix."""
    with conn.cursor() as cur:
        assert _factors_above_one(cur) == 0


def test_the_exemption_covers_nothing_but_tagged_seam_rescales(conn):
    """Any OTHER factor above 1 must still fail the gate: an untagged one, or a
    tagged one on a bar that is not a vnstock backfill. Checked inside a
    transaction that is always rolled back."""
    from vnstock_research.features.bars import current_build

    build = current_build(conn)
    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute(
            "SELECT f.symbol, f.trade_date FROM adjustment_factor f "
            "JOIN bar_raw r USING (symbol, trade_date) "
            "WHERE f.build_id = %s AND r.source = 'cafef' "
            "AND f.trade_date >= DATE '2012-01-01' LIMIT 2",
            (build,),
        )
        (s1, d1), (s2, d2) = cur.fetchall()
        before = _factors_above_one(cur)
        cur.execute(
            "UPDATE adjustment_factor SET factor = 1.5, source = 'cafef' "
            "WHERE symbol = %s AND trade_date = %s AND build_id = %s", (s1, d1, build),
        )
        cur.execute(
            "UPDATE adjustment_factor SET factor = 1.5, source = 'seam_rescale' "
            "WHERE symbol = %s AND trade_date = %s AND build_id = %s", (s2, d2, build),
        )
        assert _factors_above_one(cur) == before + 2


def test_no_session_and_no_bar_falls_on_a_listed_holiday(conn):
    """A stray row on a closed day creates a phantom session (the 2025-05-02
    class). Real data first, then an injected row inside a rolled-back
    transaction must be caught by the same query."""
    days = [d for _, d in checks.holiday_list()]
    with conn.cursor() as cur:
        cur.execute(checks.HOLIDAY_SESSIONS_SQL, {"days": days})
        assert cur.fetchone() == (0, 0)
    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO bar_raw (symbol, trade_date, open, high, low, close, "
            "matched_volume, exchange, source) "
            "VALUES ('VNM', DATE '2024-02-12', 1, 1, 1, 1, 100, 'HOSE', 'cafef')"
        )
        cur.execute(
            "INSERT INTO trading_day (trade_date, exchange, symbols_traded) "
            "VALUES (DATE '2024-02-12', 'HOSE', 1)"
        )
        cur.execute(checks.HOLIDAY_SESSIONS_SQL, {"days": days})
        assert cur.fetchone() == (1, 1)


def test_no_index_session_repeats_the_previous_one_since_2012(conn):
    """A full OHLC tuple identical to the previous session's is a stale copy
    (CafeF 2026-07-31 carried 07-30's prices; 2023-05-08 HNX carried 05-09's).
    Failed with 3 rows before the 2026-09-23 repair."""
    with conn.cursor() as cur:
        cur.execute(checks.INDEX_REPEATED_SQL)
        assert cur.fetchone()[0] == 0


def _resolved(cur, symbol, day):
    from vnstock_research.data import exchanges

    # The first bar on or after `day`: thin symbols do not trade every day.
    cur.execute(
        f"SELECT xm.exchange FROM bar_raw r {exchanges.RESOLVE_JOIN_SQL} "
        "WHERE r.symbol = %s AND r.trade_date = (SELECT min(trade_date) FROM "
        "bar_raw WHERE symbol = %s AND trade_date >= %s)",
        (symbol, symbol, day),
    )
    row = cur.fetchone()
    assert row is not None, f"no bar for {symbol} {day}"
    return row[0]


def test_exchange_membership_dates_the_known_cases(conn):
    """Real cases the dated membership must get right (None = not dated)."""
    with conn.cursor() as cur:
        assert _resolved(cur, "DPG", "2017-06-01") is None  # filed HSX, on HNX then
        assert _resolved(cur, "DPG", "2019-01-02") == "HOSE"  # KBS: from 2018-05-22
        assert _resolved(cur, "ACB", "2015-06-01") is None  # vnstock backfill, pre-move
        assert _resolved(cur, "ACB", "2021-06-01") == "HOSE"
        assert _resolved(cur, "VNM", "2015-06-01") == "HOSE"  # listed 2006, never moved
        # G4 Class A: UPCoM 2021-08-04..2022-09-27, then HOSE from 2022-10-10.
        assert _resolved(cur, "ACG", "2022-06-01") == "UPCOM"
        assert _resolved(cur, "ACG", "2023-06-01") == "HOSE"
        assert _resolved(cur, "SHB", "2015-06-01") is None  # backfill; KBS date = move
        assert _resolved(cur, "SHB", "2022-06-01") == "HOSE"
        assert _resolved(cur, "MHL", "2015-06-01") is None  # KBS contradicted (rule A)


def test_the_python_and_sql_resolvers_agree(conn):
    """The gate resolves in SQL, the backtest in pandas: they must never drift."""
    from vnstock_research.data import exchanges

    spans = exchanges.load(conn)
    with conn.cursor() as cur:
        for symbol in ("DPG", "ACB", "ACG", "VNM", "SHB", "VIX", "MHL", "HBC",
                       "PXL", "ITA"):
            cur.execute(
                f"SELECT r.trade_date, r.exchange, xm.exchange, r.source "
                f"FROM bar_raw r "
                f"{exchanges.RESOLVE_JOIN_SQL} WHERE r.symbol = %s "
                "AND r.trade_date >= DATE '2012-01-01' ORDER BY 1",
                (symbol,),
            )
            rows = cur.fetchall()
            py = exchanges.resolve(spans, symbol, [r[0] for r in rows],
                                   [r[1] for r in rows],
                                   [r[3] == "vnstock" for r in rows])
            sql_known = [r[2] for r in rows]
            assert py["exchange_unknown"].tolist() == [k is None for k in sql_known]
            assert [e for e, k in zip(py["exchange"], sql_known, strict=True) if k] \
                == [k for k in sql_known if k]



def test_no_transfer_dates_pre_move_history_with_the_current_exchange(conn):
    """The load-bearing assumption, over the WHOLE transfer set, not samples.

    1. G4 Class B: every vnstock backfill row is pre-transfer by construction,
       so none may be dated (KBS sometimes reports the ORIGINAL listing date;
       3,136 rows on 17 symbols were dated before rule B).
    2. Every symbol KBS shows moving inside its history: no row before its
       listing_date is dated, unless a CafeF-documented span dates it.
    3. G4 Class A: every CafeF-filed row resolves, dated, to the exchange it
       was filed under, except the three stray one-day HOSE filings on
       2015-09-01 (PXL, VLF, VNA), which the longer UPCoM span outranks.
    """
    from vnstock_research.data import exchanges

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT count(*) FROM bar_raw r {exchanges.RESOLVE_JOIN_SQL} "
            "WHERE r.source = 'vnstock' AND xm.exchange IS NOT NULL"
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            f"""
            SELECT count(*) FROM bar_raw r
            JOIN exchange_membership k
              ON k.symbol = r.symbol AND k.source = 'kbs_listing'
             AND r.trade_date < k.valid_from
            {exchanges.RESOLVE_JOIN_SQL}
            WHERE xm.exchange IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM exchange_membership t
                WHERE t.symbol = r.symbol AND t.source = 'cafef_transfer'
                  AND r.trade_date BETWEEN t.valid_from AND t.valid_to)
            """
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            f"""
            SELECT r.symbol, r.trade_date FROM bar_raw r
            {exchanges.RESOLVE_JOIN_SQL}
            WHERE r.source = 'cafef' AND EXISTS (
                SELECT 1 FROM exchange_membership t
                WHERE t.symbol = r.symbol AND t.source = 'cafef_transfer')
              AND xm.exchange IS DISTINCT FROM r.exchange
            ORDER BY 1
            """
        )
        odd = {(sym, str(d)) for sym, d in cur.fetchall()}
    assert odd == {("PXL", "2015-09-01"), ("VLF", "2015-09-01"),
                   ("VNA", "2015-09-01")}


def test_a_flagged_exchange_day_lands_in_the_gates_flagged_count(conn):
    """The gate's price-limit check keeps undated-exchange violations apart:
    a big move on a DPG day before its KBS listing (2018-05-22) must raise the
    FLAGGED count and leave the dated one alone, and vice versa after it."""
    from vnstock_research.features.bars import current_build

    build = current_build(conn)
    params = {"build": build, "symbols": ["DPG"]}

    def flat_factor_day(cur, after):
        # A day whose factor equals its neighbours' exactly: the check skips a
        # day whose factor "changed", and CafeF's factor jitters with rounding
        # (open-questions G19), so the injected move must land on a flat one.
        cur.execute(
            "SELECT trade_date FROM (SELECT trade_date, factor, lag(factor) "
            "OVER w pf, lead(factor) OVER w nf FROM adjustment_factor WHERE "
            "symbol = 'DPG' AND build_id = %s WINDOW w AS (ORDER BY trade_date)) x "
            "WHERE trade_date > %s AND factor = pf AND factor = nf "
            "ORDER BY 1 LIMIT 1",
            (build, after),
        )
        return cur.fetchone()[0]

    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute(checks.price_limit_sql(), params)
        dated0, flagged0 = cur.fetchone()
        cur.execute(
            "UPDATE bar_raw SET close = close * 1.4, high = greatest(high, "
            "close * 1.4) WHERE symbol = 'DPG' AND trade_date = %s",
            (flat_factor_day(cur, "2017-06-01"),),
        )
        cur.execute(checks.price_limit_sql(), params)
        dated1, flagged1 = cur.fetchone()
        assert flagged1 > flagged0 and dated1 == dated0
        cur.execute(
            "UPDATE bar_raw SET close = close * 1.4, high = greatest(high, "
            "close * 1.4) WHERE symbol = 'DPG' AND trade_date = %s",
            (flat_factor_day(cur, "2019-06-01"),),
        )
        cur.execute(checks.price_limit_sql(), params)
        dated2, flagged2 = cur.fetchone()
        assert dated2 > dated1 and flagged2 == flagged1


def test_g3_fillability_on_real_dpg_is_quarantined_before_its_listing(conn):
    """End to end on real bars: raw DPG, the resolved exchange, G3
    fillability, then the quarantine gate. Blank exactly before 2018-05-22."""
    import datetime as dt

    import pandas as pd

    from vnstock_research.backtest import forward_returns as fr
    from vnstock_research.data import exchanges
    from vnstock_research.features import quarantine_flagged

    with conn.cursor() as cur:
        cur.execute(
            "SELECT trade_date, open, close, exchange, source FROM bar_raw "
            "WHERE symbol = 'DPG' AND trade_date BETWEEN '2018-01-01' AND "
            "'2018-12-31' ORDER BY 1"
        )
        bars = pd.DataFrame(cur.fetchall(),
                            columns=["trade_date", "open", "close", "filed", "source"])
    bars[["open", "close"]] = bars[["open", "close"]].astype(float)
    r = exchanges.resolve(exchanges.load(conn), "DPG", bars["trade_date"],
                          bars["filed"], bars["source"] == "vnstock")
    bars["exchange"] = r["exchange"].to_numpy()
    bars["exchange_unknown"] = r["exchange_unknown"].to_numpy()
    clean = quarantine_flagged(fr.fillability(bars), fr.FILLABILITY)
    before = (bars["trade_date"] < dt.date(2018, 5, 22)).to_numpy()
    assert clean["limit"][before].isna().all()
    assert clean["limit"][~before].notna().all()



def test_rebuild_drops_a_kbs_span_the_cafef_filing_contradicts(conn):
    """Rule A, run for real and rolled back: MHL is filed HNX 2009-2023 while
    KBS says "UPCoM since 2009", so its KBS span must not survive the rebuild."""
    from vnstock_research.data import exchanges

    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        counts = exchanges.rebuild(conn, commit=False)
        cur.execute("SELECT count(*) FROM exchange_membership "
                    "WHERE symbol = 'MHL' AND source = 'kbs_listing'")
        assert cur.fetchone()[0] == 0
    assert counts["kbs_dropped_contradicted"] >= 1


def test_the_gate_judges_a_move_by_the_dated_exchange_not_the_filed_one(conn):
    """A +10% move breaks HOSE's 7% limit but not UPCoM's 15%. DPG is filed
    HOSE; give one 2019 day a documented UPCoM span (rolled back) and the
    same move must stop counting as a violation."""
    from vnstock_research.features.bars import current_build

    build = current_build(conn)
    params = {"build": build, "symbols": ["DPG"]}
    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute(
            "SELECT trade_date FROM (SELECT trade_date, factor, lag(factor) "
            "OVER w pf, lead(factor) OVER w nf FROM adjustment_factor WHERE "
            "symbol = 'DPG' AND build_id = %s WINDOW w AS (ORDER BY trade_date)) x "
            "WHERE trade_date > '2019-06-01' AND factor = pf AND factor = nf "
            "ORDER BY 1 LIMIT 1",
            (build,),
        )
        day = cur.fetchone()[0]
        cur.execute(
            "UPDATE bar_raw SET close = close * 1.10, high = greatest(high, "
            "close * 1.10) WHERE symbol = 'DPG' AND trade_date = %s",
            (day,),
        )
        cur.execute(checks.price_limit_sql(), params)
        as_hose, _ = cur.fetchone()
        cur.execute(
            "INSERT INTO exchange_membership VALUES "
            "('DPG', 'UPCOM', %s::date - 10, %s::date + 10, 'cafef_transfer')",
            (day, day),
        )
        cur.execute(checks.price_limit_sql(), params)
        as_upcom, _ = cur.fetchone()
    assert as_hose > as_upcom
