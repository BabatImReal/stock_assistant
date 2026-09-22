"""Schema checks that do not need a database.

The migrations are the schema documentation, so the things worth testing without
a live server are that they exist, are ordered, and still encode the two
decisions that are easiest to undo by accident.
"""

from pathlib import Path

from vnstock_research.data import db


def test_migrations_exist_and_are_ordered():
    files = sorted(db.MIGRATIONS.glob("*.sql"))
    assert files, "no migrations found"
    # Numbered prefixes: applied in filename order, so the order must be explicit.
    assert [f.name[:3] for f in files] == sorted(f.name[:3] for f in files)


def test_universe_is_restricted_to_three_letter_tickers():
    # Without this constraint the HOSE file's ~2,000 covered warrants enter the
    # universe and every base rate is computed over the wrong population.
    sql = (db.MIGRATIONS / "001_initial.sql").read_text()
    assert "^[A-Z]{3}$" in sql


def test_negotiated_volume_cannot_be_faked_with_a_zero_row():
    # "Absent is not zero": deal_volume is NOT NULL, so a missing row is the
    # only way to say unknown -- which is the point.
    sql = (db.MIGRATIONS / "001_initial.sql").read_text()
    block = sql[sql.index("CREATE TABLE IF NOT EXISTS negotiated_volume") :]
    block = block[: block.index(");")]
    assert "deal_volume   bigint NOT NULL" in block


def test_env_loading_does_not_override_the_shell(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-shell/db")
    db.load_env()
    import os

    assert os.environ["DATABASE_URL"] == "postgresql://from-shell/db"


def test_repo_root_resolves_to_the_project(tmp_path):
    assert (Path(db.REPO) / "pyproject.toml").is_file()
