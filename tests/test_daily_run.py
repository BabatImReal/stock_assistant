"""The daily runner's pure parts: page parsing, staleness, locking, failure handling,
pruning and the launchd file. No database, no network.
"""

import datetime as dt
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import daily_run as dr  # noqa: E402

HTML = "".join(
    f'<a href="https://x.vn/{n}">'
    for n in (
        "CafeF.SolieuGD.Upto30092026.zip",
        "CafeF.SolieuGD.Raw.Upto30092026.zip",
        "CafeF.Index.Upto30092026.zip",
        "CafeF.SolieuGD.Upto02102026.zip",
        "CafeF.SolieuGD.Raw.Upto02102026.zip",
        "CafeF.Index.Upto02102026.zip",
        "CafeF.SolieuGD.Upto05102026.zip",  # incomplete: the other two not up yet
        "CafeF.SolieuGD.02102026.zip",  # a DAILY file: must be ignored
    )
)


def test_the_newest_complete_cumulative_set_is_chosen():
    tag, links = dr.upto_links(HTML)
    assert tag == "02102026"  # 05-10 is incomplete, so it is not offered yet
    assert set(links) == {"stocks_adjusted", "stocks_unadjusted", "index"}


def test_no_complete_set_is_an_error_not_silence():
    with pytest.raises(RuntimeError):
        dr.upto_links('<a href="https://x.vn/CafeF.SolieuGD.Upto02102026.zip">')


D = dt.date


def test_a_newer_publication_is_new():
    assert dr.source_status(D(2026, 10, 5), D(2026, 10, 2), D(2026, 10, 5)) == "new"


def test_running_early_is_quiet_but_two_business_days_behind_is_stale():
    have = D(2026, 10, 2)  # Friday
    assert dr.source_status(have, have, D(2026, 10, 3)) == "no_new_data"  # Saturday
    assert dr.source_status(have, have, D(2026, 10, 5)) == "no_new_data"  # Monday
    assert dr.source_status(have, have, D(2026, 10, 6)) == "stale_source"  # Tuesday


def test_the_first_failure_stops_the_rest_and_notifies():
    ran, told = [], []

    def boom():
        raise ValueError("db down")

    steps = [
        ("a", lambda: ran.append("a")),
        ("b", boom),
        ("c", lambda: ran.append("c")),
    ]
    code = dr.run_pipeline(steps, lambda s="": None, lambda t, m: told.append((t, m)))
    assert code == 1 and ran == ["a"]  # c never ran
    assert told and "b" in told[0][1]  # the failure was announced, not swallowed


def test_a_clean_pipeline_returns_zero_and_runs_everything():
    ran = []
    steps = [("a", lambda: ran.append(1)), ("b", lambda: ran.append(2))]
    assert dr.run_pipeline(steps, lambda s="": None, lambda t, m: None) == 0
    assert ran == [1, 2]


def test_a_live_lock_refuses_a_second_copy(tmp_path):
    lock = tmp_path / "l"
    dr.take_lock(lock, pid=os.getpid())
    with pytest.raises(dr.Locked):
        dr.take_lock(lock, pid=1234)


def test_a_dead_process_lock_is_taken_over(tmp_path):
    lock = tmp_path / "l"
    lock.write_text("999999999")  # no such process
    dr.take_lock(lock, pid=os.getpid())
    assert lock.read_text() == str(os.getpid())


def test_pruning_keeps_only_the_newest_folders(tmp_path):
    for d in ("2026-09-30", "2026-10-01", "2026-10-02"):
        (tmp_path / d).mkdir()
    gone = dr.prune_upto(tmp_path, keep=2)
    assert gone == ["2026-09-30"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10-01", "2026-10-02"]


def test_the_launchd_file_uses_absolute_paths_weekdays_and_logs():
    repo = Path("/Users/Ben Nguyen/stock_assistant/stock_assistant")
    xml = dr.plist(repo, "/opt/homebrew/bin/uv", "/usr/local/bin")
    assert "<string>/opt/homebrew/bin/uv</string>" in xml  # absolute, no shell
    assert f"<string>{repo}/scripts/daily_run.py</string>" in xml  # space-safe
    assert xml.count("<key>Weekday</key>") == 10  # Mon-Fri x 21:30 and 23:30
    assert "<integer>6</integer>" not in xml and "<integer>0</integer>" not in xml
    assert "StandardErrorPath" in xml and "EnvironmentVariables" in xml


def _http_error(code):
    import requests

    r = requests.Response()
    r.status_code = code
    return requests.HTTPError(response=r)


def _zip_bytes():
    import io
    import zipfile

    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x.csv", "a")
    return b.getvalue()


def test_a_listed_but_unserved_file_means_not_ready_not_failure(tmp_path):
    def getter(url):
        if "Raw" in url:
            raise _http_error(404)
        return _zip_bytes()

    links = {"stocks_adjusted": "u/a", "stocks_unadjusted": "u/Raw", "index": "u/i"}
    assert dr.fetch_set(links, tmp_path, getter) is False
    # and the retry resumes: the first file is not downloaded twice
    calls = []
    assert dr.fetch_set(links, tmp_path, lambda u: calls.append(u) or _zip_bytes())
    assert "u/a" not in calls and len(calls) == 2


def test_any_other_http_error_is_still_a_failure(tmp_path):
    def getter(url):
        raise _http_error(500)

    with pytest.raises(Exception):  # noqa: B017 - requests.HTTPError
        dr.fetch_set({"index": "u/i"}, tmp_path, getter)


def test_every_heartbeat_status_is_one_the_table_accepts():
    # the first live run died writing its heartbeat: 'loaded' was not allowed
    sql = (
        Path(__file__).resolve().parent.parent / "migrations" / "005_job_run.sql"
    ).read_text()
    allowed = set(
        re.findall(r"'(\w+)'", sql[sql.index("CHECK (status IN") :].split(")")[0])
    )
    assert allowed >= {"ok", "failed", "no_new_data", "stale_source"}
    assert set(dr.HEARTBEAT.values()) <= allowed


def _fp_dir(root, name, age):
    d = root / name
    d.mkdir(parents=True)
    m = d / "manifest.json"
    m.write_text("{}")
    os.utime(m, (age, age))
    return d


def test_pruning_removes_only_old_daily_series_dirs_of_the_current_build(tmp_path):
    reg = {"aaa", "bbb", "ccc", "ddd", "eee"}
    for i, h in enumerate(["aaa", "bbb", "ccc", "ddd", "eee"]):
        _fp_dir(tmp_path, f"6_{h}", 1000 + i)  # oldest .. newest
    _fp_dir(tmp_path, "6_structural", 10)  # same build, hash never in the ledger
    _fp_dir(tmp_path, "5_aaa", 5)  # another build's directory
    (tmp_path / "6_unknown_file").write_text("x")  # not a directory
    gone = dr.prune_fingerprints(tmp_path, 6, reg, keep=3)
    assert sorted(gone) == ["6_aaa", "6_bbb"]  # the two oldest of the series only
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == [
        "5_aaa",
        "6_ccc",
        "6_ddd",
        "6_eee",
        "6_structural",
        "6_unknown_file",
    ]


def test_pruning_keeps_everything_when_the_series_is_short(tmp_path):
    _fp_dir(tmp_path, "6_aaa", 1)
    assert dr.prune_fingerprints(tmp_path, 6, {"aaa"}, keep=3) == []
    assert (tmp_path / "6_aaa").exists()
