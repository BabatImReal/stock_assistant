# Current state — 2026-10-05 (session 2026-10-05-01, run 10)

## Purpose and boundary
- Private end-of-day Vietnamese stock research for Ben: HOSE, HNX, UPCoM. Goal: ONE
  or TWO well-evidenced stocks, not a list. Research, not prediction; Ben decides.
- Deterministic code measures prices, patterns and returns; LLMs coordinate and
  explain. "Nothing strong today" is valid.
- Source of truth: `docs/knowledge/pattern-research-knowledge.md` (never edit).
- Phase: research-only chart formations beyond the original phase roadmap; no chart
  family is approved for recommendation or production promotion.
- Branch: `claude/design-system-pattern-history-aqbkd8` (the only working branch), pushed to
  origin at the end of run 10. Only Ben merges.

## The forward log is running (verified this run)
- bar_raw = 2,894,845 rows through 2026-10-05. Ledger `research/paper_ledger.csv`: 17
  days, 7 forward (09-25 .. 10-05), 3 before the freeze (09-22, 09-23, 09-24;
  frozen_on = 2026-09-24).
- Forward proposals, all `k5:marubozu_red+ma_50_rising+rvol_high`, all PENDING:
  AAA 2026-09-28, VNM 2026-10-02, TAL 2026-10-05. Verdict: NO VERDICT YET (0 of 30
  scored signal days, needs >= 3 months). Pre-freeze FPT 2026-09-18: net -4.59%.
- These are NOT recommendations. In the registered holdout this signal is ACCEPT
  (741 trades on 275 signal days) but at 0.40% cost avg per trade +0.27% and avg per
  SIGNAL DAY -0.43%; one-pick total -1.18 stakes (median path); 60-pick stretches
  below zero 76%.
- Rows for 09-22..10-02 were recorded on 10-05 (late `recorded_at`), each using only
  data through its own close. Scan evidence reports exist only for 09-21 and 10-05.
- Fee: Ben confirmed 0.15%/side + 0.1% sale tax (equals config). `broker_fee_provisional`
  stays true until the next planned returns rebuild (costs.yaml is inside
  `forward_returns.rules_hash()`); scoring still prints NET PROVISIONAL.

## Data handling (restatements)
- CafeF restates adjusted history after corporate actions. 41 symbols are in
  `excluded_window` (reason "restated by CafeF: ...", event dates 09-22..10-05). Each
  keeps old-basis adjusted bars for days before its action; from the action date it is
  excluded for 60 sessions (valid_to ~ +91 days). Later bars are appended and blanked by
  the window (invariant: every adjusted row on/after an event lies inside its window;
  verified 24 rows, 0 outside). They re-enter research at the next rebuild.
- `scripts/catch_up_upto.py` (dry run by default, `--apply`, `--since=DATE`) compares
  every symbol on its OWN last stored day. NEVER use `scripts/load_history.py`.
- Gates passed after the repair: fingerprint 0 changed rows (dates <= 09-21) vs the
  pre-catch-up backup; returns 0 previously resolved outcomes altered; all 9 recorded
  days re-derived identically; pytest 732 passed; describe-holdout reproduces the
  logged holdout.
- Backups to keep until Ben says all is well (git-ignored): `data/backups/pre-catchup-20261005-1121.dump`
  (241 MB DB), `data/backups/artifacts-pre-catchup/` (592 MB), `data/backups/artifacts-after-first-rebuild/`.

## The daily cycle (built, tested, INSTALLED 2026-10-05)
- `scripts/daily_run.py` does: lock, DB check, load via `Upto` + catch_up, industry
  snapshot, rebuild fingerprint + returns when ledger days are missing (~16 min), regression
  guard, scan + record each missing day, score, heartbeat, log, macOS notification.
  A listed-but-404 file means "not ready". `nightly_update.py`'s price append is
  superseded and must not be scheduled with it. First live run: 10-05, recorded TAL.
- launchd job `com.vnstock.daily-run` is loaded for user `apple`
  (`~/Library/LaunchAgents/com.vnstock.daily-run.plist`): weekdays 21:30 and a 23:30
  retry, Vietnam time. Verified by a kickstart through launchd: exit 0, empty stderr,
  heartbeat `no_new_data`, ledger unchanged. Logs: `data/reports/daily-*.txt`,
  `daily-launchd.out.log`, `daily-launchd.err.log`. Needs Docker Desktop running and
  the Mac awake (launchd runs a missed slot on wake). To stop it:
  `launchctl bootout gui/$(id -u)/com.vnstock.daily-run`.
- Disk: the fingerprint directory changes daily (sector snapshot date is in the
  feature-set hash), ~213 MB/day, nothing prunes it (317 GB free).

## Open problems (decisions for Ben)
- Decide on a fingerprint prune policy; check the first scheduled evening run (21:30) in
  `data/reports/daily-*.txt` and the heartbeat rows (`job_run`, job = 'daily_run').
- G2: `nightly_update.py:295` still hardcodes `restated = False` (the daily runner
  does not use it). IRC, VHF and PIS differ from CafeF's file on older dates and were
  not investigated. Symbols excluded after a corporate action return only at a rebuild
  with rescale (option 1 was deferred); if restatement bursts are typical this erodes the
  pool, so that rebuild is the next piece of data work.
- UPCoM price-limit date conflict (2013-01-15 in `market_rules.yaml` vs 2015-07-01 per
  the SSC notice) and early exchange bands remain unresolved.
- The structural feature set `5_f6181075e5962796` was not rebuilt (lacks 09-22..10-05).

## Research status (carried forward from run 5, not re-verified)
- Codex's v1/v2 chart detectors claim NO validated edge; v2 census 3,172 episodes; only
  590 of 1,657 pre-2024 confirmed breaks reached a gated outcome; best cell n=14, one
  of 40 trials on seen data; only 15.8% of double-level episodes carry a prior-trend
  context. 2012-2023 and the 2024-2026 holdout are spent; the forward record is the only
  clean confirmation. Report-faithfulness LLM eval: spec only
  (`docs/evals/report-faithfulness-eval.md`), no LLM surface exists.

## Next action and guardrails
1. Ben: prune policy; look at tonight's scheduled run.
2. Each trading day: let the daily cycle record the day; never score before recording;
   do not read a proposal as a recommendation.
3. Next data work: rebuild with rescale so restated names return; G2 detection is
   handled in the daily path, the old nightly job stays unscheduled.
4. Freeze v3 chart rules only with Ben's approval and before looking at revised effects.

## Session discipline
- Read this file, `knowledge/00-index.md`, then task-relevant notes/code.
- Log each run, rewrite this file from scratch, and verify numbers against git and
  stored manifests before replying.
