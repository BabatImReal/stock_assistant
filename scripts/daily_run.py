"""The daily cycle: load the day, rebuild, scan, record, score. One command.

    uv run python scripts/daily_run.py            # the real run
    uv run python scripts/daily_run.py --print-plist   # show the launchd file

Why this exists. The forward test is only worth something if EVERY trading day is
recorded, and CafeF keeps only ~3 daily files, so a Mac that is off for a few days
used to lose the clock for good. Each run therefore:

  1. takes a lock (a second copy exits), and checks the database answers;
  2. reads CafeF's page and, if it offers a session newer than the database, loads
     it from the cumulative `Upto` files through scripts/catch_up_upto.py. That path
     recovers any outage and detects restatements (the old nightly_update.py price
     append can do neither, so it must NOT be scheduled alongside this);
  3. stores today's dated industry snapshot (never fatal);
  4. if there are trading days not yet in the paper ledger, rebuilds the fingerprint
     and the returns, then scans and RECORDS each missing day in date order. The
     ledger is the checkpoint, so a run that died halfway is finished by the next
     one; a run with nothing to do skips the ten-minute rebuild;
  5. re-records the latest day already in the ledger as a regression guard: the
     ledger is append-only and refuses a different answer, so a rebuild that
     silently changed history fails loudly here instead of corrupting the record;
  6. scores the ledger (only after every day is recorded, never before).

Every run writes a heartbeat row and a log file, and sends a macOS notification on
failure and when a new day was recorded. Silence is the failure mode that matters
(nightly_update.py says so too): a job that dies looks exactly like a quiet day.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parent.parent
UPTO_ROOT = REPO / "data" / "raw" / "cafef_upto"
REPORTS = REPO / "data" / "reports"
LOCK = REPORTS / ".daily_run.lock"
KEEP_FINGERPRINTS = 3  # newest daily fingerprint dirs kept (~213 MB each)
KEEP_UPTO = 2  # extracted cumulative folders to keep (~200 MB each)
# After this many business days with no newer publication, the source has gone
# quiet rather than us running early (same rule as nightly_update.py).
STALE_AFTER = 2

# What the run calls its outcome -> what job_run.status accepts (migration 005).
HEARTBEAT = {
    "loaded": "ok",
    "new": "ok",
    "no_new_data": "no_new_data",
    "not_ready": "no_new_data",
    "stale_source": "stale_source",
    "failed": "failed",
}

UPTO = {
    "stocks_adjusted": r"CafeF\.SolieuGD\.Upto(\d{8})\.zip",
    "stocks_unadjusted": r"CafeF\.SolieuGD\.Raw\.Upto(\d{8})\.zip",
    "index": r"CafeF\.Index\.Upto(\d{8})\.zip",
}


# --- pure helpers (tested) ------------------------------------------------------


def upto_links(html: str) -> tuple[str, dict[str, str]]:
    """(newest date tag DDMMYYYY, role -> url) among dates offering all three files."""
    found: dict[str, dict[str, str]] = {}
    for href in re.findall(r'href="(https://[^"]+\.zip)"', html):
        name = href.rsplit("/", 1)[-1]
        for role, pattern in UPTO.items():
            if m := re.fullmatch(pattern, name):
                found.setdefault(m.group(1), {})[role] = href
    complete = {d: v for d, v in found.items() if len(v) == len(UPTO)}
    if not complete:
        raise RuntimeError("no CafeF date offers the full cumulative Upto file set")
    latest = max(complete, key=lambda d: datetime.strptime(d, "%d%m%Y"))
    return latest, complete[latest]


def source_status(offered: date, have: date, today: date) -> str:
    """'new' | 'no_new_data' | 'stale_source' (a trading day passed with nothing)."""
    if offered > have:
        return "new"
    behind = len(pd.bdate_range(have, today)) - 1
    return "stale_source" if behind >= STALE_AFTER else "no_new_data"


def prune_upto(root: Path, keep: int = KEEP_UPTO) -> list[str]:
    """Delete all but the newest `keep` extracted folders (named YYYY-MM-DD)."""
    dirs = sorted(p for p in root.glob("*/") if p.is_dir())
    gone = dirs[:-keep] if keep else dirs
    for d in gone:
        shutil.rmtree(d)
    return [d.name for d in gone]


def fetch_set(links: dict[str, str], dest: Path, getter) -> bool:
    """Download and extract each file once; False if CafeF lists one it cannot serve.

    CafeF puts links on its page before the files are downloadable (a 404 at 17:00
    on the day itself). That means "not ready, retry later", not a failure to
    shout about. A marker per file lets the retry resume without re-downloading.
    """
    import io
    import zipfile

    import requests

    dest.mkdir(parents=True, exist_ok=True)
    for role, url in links.items():
        marker = dest / f".{role}.done"
        if marker.exists():
            continue
        try:
            blob = getter(url)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False
            raise
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            z.extractall(dest)
        marker.touch()
    return True


def prune_fingerprints(
    root: Path, build: int, registered: set[str], keep: int = KEEP_FINGERPRINTS
) -> list[str]:
    """Delete old daily fingerprint directories; return the names removed.

    The feature-set hash changes with every sector snapshot, so each daily run writes
    a NEW ~213 MB directory and the old ones are never read again. This removes only
    directories that are provably part of that daily series: named `<build>_<hash>`
    for the CURRENT build, with a hash the ledger has recorded. Anything else (the
    structural feature set, other builds' directories, unknown folders, returns,
    backups) is never touched. The newest `keep` (by manifest time) survive.
    """
    series = [
        d
        for d in root.glob(f"{build}_*")
        if d.is_dir() and d.name.split("_", 1)[1] in registered
    ]
    series.sort(
        key=lambda d: (
            (d / "manifest.json").stat().st_mtime
            if (d / "manifest.json").exists()
            else 0
        )
    )
    gone = series[:-keep] if keep else series
    for d in gone:
        shutil.rmtree(d)
    return [d.name for d in gone]


def needs_rebuild(unrecorded_days: list, index_healed: bool) -> bool:
    """Rebuild when days are unrecorded OR index rows were just filled.

    The fingerprint stores the market-regime columns (index_above_ma_50, ...). If a
    VNINDEX row was missing when it was built and is healed later, the stored copy
    keeps NaN for that day until it is rebuilt, and the stored-vs-fresh test fails.
    """
    return bool(unrecorded_days) or index_healed


def refresh_index(links: dict[str, str], dest: Path, getter) -> bool:
    """Re-download the small Index file (always, no marker) into `dest`.

    CafeF's Index file lags its stock files: a day's VNINDEX row can appear hours
    after its stock bars. The run that loaded the stock bars therefore may have a
    stale Index file, and a later run with no new bars must fetch it again. False if
    CafeF lists it but cannot serve it yet (404 = not ready).
    """
    import io
    import zipfile

    import requests

    dest.mkdir(parents=True, exist_ok=True)
    try:
        blob = getter(links["index"])
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return False
        raise
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        z.extractall(dest)  # overwrites the stale copy
    return True


def run_pipeline(steps, log, notify) -> int:
    """Run (name, fn) steps in order; the first failure stops the rest and notifies.

    Each fn may return a short string that is logged. Returns 0 on success.
    """
    for name, fn in steps:
        log(f"--- {name}")
        try:
            msg = fn()
            if msg:
                log(str(msg))
        except Exception as e:  # noqa: BLE001 - the heartbeat must record any failure
            log(f"FAILED at '{name}': {type(e).__name__}: {e}")
            log(traceback.format_exc())
            notify("Stock research: FAILED", f"step '{name}': {type(e).__name__}: {e}")
            return 1
    return 0


class Locked(RuntimeError):
    pass


def take_lock(path: Path, pid: int | None = None) -> None:
    """Refuse a second copy; a lock left by a dead process is taken over."""
    pid = pid or os.getpid()
    if path.exists():
        try:
            other = int(path.read_text().strip())
            os.kill(other, 0)  # raises if that process is gone
            raise Locked(f"another daily_run is running (pid {other})")
        except (ValueError, ProcessLookupError):
            pass  # stale
        except PermissionError as e:  # pid exists but is not ours
            raise Locked(f"lock held by pid in {path}") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def plist(repo: Path, uv: str, docker_dir: str) -> str:
    """The launchd job: weekdays 21:30 and a 23:30 retry, Vietnam local time.

    launchd has a minimal PATH and loads no shell profile, so every path is
    absolute and PATH is set explicitly. The repo path contains a space, so each
    argument is its own <string> and nothing goes through a shell.
    """
    slots = "".join(
        f"""
    <dict><key>Weekday</key><integer>{d}</integer>
    <key>Hour</key><integer>{h}</integer><key>Minute</key><integer>{m}</integer></dict>"""
        for d in range(1, 6)
        for h, m in ((21, 30), (23, 30))
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.vnstock.daily-run</string>
  <key>ProgramArguments</key>
  <array>
    <string>{uv}</string>
    <string>run</string>
    <string>python</string>
    <string>{repo}/scripts/daily_run.py</string>
  </array>
  <key>WorkingDirectory</key><string>{repo}</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>{Path(uv).parent}:{docker_dir}:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StartCalendarInterval</key>
  <array>{slots}
  </array>
  <key>StandardOutPath</key><string>{repo}/data/reports/daily-launchd.out.log</string>
  <key>StandardErrorPath</key><string>{repo}/data/reports/daily-launchd.err.log</string>
</dict>
</plist>
"""


