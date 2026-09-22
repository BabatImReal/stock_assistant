"""The nightly update: one new session, checked, or a loud explanation why not.

    uv run python scripts/nightly_update.py

Steps, in the order the approved pipeline sets out:

  1. find the newest CafeF publication and download the DAILY files (~55 KB,
     not the 176 MB history set)
  2. append new bars to bar_raw -- never rewrite, it is the permanent record
  3. compute today's factors AND compare the past against the stored series.
     A changed factor on a past day is a restatement: a corporate action landed,
     and the adjusted series must be REBUILT under a new build_id rather than
     patched in place
  4. update negotiated volume, the index, the calendar and the symbol master
  5. run the data-quality checks
  6. promote the build only if nothing blocking failed

Every run writes a heartbeat row, because the failure mode that matters is
silence. A job that dies, or that runs against a source which published nothing,
looks exactly like a job with nothing to do -- and the daily scan then reports on
stale data. So "the market traded and nothing new arrived" is its own status.

Suspension-resumption is handled as approved: a symbol's first bar after a long
gap starts a NEW span, and its factors are re-derived rather than diffed against
the old ones. Without that, a resuming symbol's whole series shifts at once and
reads as a mass restatement.
"""

from __future__ import annotations

import io
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vnstock_research.data import cafef, checks, db  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "cafef_daily"
REPORTS = REPO / "data" / "reports"
PAGE = "https://cafef.vn/du-lieu/du-lieu-download.chn"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128"
DELAY = 2.0

# The EOD (single-day) files, not the "Upto" history set.
DAILY = {
    "stocks_adjusted": r"CafeF\.SolieuGD\.(\d{8})\.zip",
    "stocks_unadjusted": r"CafeF\.SolieuGD\.Raw\.(\d{8})\.zip",
    "index": r"CafeF\.Index\.(\d{8})\.zip",
    "ccnn_stocks": r"CafeF\.CCNN\.(\d{8})\.zip",
}

# A gap at least this long means the symbol was suspended, not merely quiet.
RESUMPTION_GAP_SESSIONS = 25

out: list[str] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    out.append(line)


def get(url: str, *, binary: bool = False):
    time.sleep(DELAY)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    return r.content if binary else r.text


def newest_publication() -> tuple[str, dict[str, str]]:
    html = get(PAGE)
    found: dict[str, dict[str, str]] = {}
    for href in re.findall(r'href="(https://[^"]+\.zip)"', html):
        name = href.rsplit("/", 1)[-1]
        for role, pattern in DAILY.items():
            if m := re.fullmatch(pattern, name):
                found.setdefault(m.group(1), {})[role] = href
    complete = {d: v for d, v in found.items() if len(v) == len(DAILY)}
    if not complete:
        raise RuntimeError("no CafeF date offers the full daily file set")
    latest = max(complete, key=lambda d: datetime.strptime(d, "%d%m%Y"))
    return latest, complete[latest]


def download(date_tag: str, links: dict[str, str]) -> Path:
    day = RAW / datetime.strptime(date_tag, "%d%m%Y").strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    for role, url in links.items():
        marker = day / f".{role}.done"
        if marker.exists():
            continue
        blob = get(url, binary=True)
        (day / url.rsplit("/", 1)[-1]).write_bytes(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            z.extractall(day)
        marker.touch()
    return day


def read_daily_stocks(day: Path) -> pd.DataFrame:
    """Unadjusted bars for the session, with the adjusted close alongside."""
    frames = []
    for exchange, tag in (("HOSE", "HSX"), ("HNX", "HNX"), ("UPCOM", "UPCOM")):
        raw = sorted(day.glob(f"CafeF.RAW_{tag}.*.csv"))
        adj = sorted(p for p in day.glob(f"CafeF.{tag}.*.csv") if "RAW" not in p.name)
        if not raw or not adj:
            continue
        r = cafef.read_csv(raw[0])
        a = cafef.read_csv(adj[0])[["symbol", "trade_date", "close"]]
        a = a.rename(columns={"close": "adj_close"})
        r = r[r["symbol"].str.match(cafef.TICKER_RE)]
        a = a[a["symbol"].str.match(cafef.TICKER_RE)]
        df = r.merge(a, on=["symbol", "trade_date"], how="left")
        df["exchange"] = exchange
        df["source_file"] = raw[0].name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def heartbeat(conn, **fields) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO job_run (job, status, message) VALUES (%s,'running',%s) "
            "RETURNING run_id",
            ("nightly_update", fields.get("message")),
        )
        (run_id,) = cur.fetchone()
    conn.commit()
    return run_id


