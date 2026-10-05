# Eval spec: report-faithfulness (the Reasoner / write-up step)

Status: **design only, not built.** There is no LLM surface yet (no `anthropic`
dependency, no `messages.create`; the write-up step that an LLM would own does
not exist). The deterministic half it will sit on top of **does** exist:
`report/scan.py` already computes the full evidence report. This document fixes
the eval's shape now so that, when the explain/write-up step lands, the runner is
a fill-in-the-blanks job. Build it via `/claude-api build-eval` once the
"Deferred — build when" box is ticked.

## What already exists vs what the LLM would add

- **Exists (deterministic):** `report/scan.py` — `pick(conn, day) -> Pick` and
  `daily_scan(conn, day)`, which assemble the evidence report (header, regime,
  funnel, entry plan, per-trade validate/holdout, base rate stock→tier→market,
  look-alikes, runners-up, or `NOTHING STRONG TODAY`) and write it to
  `research/reports/scan-<day>.txt`. `report/paper.py` keeps the real ledger.
  A real report already exists: `research/reports/scan-2026-09-21.txt`. Only
  `report/__init__.py` is a docstring.
- **The LLM would add (doesn't exist):** turning that computed evidence into the
  prose *case Ben can argue with* (doc §7.4) — the narrative, the weighing of
  bull vs bear — using **only** numbers the code produced, citing them, and
  saying when a number is missing rather than inventing one (doc §9.3,
  architecture.md:6-8, 21).

So this is a **grounding / faithfulness** eval of a narration step whose entire
input is already-computed numbers. That makes the headline check deterministic,
and it encodes the project's #1 non-negotiable directly.

Not in scope (separate evals, one flow each): the News worker (veto extraction
from news text) and the Orchestrator's pick-vs-nothing decision — that last is
deterministic funnel code, validated by `test_holdout.py` / validation.md, not an
LLM eval.

## The entry point (call it, don't reconstruct it)

```
report.write_case(pick: Pick, stats: ScanStats) -> CaseText
```

The input is the **existing** `Pick` object plus the computed stat lines
`daily_scan` already produces — not an invented bundle. `Pick` carries: `day`,
`proposal` (chosen candidate or `None` = nothing strong), `ranked`, `candidates`,
`liquid`, `regime`, `build_id`, `featureset`, `fp_code`; `ScanStats` is the
per-trade validate/holdout expectancy, base rates, entry plan, and runners-up the
report functions compute. Output is the prose case; a structured `citations` list
(number → source field id) is worth adding to the entry point so grading is exact
rather than text-extracted.

The runner calls this real function (build-eval's rule: never rebuild the Claude
call from the prompt — exercise the real context assembly).

## Input set (cases)

One case = one `(Pick, ScanStats)` for a settled day. Target 15–100, stratified
by the write-up's situation as `tags[0]`:

| `tags[0]` split | what it is | guards against |
|---|---|---|
| `strong_pick` | clear edge over base rate | normal happy path |
| `marginal` | small edge, thin sample | over-selling a weak case |
| `nothing_today` | `proposal is None` | **inventing a pick** (doc §7.3) |
| `missing_data` | a stat is `n/a` / absent in the bundle | **inventing the number** vs flagging it (§9.3) |
| `conflicting` | strong bull *and* strong bear signals | hiding the bearish side (§3.6) |

Both directions must be covered (eval-audit §1): `nothing_today` and
`missing_data` are as important as the picks, or an always-confident write-up
scores well. Source order (build-eval Step 1): real `Pick`s replayed from the
pipeline over historical days (highest fidelity — the machinery already emits
them) → a handful hand-built to force the `nothing_today` / `missing_data` /
`conflicting` corners that are rare in real history.

## Grading

Primary graders are **programmatic** (deterministic, free, exactly the project's
rule). A judge is secondary, for taste a check can't see.

**Headline = a conjunction** (listed first so it drives the report). An empty or
constant write-up must score ~0, so "faithful" alone can't be the headline — a
blank answer fabricates nothing:

| metric id | kind | definition |
|---|---|---|
| `sound` | binary | **headline.** `faithful` AND, on a pick, required elements present; on a negative, correctly silent (`nothing_today`) or gap-flagged (`missing_data`) |
| `faithful` | binary | every number in the output traces to a bundle field within tolerance (component of `sound`) |
| `citations_complete` | number | fraction of stated stats that carry a citation |
| `elements_present` | binary | on a pick: the case states the proposal, its edge-vs-base-rate, the entry plan numbers, and the bearish side† |
| `negatives_ok` | binary | on `nothing_today`: no pick invented; on `missing_data`: the gap named, no value invented |
| `case_quality` | number | coherence, bearish side given fair weight, non-circular reasoning — LLM judge, pointwise rubric |

† The bearish column (doc §3.6) is **a pipeline prerequisite**: `scan.py` does not
emit a bull/bear split today, so `elements_present` may only grade it once the
evidence carries it. Until then grade the elements the bundle actually provides —
otherwise the LLM is marked down for data it was never given.

Two grader rules this project forces:

- **A number the model derived itself is fabricated unless the bundle carries
  it** — `edge = hit − base`, "6 of 9", a computed % change (architecture.md:6-8:
  every number comes from a tool, never the agent's arithmetic). The faithful
  check must recompute/match, not just substring-scan.
- **Normalize before matching**: VN thousand separators (`25.300` = 25300),
  fraction vs percent (`0.534` ≡ `53%`), and the report's own `n/a` sentinel
  (`_pct`), so a correct number isn't flagged on formatting.

Confusion matrix on the pick decision (positives = pick bundles, negatives =
`nothing_today`): report precision/recall on "emit a pick" and specificity on
"correctly stayed silent", not one accuracy number.

Judge: choose model at build time (`claude-haiku-4-5` / `claude-sonnet-5-5` /
`claude-opus-5-5`); never the model-under-test as its own judge; structured
output; rubric as concrete checkable claims; calibrate against ~a few dozen
human labels and test on known negatives (empty, "I don't know", confident wrong
answer) per eval-audit §4.

Side-channel columns: output length, latency, cost, `refusal`, `max_tokens`.

## Why this is the right eval

- It turns the project's non-negotiable into a number: `faithful` fails the
  moment the write-up uses a figure the code didn't produce.
- The headline is deterministic — cheap enough for every prompt change, and not
  gameable by a lenient judge (and `sound` can't be won with an empty answer).
- `nothing_today` + `missing_data` guard the two failures the doc names:
  inventing a pick, and inventing a number.

## Deferred — build when ALL of these are true

- [ ] The write-up entry point exists and returns case text
      (ideally text + structured `citations`).
- [ ] The evidence passed in is stable enough for the grader to read
      field-by-field (`Pick` already is; `ScanStats` shape pinned).
- [ ] `anthropic` added as a dependency; judge model chosen.
- [x] Real evidence exists to seed cases (`Pick` replay + `research/reports/scan-*.txt`).

Before the first paid run (eval-audit §2, §5): push an **oracle** (a hand-faithful
write-up → ~100% `sound`) and a **null** (empty, and "Buy FPT." with no numbers →
~0%) through the grader; put the noise floor (~`1/sqrt(n·reps)`) next to the
change worth shipping. When built, follow `/claude-api build-eval` Step 3:
`.claude/hillclimb/report-faithfulness/baseline/{results.jsonl,traces/}`, report
via `shared/evals/report/build-report-lite.mjs`. Both sign-offs (inputs, grading)
still required with Ben.
