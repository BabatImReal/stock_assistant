# Current state — 2026-10-06 (session 2026-10-05-01, run 17)

## Where the project is
- GOAL (unchanged): recommend ONE (max TWO) stock(s) with a tested, evidenced reason, or "nothing strong today".
  Research, not prediction; Ben decides. Ben's constraints: NO purchased data, no real-time, no broker; he wants a good
  result before considering any spending; he is tired of work without results.
- The pattern method and all its products are RETIRED AND DELETED (commit 86de0af; decision 2026-10-06). Git history
  keeps them. Nothing picks stocks now. The launchd job is stopped and its plist removed.
- What remains = data layer: `src/vnstock_research/data/*`, `features/bars.py`, `scripts/*` (data loading/repair),
  `config/rules/{costs,holidays,market_rules,universe}.yaml`, `migrations/`, DB (Docker), `data/raw`, DB dumps in
  `data/backups`. 116 tests pass. `scripts/daily_run.py` is data-only (loads the newest CafeF day + sector snapshot);
  smoke-run OK 10-06; NOT scheduled. Prices are loaded through 2026-10-05 only: run `daily_run.py` or
  `catch_up_upto.py` before any new research to bring them current.
- Still on disk, git-ignored, old-method leftovers Ben must delete himself (the safety check blocked my `rm -rf`):
  `data/processed/*` (~1.3 GB), `data/backups/artifacts-*` (~1.7 GB), `data/reports/{daily-*,chart_audit_v*,features-*}`.

## Probe results (2026-10-06)
- Fundamentals via free APIs FAIL: vnstock community = last 4 quarters; KBS and VCI disagree on period labels; no
  announcement dates. TCBS raw API is Cloudflare-blocked (not circumvented). CafeF bulk files have no financials.
- CafeF public financial-statement PAGES do serve history: `cafef.vn/du-lieu/bao-cao-tai-chinh/<sym>/incsta/<year>/<q>/0/0/...`
  returned FPT 2013 with 4 quarters of the income statement (values in VND). Untested: balance sheet pages, delisted
  symbols, restatement behaviour, how many pages (~700 symbols x ~14 years x 2 statements) and CafeF's terms.
- Foreign-flow files (CafeF CC_/NN_ Upto) cover 2006+ (4,925 dates); column meaning not decoded.

## Proposed new method (awaiting Ben's yes; nothing built)
Fundamental value + profitability on liquid stocks, held monthly (turnover low enough that 0.4% costs do not kill it).
Evidence: Vietnam value premium positive 2013-2023 (HML ~0.6%/month 2008-15), profitability +0.34%/month, EPS and BVPS
priced (631 firms 2009-2024). Data: scrape CafeF statements politely, conservative fixed publication lag (quarter end
+ 45 days, year end + 90), reconcile against vnstock's last 4 quarters, check delisted coverage first.
Pre-register BEFORE results: <=3 factors with literature signs (earnings yield, book-to-market, ROE), liquid tier only,
monthly rebalance, periods 2012-19 / 2020-23 / 2024-26, kill rule = top group net-positive vs liquid universe in BOTH
later periods, else stop. Analyst layer (LLM reads financials/news for the top few) only after the group passes.

## Progress scoreboard
- Research answer ("is there an evidenced edge on free data?"): open, 0 evidence. Ready-for-money: ~0% (no method).
- Past work verdict: engine unconfirmed (1,554 candidates -> 6 accepted, 1 of 16 holdout p<0.05, ~0.11 corrected,
  -0.43%/signal day for that one; forward record 0/30), chart formations ~ market, cross-sectional score ~0 since 2020.

## Next action
1. Ben: yes/no on the CafeF-scraping fundamentals plan; delete leftovers (commands given in chat).
2. If yes: probe 5 symbols incl. a delisted one (statements, restatement, coverage), then write the pre-registration
   (commit before any result), then scrape, then test once.

## Session discipline
Read this file, `knowledge/00-index.md`, then task-relevant notes/code. Log each run; rewrite this file from scratch.