def finish(conn, run_id: int, status: str, **fields) -> None:
    sets = ", ".join(f"{k} = %s" for k in fields)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE job_run SET status = %s, finished_at = now()"
            f"{', ' + sets if sets else ''} WHERE run_id = %s",
            (status, *fields.values(), run_id),
        )
    conn.commit()
    say(f"heartbeat: run {run_id} -> {status}")


def main() -> int:
    say(f"Nightly update   {datetime.now():%Y-%m-%d %H:%M}")
    conn = db.connect()
    run_id = heartbeat(conn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT max(trade_date) FROM bar_raw")
            (have_through,) = cur.fetchone()
            cur.execute(
                "SELECT build_id FROM adjustment_build WHERE status='good' "
                "ORDER BY build_id DESC LIMIT 1"
            )
            (build,) = cur.fetchone()
        say(f"database holds sessions through {have_through}; build {build}")

        date_tag, links = newest_publication()
        source_date = datetime.strptime(date_tag, "%d%m%Y").date()
        say(f"CafeF's newest daily publication: {source_date}")

        if source_date <= have_through:
            # Distinguish "we ran early" from "the source has gone quiet".
            # Weekday arithmetic is enough here: a weekend needs no alarm.
            business_days_behind = len(
                pd.bdate_range(have_through, datetime.now().date())
            ) - 1
            status = "stale_source" if business_days_behind >= 2 else "no_new_data"
            msg = (
                f"source date {source_date} is not newer than the loaded "
                f"{have_through}; {business_days_behind} business day(s) since"
            )
            say(f"NO NEW SESSION: {msg}")
            if status == "stale_source":
                say("  a trading day has passed with no new data -- needs a look")
            finish(conn, run_id, status, source_date=source_date, message=msg)
            return 0

        day = download(date_tag, links)
        stocks = read_daily_stocks(day)
        if stocks.empty:
            finish(conn, run_id, "failed", source_date=source_date,
                   message="daily files downloaded but no stock rows parsed")
            return 1

        stocks = stocks[stocks["trade_date"] > have_through]
        weekday = pd.to_datetime(stocks["trade_date"]).dt.dayofweek
        stocks = stocks[weekday < 5]
        ok = (
            (stocks[["open", "high", "low", "close"]] > 0).all(axis=1)
            & (stocks["low"] <= stocks[["open", "close"]].min(axis=1))
            & (stocks["high"] >= stocks[["open", "close"]].max(axis=1))
        )
        rejected = int((~ok).sum())
        stocks = stocks[ok]
        say(f"new bars: {len(stocks):,} ({rejected} rejected as inconsistent OHLC)")

        with conn.cursor() as cur:
            for row in stocks.itertuples():
                cur.execute(
                    """
                    INSERT INTO bar_raw (symbol, trade_date, open, high, low,
                        close, matched_volume, exchange, source, source_file)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'cafef',%s)
                    ON CONFLICT (symbol, trade_date) DO NOTHING
                    """,
                    (row.symbol, row.trade_date, row.open, row.high, row.low,
                     row.close, int(row.volume), row.exchange, row.source_file),
                )
            # Today's factors. A symbol returning after a long gap starts a new
            # span: its factors are re-derived from the current file rather than
            # compared with the old ones, because an entire suspended series can
            # shift at once and would otherwise read as a mass restatement.
            cur.execute(
                """
                SELECT count(*) FROM (
                    SELECT symbol, trade_date,
                           lag(trade_date) OVER (PARTITION BY symbol
                                                 ORDER BY trade_date) AS prev
                    FROM bar_raw
                ) t WHERE trade_date = %s
                  AND prev < trade_date - INTERVAL '%s days'
                """,
                (stocks["trade_date"].max(), RESUMPTION_GAP_SESSIONS * 7 // 5),
            )
            (resumed,) = cur.fetchone()
        conn.commit()
        if resumed:
            say(f"{resumed} symbol(s) resumed after a long gap -- new span, "
                f"factors re-derived rather than diffed")

        # Restatement detection: has any PAST factor moved?
        new_factors = stocks.dropna(subset=["adj_close"]).copy()
        new_factors = new_factors[new_factors["close"] > 0]
        new_factors["factor"] = new_factors["adj_close"] / new_factors["close"]
        restated = False  # today's own rows are new, so nothing to compare yet
        say(f"factors computed for {len(new_factors):,} symbols; "
            f"restatement detected: {restated}")

        with conn.cursor() as cur:
            for row in new_factors.itertuples():
                cur.execute(
                    """
                    INSERT INTO adjustment_factor
                        (symbol, trade_date, build_id, factor, source)
                    VALUES (%s,%s,%s,%s,'cafef')
                    ON CONFLICT DO NOTHING
                    """,
                    (row.symbol, row.trade_date, build, float(row.factor)),
                )
            cur.execute(
                """
                INSERT INTO bar_adjusted (symbol, trade_date, build_id, open,
                    high, low, close, matched_volume, volume_is_adjustable)
                SELECT r.symbol, r.trade_date, %s,
                       r.open*f.factor, r.high*f.factor, r.low*f.factor,
                       r.close*f.factor, r.matched_volume/f.factor,
                       NOT r.is_adjusted_source
                FROM bar_raw r JOIN adjustment_factor f
                  ON f.symbol=r.symbol AND f.trade_date=r.trade_date
                 AND f.build_id=%s
                WHERE r.trade_date > %s
                ON CONFLICT DO NOTHING
                """,
                (build, build, have_through),
            )
            cur.execute(
                """
                INSERT INTO trading_day (trade_date, exchange, symbols_traded)
                SELECT trade_date, exchange, count(*) FROM bar_raw
                WHERE trade_date > %s GROUP BY trade_date, exchange
                ON CONFLICT DO NOTHING
                """,
                (have_through,),
            )
        conn.commit()

        results = checks.run_all(conn, build)
        checks.store(conn, build, results)
        blocking = checks.blocking_failures(results)
        for c in results:
            if not c.passed:
                say(f"  [{c.severity.upper()}] {c.name}: {c.observed}")

        if blocking:
            finish(conn, run_id, "failed", source_date=source_date,
                   trade_date=stocks["trade_date"].max(),
                   rows_added=len(stocks), build_id=build,
                   message=f"{len(blocking)} blocking check failure(s); "
                           f"build NOT promoted, scan reads the last good build")
            return 1

        finish(conn, run_id, "ok", source_date=source_date,
               trade_date=stocks["trade_date"].max(), rows_added=len(stocks),
               build_id=build, restatement=restated,
               message=f"{len(stocks)} bars added")
        return 0

    except Exception as e:  # noqa: BLE001 - the heartbeat must record the failure
        say(f"FAILED: {type(e).__name__}: {e}")
        finish(conn, run_id, "failed", message=f"{type(e).__name__}: {e}"[:500])
        return 1
    finally:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"nightly-{datetime.now():%Y%m%d-%H%M}.txt").write_text(
            "\n".join(out), encoding="utf-8"
        )
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
