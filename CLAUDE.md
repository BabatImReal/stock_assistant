# VN Stock Pattern Researcher

## Project
A research tool for the Vietnamese stock market (HOSE, HNX, UPCoM). Ben is
the only end user. Every day it scans every stock code, compares recent
price and volume behaviour with what historically happened after similar
behaviour (2012 to now), and proposes ONE stock with evidence, or "nothing
strong today". This is research, not prediction. Ben makes every decision.

Source of truth: docs/knowledge/pattern-research-knowledge.md (never edit).

## Memory system: follow in EVERY session
Purpose: never scan the codebase to understand the project. Read your own
memory notes instead, because scanning code wastes tokens.

Structure:
  agent-memory/
    CURRENT_STATE.md       Rewritten after EVERY run. Max ~150 lines. Where
                           the project is now, what works, in progress, next
                           steps, open problems, blockers.
    knowledge/
      00-index.md          One line per knowledge file: what it covers
      project.md           Goal, user, framing, scope
      patterns.md          Pattern catalogue + fingerprint idea (doc §3)
      money-flow.md        Volume, matched vs deal, foreign flow (doc §4)
      context-vietnam.md   Trend, regime, sector, news, VN rules (doc §5)
      research-findings.md What studies say about reliability (doc §6)
      funnel-and-scale.md  Funnel, per-stock stats, scaling (doc §7)
      validation.md        How we avoid fooling ourselves (doc §8)
      architecture.md      Agents, code vs LLM split, data layer (doc §9-10)
      data-sources.md      SSI endpoints and fields; confirmed vs unconfirmed
      code-map.md          EVERY folder and file, one line each: purpose,
                           main functions, dependencies
      decisions.md         Date | decision | reason | rejected alternatives
      open-questions.md    Unresolved, for Ben or the broker friend
    logs/
      INDEX.md             One line per session: date | file | summary
      sessions/YYYY-MM-DD-session-NN.md

Knowledge files are your own understanding in your own words, not copies.
Reference the doc section, e.g. "(doc §4.3)". Keep them concise and condense
them when they grow.

Session file format (one file per Claude Code conversation):
  # Session YYYY-MM-DD-NN
  ## Session summary        UPSERT: rewrite after every run so it always
                            covers all runs so far
  ## Run N: <title>         APPEND one section per request from Ben:
     - Request
     - Done
     - Files created / modified / deleted (paths)
     - Decisions (also copy them to knowledge/decisions.md)
     - Problems, surprises, unfinished items
     - Next step

Start of every session, read in this order and nothing more unless needed:
  1. agent-memory/CURRENT_STATE.md
  2. agent-memory/knowledge/00-index.md
  3. Only the knowledge files the task needs
  4. Only the code files the task touches (find them via code-map.md;
     never scan the whole repo)
  Read logs/ only when history is needed. Then create the new session file
  and add it to logs/INDEX.md.

End of every run, before replying to Ben:
  - Append the run to the session file and upsert the session summary.
  - Rewrite CURRENT_STATE.md.
  - Update code-map.md if any file was added, repurposed or removed.
  - Update decisions.md / open-questions.md if relevant.
  - Update the matching knowledge file if you learned something new.
  - CURRENT_STATE.md is rewritten from scratch every run, never appended or
    patched. Before finishing a run, re-read it and check every number against
    the database or git.

Honesty rule: if a note disagrees with the actual code or data, the code or
data is correct. Fix the note immediately and log the correction in the run.
Never state that a file was written, a test passed or a task was done unless it
actually happened in this run. Say "not done yet" instead.
Never modify .env without asking first; propose the change instead.
Every fix must be proven by a check that fails without it (a test, or a query
showing the changed values). After editing, verify the edit applied; formatters
can change the text you matched on.

## Non-negotiable principles
- Deterministic code detects patterns and computes every number. LLMs only
  coordinate, read news and explain. No vision models. No ML training for
  now.
- Every pattern statistic is compared against the stock's base rate.
- Statistics are measured per stock, with fallback to group, then to the
  whole market, when samples are small.
- Real charts are layered: many patterns and cases fire at once. Each
  stock-day gets a full fingerprint (doc §3.6).
- Money flow uses MATCHED volume only, never negotiated/deal volume.
- Every dataset is reconciled against a second source before use.
  Mismatches beyond tolerance are flagged and excluded until explained.
- History window: 2012 to now. Prices adjusted for stock dividends and
  rights.
- Validation (doc §8): no look-ahead bias; parameters fixed before testing;
  discover/validate/holdout split; costs and VN rules (price limits, T+2,
  fees, 0.1% sale tax) always modelled.
- No pattern window or forward-return window may span a gap in trading.
- "No recommendation today" is a valid output.

## Working rules
- Explain the "why" in code comments. Ben is learning and must own this
  system.
- Ask Ben before any architectural decision.
- Never put secrets in code, memory files or git. Credentials live in .env
  only.
- Do only what the current phase allows (roadmap below).

## Roadmap
  Phase 1  Understand the doc, build memory               <- start here
  Phase 2  Project skeleton (uv, ruff, pytest, Docker with Timescale)
  Phase 3  Free-source probe (CafeF + vnstock) with reconciliation
  Later    Schema + full download, price adjustment, features, pattern
           rules, backtest, daily scan, report, agents, real-time layer.
  The current phase is recorded in CURRENT_STATE.md.
