"""The nightly job's index step (G16) and its daily industry snapshot.

The DB tests run inside transactions that are always rolled back, and the
wiring test gives main() a connection whose commits are swallowed and which
rolls back on close. So nothing here leaves a row behind.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

from vnstock_research.data import cafef, db, sectors

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import nightly_update  # noqa: E402

HEADER = "<Ticker>,<DTYYYYMMDD>,<Open>,<High>,<Low>,<Close>,<Volume>\n"


def daily_dir(tmp_path, day="20300102", extra=""):
    (tmp_path / "CafeF.INDEX.02.01.2030.csv").write_text(
        HEADER
        + f"VNINDEX,{day},1800,1810,1790,1805,400000000\n"
        + f"HNX-INDEX,{day},270,272,269,271,40000000\n"
        + extra,
        encoding="utf-8-sig",
    )
    return tmp_path


@pytest.fixture
def conn():
    try:
        c = db.connect()
    except Exception as e:  # noqa: BLE001 - any connection problem means skip
        pytest.skip(f"no database: {type(e).__name__}")
    yield c
    c.close()


def test_the_daily_index_file_is_parsed_and_the_history_file_is_not(tmp_path):
    d = daily_dir(tmp_path, extra="VNINDEX,20300105,1,1,1,1,1\n")  # a Saturday
    (tmp_path / "CafeF.INDEX.Upto02.01.2030.csv").write_text(HEADER, "utf-8-sig")
    df = cafef.index_bars(d, cafef.DAILY_INDEX_FILE)
    assert sorted(df["symbol"]) == ["HNX-INDEX", "VNINDEX"]  # weekend row dropped
    assert set(df["trade_date"]) == {dt.date(2030, 1, 2)}


def count_index(cur, day):
    cur.execute("SELECT count(*) FROM index_bar WHERE trade_date = %s", (day,))
    return cur.fetchone()[0]


def test_the_nightly_writes_the_sessions_index_rows(conn, tmp_path):
    """G16: the docstring promised the index, and nothing wrote it."""
    d = daily_dir(tmp_path)
    day = dt.date(2030, 1, 2)
    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        assert nightly_update.write_index(conn, d, after=dt.date(2029, 12, 31)) == 2
        assert count_index(cur, day) == 2
        # Idempotent: a re-run of the same session adds nothing.
        nightly_update.write_index(conn, d, after=dt.date(2029, 12, 31))
        assert count_index(cur, day) == 2
        # Only sessions after what the database already holds.
        assert nightly_update.write_index(conn, d, after=day) == 0


def test_the_industry_snapshot_is_idempotent_per_day(conn):
    snap = pd.DataFrame(
        {
            "symbol": ["VCB", "HPG"],
            "icb_l2": ["8300", "1700"],
            "icb_l2_name": ["Banks", "Basic resources"],
            "icb_l4": ["8355", "1757"],
            "icb_l4_name": ["Banks", "Steel"],
        }
    )
    day = dt.date(2030, 1, 1)
    with conn.transaction(force_rollback=True):
        assert sectors.write_snapshot(conn, snap, day) == 2
        assert sectors.write_snapshot(conn, snap, day) == 2


class NoCommit:
    """A real connection for main(), minus the ability to persist anything."""

    def __init__(self, c):
        self._c = c

    def __getattr__(self, name):
        return getattr(self._c, name)

    def commit(self):
        pass

    def close(self):
        self._c.rollback()
        self._c.close()


def test_the_nightly_takes_the_snapshot_on_every_run(conn, monkeypatch, tmp_path):
    """Dated sector labels only accumulate if every run snapshots, including a
    run where the source has no new session."""
    calls = []
    real_connect = db.connect  # patched below; the same module object
    monkeypatch.setattr(nightly_update.db, "connect", lambda: NoCommit(real_connect()))
    monkeypatch.setattr(nightly_update, "refresh_labels", lambda c: calls.append(c))
    monkeypatch.setattr(nightly_update, "newest_publication", lambda: ("01012000", {}))
    monkeypatch.setattr(nightly_update, "REPORTS", tmp_path)
    assert nightly_update.main() == 0  # no new session: nothing appended
    assert len(calls) == 1
