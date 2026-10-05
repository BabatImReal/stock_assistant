# VN Stock Researcher

Research tool for the Vietnamese stock market (HOSE, HNX, UPCoM): free end-of-day data
only, one pre-registered method at a time, and nothing recommended until it passes its test.

The pattern-matching method was retired on 2026-10-06 (see agent-memory/knowledge/decisions.md).
What remains is the data layer:

- `src/vnstock_research/data/`   CafeF loaders, price adjustment, reconciliation, universe
- `src/vnstock_research/features/bars.py`   adjusted candles, point in time
- `scripts/daily_run.py`   loads the latest trading day (not scheduled)
- `config/rules/`   costs, holidays, market rules, universe

Run the tests: `uv run pytest`. Start the database: `docker compose up -d`.
Project memory for Claude sessions lives in `agent-memory/` (start at CURRENT_STATE.md).