def notify(title: str, message: str) -> None:
    """A macOS notification; never raises (it must not hide the real error)."""
    if sys.platform != "darwin":
        return
    try:
        text = message.replace('"', "'")[:200]
        subprocess.run(
            ["osascript", "-e", f'display notification "{text}" with title "{title}"'],
            check=False,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        pass


# --- the real run -----------------------------------------------------------------


def main() -> int:
    import nightly_update as nu
    from catch_up_upto import fill_index
    from catch_up_upto import main as catch_up
    from vnstock_research.backtest import forward_returns as fr
    from vnstock_research.data import db
    from vnstock_research.patterns import fingerprint as fpm
    from vnstock_research.report import paper, scan

    REPORTS.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def log(line: str = "") -> None:
        text = f"{datetime.now():%H:%M:%S}  {line}"
        lines.append(text)
        print(text, flush=True)

    try:
        take_lock(LOCK)
    except Locked as e:
        log(str(e))
        return 0
    state: dict = {"recorded": [], "status": "failed", "message": ""}
    conn = None

    def connect():
        nonlocal conn
        conn = db.connect()  # a refused connection means Docker is not up
        return "database ok"

    def heal_index(have, offered, links) -> str:
        """Fill VNINDEX rows missing for days we already hold (see refresh_index)."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT max(trade_date) FROM index_bar WHERE symbol = 'VNINDEX'"
            )
            (idx_max,) = cur.fetchone()
        if idx_max is not None and idx_max >= have:
            return ""
        state["index_before"] = idx_max
        dest = UPTO_ROOT / offered.isoformat()
        if not refresh_index(links, dest, lambda u: nu.get(u, binary=True)):
            return "; index file not served yet"
        with conn.cursor() as cur:
            n = fill_index(cur, dest, have)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT max(trade_date) FROM index_bar WHERE symbol = 'VNINDEX'"
            )
            (after,) = cur.fetchone()
        state["index_healed"] = after is not None and after != idx_max
        return f"; index checked ({n} rows offered), VNINDEX now through {after}"

    def load():
        with conn.cursor() as cur:
            cur.execute("SELECT max(trade_date) FROM bar_raw")
            (have,) = cur.fetchone()
        tag, links = upto_links(nu.get(nu.PAGE))
        offered = datetime.strptime(tag, "%d%m%Y").date()
        status = source_status(offered, have, date.today())
        state["status"] = status
        if status != "new":
            if status == "stale_source":
                notify("Stock research", f"CafeF has nothing newer than {have}")
            healed = heal_index(have, offered, links)
            return f"{status}: CafeF offers {offered}, database holds {have}{healed}"
        dest = UPTO_ROOT / offered.isoformat()
        if not fetch_set(links, dest, lambda u: nu.get(u, binary=True)):
            state["status"] = "not_ready"
            return f"not ready: CafeF lists {offered} but a file is not served yet"
        if catch_up(dest, True) != 0:
            raise RuntimeError("catch_up_upto refused (blocking data-check failure)")
        prune_upto(UPTO_ROOT)
        state["status"] = "loaded"
        return f"loaded through {offered}"

    def snapshot():
        nu.refresh_labels(conn)

    def todo_days():
        ledger = paper.read(paper.LEDGER)
        done = set(ledger["day"].astype(str)) if len(ledger) else set()
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT trade_date FROM trading_day ORDER BY 1")
            days = [str(r[0]) for r in cur.fetchall()]
        first = min(done) if done else days[-1]
        return [d for d in days if d >= first and d not in done]

    def rebuild():
        days = todo_days()
        state["todo"] = days
        if not needs_rebuild(days, state.get("index_healed", False)):
            return "ledger is up to date; nothing to rebuild"
        log(f"{len(days)} unrecorded day(s): {', '.join(days) or '-'}")
        if state.get("index_healed"):
            log("index rows were filled: rebuilding so the regime columns are current")
        log(f"fingerprint -> {fpm.build(conn)}")
        log(f"returns -> {fr.build(conn)}")

    def regression():
        ledger = paper.read(paper.LEDGER)
        if not len(ledger):
            return "empty ledger"
        day = str(ledger["day"].astype(str).max())
        paper.record(scan.pick(conn, day))  # raises if the rebuilt data now disagrees
        return f"{day} re-derived identically (append-only guard)"

    def record():
        for day in state.get("todo", []):
            p, report = scan.daily_scan(conn, day)
            row = paper.record(p)
            out = paper.REPORTS / f"scan-{p.day}.txt"
            out.write_text("\n".join(report) + "\n", encoding="utf-8")
            what = (
                "NOTHING STRONG"
                if row["outcome"] == "nothing"
                else f"{row['symbol']} {row['hypothesis']}"
            )
            state["recorded"].append(f"{day}: {what}")
            log(f"recorded {day}: {what}")

    def chart_forward():
        """Shadow track (registration chart-forward-v3). Never fails the main record."""
        try:
            from vnstock_research import chart_forward as cf

            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT trade_date FROM trading_day ORDER BY 1")
                all_days = [r[0] for r in cur.fetchall()]
            missing = cf.missing_days(all_days, cf.read())
            msg = "chart forward: up to date"
            if missing:
                done = cf.record_days(conn, missing)
                msg = f"chart forward recorded {done}"
            if date.today().weekday() == 4:  # Friday: the weekly report
                report = cf.evaluate(conn)
                out = cf.REPORTS / f"chart-forward-{date.today():%Y%m%d}.txt"
                out.write_text("\n".join(report) + "\n", encoding="utf-8")
                msg += f"; weekly report {out.name}"
            return msg
        except Exception as e:  # noqa: BLE001 - a shadow track must not stop the ledger
            log(f"WARNING chart forward step failed: {type(e).__name__}: {e}")
            notify("Stock research", f"chart forward track failed: {type(e).__name__}")
            return "chart forward: FAILED (see log); the main record is unaffected"

    def score():
        for line in paper.run_score(conn):
            log(line)

    def brief():
        """One-screen summary for Ben. Read-only and non-fatal: the record is done."""
        if not state["recorded"]:
            return "no new day, no brief"
        try:
            from vnstock_research.report import brief as daily_brief

            head, out = daily_brief.write(conn, str(state["todo"][-1]))
            state["headline"] = head
            return f"brief written: {out.name}"
        except Exception as e:  # noqa: BLE001 - the ledger is already safe
            log(f"WARNING brief step failed: {type(e).__name__}: {e}")
            return "brief: FAILED (see log); the record is unaffected"

    def prune():
        ledger = paper.read(paper.LEDGER)
        registered = set(ledger["featureset"].astype(str)) if len(ledger) else set()
        build, fs = fpm.expected(conn)
        registered.add(fs.fingerprint)
        gone = prune_fingerprints(fpm.ROOT, build, registered)
        return f"pruned {len(gone)} old fingerprint dir(s): {', '.join(gone) or '-'}"

    steps = [
        ("database", connect),
        ("load", load),
        ("industry snapshot", snapshot),
        ("rebuild if days are unrecorded", rebuild),
        ("regression guard", regression),
        ("scan and record", record),
        ("chart forward (shadow)", chart_forward),
        ("score", score),
        ("daily brief", brief),
        ("prune old fingerprints", prune),
    ]
    code = run_pipeline(steps, log, notify)
    status = "failed" if code else HEARTBEAT.get(state["status"], "ok")
    try:
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO job_run (job, status, message, finished_at) "
                    "VALUES ('daily_run', %s, %s, now())",
                    (status, "; ".join(state["recorded"])[:500] or status),
                )
            conn.commit()
            conn.close()
    except Exception as e:  # noqa: BLE001
        log(f"WARNING: heartbeat not written ({type(e).__name__}: {e})")
    if state["recorded"] and not code:
        notify("Stock research", state.get("headline") or " | ".join(state["recorded"]))
    (REPORTS / f"daily-{datetime.now():%Y%m%d-%H%M}.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    LOCK.unlink(missing_ok=True)
    return code


if __name__ == "__main__":
    if "--print-plist" in sys.argv:
        uv = shutil.which("uv") or "/opt/homebrew/bin/uv"
        docker = shutil.which("docker")
        print(plist(REPO, uv, str(Path(docker).parent) if docker else "/usr/local/bin"))
        raise SystemExit(0)
    raise SystemExit(main())
