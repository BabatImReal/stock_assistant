# Current state — 2026-10-05 (session 2026-10-05-01, run 8)

## Purpose and boundary
- Private end-of-day Vietnamese stock research for Ben: HOSE, HNX, UPCoM. Goal: ONE
  or TWO well-evidenced stocks, not a list. Research, not prediction; Ben decides.
- Deterministic code measures prices, patterns and returns; LLMs coordinate and
  explain. "Nothing strong today" is valid.
- Source of truth: `docs/knowledge/pattern-research-knowledge.md` (never edit).
- Phase: research-only chart formations beyond the original phase roadmap; no chart
  family is approved for recommendation or production promotion.
- Branch: `claude/design-system-pattern-history-aqbkd8` (the only working branch).
  Only Ben merges. UNCOMMITTED: research/paper_ledger.csv, scripts/catch_up_upto.py,
  tests/test_catch_up_upto.py and the agent-memory files (Ben to approve a commit).

## The forward log is running again (verified this run)
- Database `vnstock-db` healthy. bar_raw = 2,894,044 rows through 2026-10-02 (the 9
  sessions 09-22..10-02 are loaded). bar_adjusted build 5 has 7,203 new rows on 1,142
  symbols.
- `research/paper_ledger.csv`: 16 days recorded, 6 forward (09-25 .. 10-02), 3 before
  the freeze (09-22, 09-23, 09-24, frozen_on = 2026-09-24). Two forward proposals, both
  `k5:marubozu_red+ma_50_rising+rvol_high`: AAA 2026-09-28 and VNM 2026-10-02, both
  PENDING. Verdict rule: 0 of 30 scored signal days, needs >= 3 months: NO VERDICT YET.
- DISCLOSURE: the 9 rows were recorded on 2026-10-05 (late `recorded_at`), each using
  only data through its own close.
- These proposals are NOT recommendations: in the registered holdout that signal is
  ACCEPT (741 trades on 275 signal days) but at 0.40% cost avg per trade +0.27% and
  avg per SIGNAL DAY -0.43%; one-pick total -1.18 stakes (median path); 60-pick
  stretches below zero 76%. Pre-freeze FPT 2026-09-18 resolved net -4.59%.
- Fee: Ben confirmed 0.15%/side + 0.1% sale tax (equal to config). The flag
  `broker_fee_provisional` stays true until the next planned returns rebuild, because
  `costs.yaml` is inside `forward_returns.rules_hash()`; scoring still prints
  NET PROVISIONAL.

## How the catch-up was done (reuse after any outage)
- CafeF's daily page keeps ~3 dates; `nightly_update.py` loads one newest day per run.
  After an outage use `scripts/catch_up_upto.py DIR` (dry run, rolled back) then
  `--apply`, with DIR = extracted CafeF `Upto<date>` files (raw + adjusted + index),
  `--since=DATE` to repair. NEVER `scripts/load_history.py` (truncates derived tables).
- 26 symbols were restated by CafeF (VPB, TPB, GAS, ...). Option chosen by Ben: keep
  build 5, exclude. Each gets old-basis adjusted bars only for days before its action
  and an excluded_window from the action date for 60 sessions (valid_to ~ 12-22..12-31).
- Verified: raw prices equal bar_raw (97,788 rows, 0 diffs); fingerprint rebuilt: 0
  changed rows of 2,511,070 for dates <= 09-21; returns rebuilt (2,518,273 rows): 4,621
  changed rows, all pending/data_ends -> resolved/terminal, 0 previously resolved
  outcomes changed; pytest 718 passed; describe-holdout reproduces the logged holdout.
- Backups (keep until Ben confirms all is well): `data/backups/pre-catchup-20261005-1121.dump`
  (241 MB) and `data/backups/artifacts-pre-catchup/` (592 MB). Both git-ignored.
- NOT rebuilt: structural feature set `data/processed/fingerprint/5_f6181075e5962796`
  lacks 09-22..10-02.

## Open problems (decisions for Ben)
- G2 is still open: `nightly_update.py:295` hardcodes `restated = False`, so every new
  corporate action silently seams its symbol. 12 symbols already carry stale `cafef`
  factors in build 5 (GLT, IRC, VHF, NST, PIS, PNP, ALT, CKV, QHW, THB, SBR, TDW).
- The nightly job is NOT scheduled; without it the forward clock stalls again. A launchd
  draft is owed (nothing installed without Ben's yes). Stopgap: run the dry run of
  `catch_up_upto.py` after each nightly as a restatement detector.
- UPCoM price-limit date conflict (2013-01-15 in `market_rules.yaml` vs 2015-07-01
  per the SSC notice) and early exchange bands remain unresolved.

## Research status (read this run; chart figures carried forward, not re-verified)
- Codex's v1/v2 chart detectors (double top/bottom, triangles) claim NO validated edge.
  v2: 3,172 episodes; only 590 of 1,657 pre-2024 confirmed breaks reached a gated
  outcome; best cell (descending-triangle/up) n=14, one of 40 trials on seen data.
- Only 15.8% of double-level episodes carry a prior-trend context: call them
  "repeated highs/lows" until a v3 label or gate is approved.
- 2012-2023 and the 2024-2026 holdout are spent; the forward record is the only clean
  confirmation.

## Deferred (not blocking)
- Report-faithfulness LLM eval: spec only (`docs/evals/report-faithfulness-eval.md`);
  no LLM surface exists yet.
- Rebuild of the structural feature set; flip of `broker_fee_provisional`.

## Next action and guardrails
1. Ben decides: commit (ledger, script, tests, memory) and the nightly schedule.
2. Run the daily scan and `paper record` each trading day; never score before
   recording; do not read a proposal as a recommendation.
3. Build G2 restatement detection into the nightly (or the stopgap above).
4. Freeze v3 chart rules (rename or prior-trend gate) only with Ben's approval and
   before looking at revised effects; keep v2 research-only.

## Session discipline
- Read this file, `knowledge/00-index.md`, then task-relevant notes/code.
- Log each run, rewrite this file from scratch, and verify numbers against git and
  stored manifests before replying.
