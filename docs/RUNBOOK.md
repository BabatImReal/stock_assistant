# Running it yourself (no Claude needed day to day)

## What runs by itself
A launchd job runs `scripts/daily_run.py` on weekdays at 21:30 (retry 23:30), Vietnam time.
It needs two things: **Docker Desktop running** and the **Mac awake** (a missed slot runs on wake).
It loads the day, records the engine's pick, scores old picks, and writes the brief.

## What you read (one file a day)
    cd "/Users/Ben Nguyen/stock_assistant/stock_assistant"
    open "$(ls -t research/reports/brief-*.txt | head -1)"
The first line is the answer. "NOTHING STRONG TODAY" is the normal answer. A fired signal
is labelled WEAK / UNPROVEN / STRONG; only STRONG is a candidate, and even then it is research.
Full evidence for a pick: `research/reports/scan-<date>.txt`.

## If you want to run it by hand
    uv run python scripts/daily_run.py
Safe to repeat: days are recorded once, a changed rule is refused.

## When to worry (and when not)
- Notification "Stock research: FAILED": open the newest `data/reports/daily-*.txt`; the last lines say the step.
  Usual cause: Docker not running. Start Docker, run the command above.
- No brief for a trading day: the CafeF file was probably late; the 23:30 retry or next evening fills it.
- Do NOT run `scripts/load_history.py` (it overwrites restated history). Do NOT edit `config/rules/*`
  or `research/paper_ledger.csv` (they are frozen; the code refuses a changed file).
- Stop the schedule: `launchctl bootout gui/$(id -u)/com.vnstock.daily-run`

## Needs Claude (not daily)
Monthly `scripts/rescale_build.py` (brings restated stocks back); anything that changes a rule.

## How to judge it (the part that matters)
Ignore single days. After about January 2027 the forward record has 30+ scored signal days; the
verdict line in the brief then says PASS / FAIL / PROVISIONAL by a rule frozen in advance.
Until then it is a research log, not a trading tool.
