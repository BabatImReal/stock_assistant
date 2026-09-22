"""Database connection and migrations.

Deliberately small. Migrations are numbered .sql files applied in order and
recorded in a table, which is all a one-developer project needs -- no ORM, no
migration framework, no model classes to keep in sync with the SQL.

The SQL files are the schema documentation: they carry the "why" comments, so
the reasoning lives next to the constraint it explains rather than in a wiki.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

REPO = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO / "migrations"


def load_env() -> None:
    """Read .env into the environment.

    Hand-rolled rather than pulling in python-dotenv for four lines. Existing
    environment variables win, so a shell override still works.
    """
    env = REPO / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def dsn() -> str:
    load_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env "
            "(see README) and start the database with `docker compose up -d`."
        )
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(dsn())


def migrate(verbose: bool = True) -> list[str]:
    """Apply every migration that has not been applied yet.

    Each file runs inside its own transaction, so a failure leaves the database
    on the last complete migration rather than half-way through one.
    """
    applied: list[str] = []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migration (
                    filename    text PRIMARY KEY,
                    applied_at  timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()
            cur.execute("SELECT filename FROM schema_migration")
            done = {row[0] for row in cur.fetchall()}

        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            with conn.cursor() as cur:
                cur.execute(path.read_text())
                cur.execute(
                    "INSERT INTO schema_migration (filename) VALUES (%s)", (path.name,)
                )
            conn.commit()
            applied.append(path.name)
            if verbose:
                print(f"applied {path.name}")

    if verbose and not applied:
        print("database already up to date")
    return applied


if __name__ == "__main__":
    migrate()
