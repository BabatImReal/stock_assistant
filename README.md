# VN Stock Pattern Researcher

A research tool for the Vietnamese stock market (HOSE, HNX, UPCoM). Every day it
scans every listed code, compares the last few days of price and volume
behaviour with what historically followed similar behaviour since 2012, and
proposes **one** stock with the evidence behind it — or says "nothing strong
today".

It is research, not prediction. It proposes; Ben decides.

Full background: [`docs/knowledge/pattern-research-knowledge.md`](docs/knowledge/pattern-research-knowledge.md).
That document is the source of truth and is never edited.

**Current status: Phase 2 — skeleton.** The folders and configuration exist; the
modules are empty on purpose. There is nothing to scan or report yet.

---

## What you need installed

Two things, and neither is Python itself.

### 1. uv — manages Python and the project's packages

`uv` downloads the right Python version, creates an isolated environment in the
project folder, and installs the packages. You never have to think about
"which Python is this using".

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then close and reopen the terminal, and check it worked:

```bash
uv --version
```

### 2. Docker Desktop — runs the database

**What Docker is, in one paragraph.** Installing a database normally means
installing software onto your Mac, configuring it, and hoping you can remove it
cleanly later. Docker instead runs the database inside a *container*: a sealed
box with its own filesystem, which talks to your machine only through the ports
you open. The box is described entirely by `docker-compose.yml` in this repo, so
anyone who runs that file gets an identical database. When you are done, you
delete the box and your Mac is exactly as it was.

Three words you will see:

- **Image** — the downloaded template (here: PostgreSQL with the TimescaleDB
  extension). Read-only.
- **Container** — a running copy of an image. This is the actual database.
- **Volume** — a storage area that lives *outside* the container, so the data
  survives when the container is deleted and recreated.

Install Docker Desktop from <https://www.docker.com/products/docker-desktop/>,
then **open the app once**. That first launch matters: it accepts the licence,
asks for your admin password, and installs the `docker` command onto your PATH.
Until you have done it, `docker --version` reports "command not found" even
though the app is sitting in your Applications folder — which is exactly the
state this machine was in when the skeleton was written.

Leave it running (a whale icon appears in the menu bar). Docker commands only
work while Docker Desktop is running.

```bash
docker --version
```

---

## Setting up the project

From the repo folder:

```bash
# 1. Create the environment and install everything (takes a minute the first time)
#    .python-version pins this project to Python 3.12; uv downloads it for you
#    if you do not have it, and does not touch the Python your Mac ships with.
uv sync

# 2. Create your local settings file from the template
cp .env.example .env
```

Then open `.env` and fill in `SSI_CONSUMER_ID` and `SSI_CONSUMER_SECRET` once
you have SSI FastConnect credentials. **`.env` is git-ignored and must never be
committed** — it is the only place credentials live.

Optional but recommended, so that formatting problems are fixed before they
reach a commit rather than after:

```bash
uv run pre-commit install
```

---

## Starting the database

```bash
docker compose up -d
```

`up` starts it; `-d` means "detached", i.e. in the background instead of taking
over your terminal. The first run downloads the image (a few hundred MB); later
runs take a second or two.

Check it is healthy:

```bash
docker compose ps
```

You want to see `vnstock-db` with status `running (healthy)`.

Open a SQL prompt inside the container:

```bash
docker compose exec db psql -U vnstock -d vnstock
```

(`\dt` lists tables, `\q` quits. There are no tables yet — the schema is
designed in a later phase, deliberately after we have seen real SSI data.)

Watch the database's log output:

```bash
docker compose logs -f db     # Ctrl-C to stop watching; the database keeps running
```

### Stopping it

```bash
docker compose stop     # pause; data and container kept
docker compose down     # remove the container; DATA IS KEPT in the volume
docker compose down -v  # remove the container AND DELETE ALL DATA
```

The difference matters: `down` is safe and routine, `down -v` throws away
everything you downloaded. Only `-v` deletes data.

### If port 5432 is already in use

Something else on your machine is already using the default PostgreSQL port.
Set a different one in `.env`, then `docker compose up -d` again:

```
POSTGRES_PORT=5433
```

---

## Running the tools

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
```

`uv run` means "run this inside the project's environment" — you never need to
activate a virtualenv by hand.

---

## Layout

```
CLAUDE.md                     Permanent instructions for every Claude Code session
docs/knowledge/               The knowledge document — source of truth, never edited
agent-memory/                 Claude's own notes; committed on purpose, read first
  CURRENT_STATE.md              Where the project is right now
  knowledge/                    One file per topic, plus decisions and open questions
  logs/                         One file per session
src/vnstock_research/
  data/                       SSI client, download, storage, price adjustment (doc §7.5)
  features/                   Volume, trend and context measures (doc §4-5)
  patterns/                   Pattern rules as arithmetic on OHLCV (doc §3)
  backtest/                   Forward returns, base rates, validation (doc §2, §8)
  report/                     The daily recommendation (doc §7.4)
config/rules/                 Pattern thresholds as config, never hard-coded (doc §3.5)
data/raw/                     Raw downloads (git-ignored)
data/processed/               Derived data (git-ignored)
scripts/                      One-off and scheduled scripts
tests/                        Tests
notebooks/                    Exploration
docker-compose.yml            PostgreSQL + TimescaleDB
```

`agent-memory/` is committed deliberately: it lets a new session understand the
project without re-reading the whole codebase.

---

## What comes next

**Phase 3 — the SSI history probe.** Before any database schema is designed, a
script calls the real SSI API to find out what data actually exists: how far
back it goes, whether delisted stocks are included, and whether the matched vs
negotiated volume split and foreign flow are populated in the older years.
Published API documentation and real payloads often differ, so nothing is
assumed.

Eleven items must be resolved before any statistic is computed — they are listed
under "must resolve before any measurement" in
[`agent-memory/knowledge/open-questions.md`](agent-memory/knowledge/open-questions.md).
