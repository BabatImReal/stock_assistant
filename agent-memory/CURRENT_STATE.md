# Current state — 2026-10-05 (session 2026-10-05-01, run 15)

## Purpose and boundary
- Private end-of-day Vietnamese stock research for Ben: HOSE, HNX, UPCoM. Goal: ONE
  or TWO well-evidenced stocks, not a list. Research, not prediction; Ben decides.
- Deterministic code measures prices, patterns and returns; LLMs coordinate and
  explain. "Nothing strong today" is valid.
- Source of truth: `docs/knowledge/pattern-research-knowledge.md` (sections 1-11 never rewritten; changes only as dated amendments in section 12 on Ben's decision).
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

## Data handling (restatements) — build 6 is current
- CafeF restates adjusted history after corporate actions. Adjustment build 6 (promoted
  2026-10-05 evening, `scripts/rescale_build.py`) rescales the 36 symbols whose history differs
  from CafeF's file by ONE constant ratio; their windows were removed. 5 are refused and stay
  excluded (ADP, LPT, PDV, PSE, VCC; not constant / a stored day absent from CafeF). The text
  below describes the mechanism that still applies to FUTURE restatements: symbols are
  flagged by the daily load, e.g. 41 were flagged 09-22..10-05. Each
  keeps old-basis adjusted bars for days before its action; from the action date it is
  excluded for 60 sessions (valid_to ~ +91 days). Later bars are appended and blanked by
  the window (invariant: every adjusted row on/after an event lies inside its window;
  verified 24 rows, 0 outside). They re-enter research at the next rebuild.
- `scripts/catch_up_upto.py` (dry run by default, `--apply`, `--since=DATE`) compares
  every symbol on its OWN last stored day. NEVER use `scripts/load_history.py`.
- Gates passed after the catch-up repair, ON BUILD 5 (history; build 6 gates are below): fingerprint
  0 changed rows (dates <= 09-21) vs the pre-catch-up backup; returns 0 previously resolved
  outcomes altered; all 9 recorded days re-derived identically. describe-holdout reproduced the
  logged holdout then; it now refuses on build 6 (see Build 6 consequences).
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

## Build 6 consequences (verified)
- `describe-holdout` REFUSES on build 6 ("the holdout ran on build [5], these rows are build
  6: not the trades it judged"). By design; the description is frozen on build 5 in git.
- Ledger rows 09-11..10-05 carry build 5; new rows carry build 6. All 17 recorded days
  re-derive identically on build 6; scoring runs on build 6. pytest 741 passed.
- Index rows for 2026-10-05 were missing (CafeF's Index file lagged) and are now FILLED (daily run,
  19:55). The 10-05 scan row was recorded without the regime (append-only); the six accepted
  signals do not use the index. The daily run re-fetches the Index file whenever VNINDEX lags.
- Fingerprint pruning runs as the last daily step (current build's daily series only,
  newest 3 kept). The `5_*` artifacts (~700 MB) are the rollback for build 6 and can be
  deleted by hand once Ben is satisfied.
- Extra backups (git-ignored): `data/backups/pre-rescale-20261005-1751.dump` (241 MB),
  `data/backups/artifacts-pre-rescale/` (806 MB), `data/reports/rescale-windows-removed.json`.
- The schedule is loaded. The first SCHEDULED run (21:36 on 10-05) exited 0: no_new_data, regression
  guard identical, scored on build 6. A heal of a lagging VNINDEX row now forces a fingerprint
  rebuild (the stored copy would otherwise keep NaN regime columns). pytest 746 passed.

## Chart-formation forward track v3 (frozen 2026-10-05 22:39, commit 027df73)
- Shadow track beside the registered scan; never alters it. Frozen: `config/rules/chart_forward_v3.yaml`;
  text: `docs/preregistration/chart-forward-v3.md`. Log: `research/chart_forward_log.csv` (append-only,
  created at the first forward day, 2026-10-06). Code: `src/vnstock_research/chart_forward.py`; runs as
  the "chart forward (shadow)" step of the daily cycle (non-fatal) and writes a Friday report.
- H1 up-break excess and H2 down-break AVOID vs the same signal day's liquid cross-section; looks at
  60/120/240 resolved events, alpha 0.008 each; no p shown below n=60. ~40 events/yr per side, so only
  LARGE effects settle within 1-2 years (MDE table in the registration). Pooled spent-history numbers
  that motivated H2 are NOT evidence.
- Gate passed: wrapper == frozen census for 2026-01-01..09-21 (176/176). pytest 760 passed.

## Progress scoreboard (Ben asked for honest tracking, 2026-10-05; update EVERY run)
Target: ONE or TWO stocks with a good, evidenced chance to rise, or "nothing strong today". Judgement numbers, checklist below.
- Research tooling/pipeline: ~85%. Research ANSWER ("is there a tradable edge?"): open. So far NO: engine -0.43% per signal day
  in holdout, chart formations ~ market, cross-sectional score ~0 since 2020. Only the forward record can settle it.
- Ready-for-money: ~25% (Ben's target 50-60%). Checklist: [done] data+daily automation (first new-day run pending 10-06),
  [done] costs/fee/VN rules, [partial] forward paper ledger 0/30 scored days, [partial] readable daily brief (unverified live),
  [partial] risk sizing (drawdown in stakes only), [NOT] evidence of positive edge, [NOT] news veto.
- Earliest honest verdict: >= 30 scored signal days over >= 3 months -> about Jan 2027. Code cannot shorten it.
- Drift check: run 6-13 plumbing (restatements, rescale, fingerprints) kept data correct but added no edge; Amendment 1 was a
  null detour. New work must be tied to the output Ben reads or to the forward evidence.

## Daily brief (built run 15, wired into the daily cycle)
- `src/vnstock_research/report/brief.py` -> `research/reports/brief-<day>.txt`; non-fatal step "daily brief" after score in
  `daily_run.py`; its headline is the notification. Label rule (decisions 2026-10-05): WEAK / UNPROVEN / STRONG from the
  holdout's net PER SIGNAL DAY plus the forward record; "NOTHING STRONG TODAY" unless STRONG. 10-05: TAL = WEAK
  (+0.27% per trade, -0.43% per signal day). The scorecard lists AAA 09-28, VNM 10-02, TAL 10-05, all pending.
- BUG FOUND AND FIXED this run: after build 6 `describe_holdout` refuses, which would have crashed any proposal day's scan.
  `scan.daily_scan` now reads the saved description (`research/reports/holdout-2026-09-10-describe.txt`) when the build differs.
- Not yet run in a scheduled cycle with a new day (first: 10-06 21:30). Excess vs the same-day universe is not in the brief yet.

## Strategy status (Amendment 1, docs section 12)
- Ben approved a daily cross-sectional ranking and the document was amended (da7881d; corrections in 12.4a).
- Phase 1 development run, CORRECTED: the score (52-week-high proximity + 1-month abnormal turnover) earned
  +0.51% per 5-session trade over the day's liquid stocks in 2012-2019 (t 5.56) but ~0 in 2020-2023 (t -0.02)
  and +0.16% in 2024-26 (t 1.25). Frozen rule -> DROPPED, not tuned, no Phase 2. The first, flawed run had
  "passed"; both runs are in `research/reports/` and were taken to Ben.
- So far NOTHING tested has shown a usable forward-looking edge in recent years on liquid stocks: the registered
  engine (weak per signal day), chart formations (about the market), the cross-sectional score (zero since 2020).
  The forward logs (engine ledger, chart track v3) keep running at no cost.
- Closed out (docs 12.6): the score is dropped, no Phase 2. Ben (10-05): drop efforts without positive results. The
  shares-outstanding / foreign-flow / fundamentals experiments are NOT started; available only if Ben asks.

## Open problems (decisions for Ben)
- Check the first scheduled evening run (21:30) in
  `data/reports/daily-*.txt` and the heartbeat rows (`job_run`, job = 'daily_run').
- G2: `nightly_update.py:295` still hardcodes `restated = False` (the daily runner
  does not use it). IRC, VHF and PIS differ from CafeF's file on older dates and were
  not investigated. Symbols excluded after a corporate action return only at a rebuild
  with rescale (option 1 was deferred); if restatement bursts are typical this erodes the
  pool, so that rebuild is the next piece of data work.
- UPCoM price-limit date conflict (2013-01-15 in `market_rules.yaml` vs 2015-07-01 per
  the SSC notice) and early exchange bands remain unresolved.
- The structural feature set `5_f6181075e5962796` was not rebuilt (lacks 09-22..10-05).
- Refused by the rescale and still excluded: ADP, LPT, PDV (CafeF restated only part of their
  history, or one odd day: no single ratio) and PSE, VCC (only a flagged date-shifted day is
  missing; the rule now accepts that, so the next rescale takes them).

## Research status (carried forward from run 5, not re-verified)
- Codex's v1/v2 chart detectors claim NO validated edge; v2 census 3,172 episodes; only
  590 of 1,657 pre-2024 confirmed breaks reached a gated outcome; best cell n=14, one
  of 40 trials on seen data; only 15.8% of double-level episodes carry a prior-trend
  context. 2012-2023 and the 2024-2026 holdout are spent; the forward record is the only
  clean confirmation. Report-faithfulness LLM eval: spec only
  (`docs/evals/report-faithfulness-eval.md`), no LLM surface exists.

## Next action and guardrails
1. Watch the 10-06 21:30 run: first real new-day load, first chart-track day, first brief and notification.
2. Each trading day: let the daily cycle record the day; never score before recording;
   do not read a proposal as a recommendation.
3. Restatements of FUTURE corporate actions are flagged and excluded by the daily load; run
   `scripts/rescale_build.py build|verify|promote` periodically (e.g. monthly) to bring them back.
4. Freeze v3 chart rules only with Ben's approval and before looking at revised effects.

## Session discipline
- Read this file, `knowledge/00-index.md`, then task-relevant notes/code.
- Log each run, rewrite this file from scratch, and verify numbers against git and
  stored manifests before replying.
