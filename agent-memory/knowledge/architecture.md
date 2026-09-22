# Architecture: agents and the code/LLM split (doc §9-10)

**Status: concept only. Nothing here is for implementation yet.**

## The key principle (§9)
**Agents coordinate and explain; deterministic code computes.** Every number an
agent uses must come from a tool that calculated it, never from the agent's own
estimate — otherwise agents argue about numbers instead of computing them.

Shape: data layer (SSI → database: OHLCV, matched vs negotiated volume, foreign
flow) → deterministic tools (pattern detector, volume metrics, context metrics,
backtest stats) → orchestrator + workers → daily report to Ben (Telegram + web).

## Roles (§9.1)
| Role | Job | Code or LLM |
| --- | --- | --- |
| Scanner | run all pattern and money-flow rules on today's data for every code | code |
| Filter | liquidity, regime, "strong on this stock" → shortlist | code |
| Analyst | pull historical stats, context, sector for each shortlisted stock | code gathers, LLM may summarise |
| News worker (later) | read recent news, flag vetoes | LLM |
| Reasoner | weigh evidence, compare candidates, write the case for and against | LLM, using only tool-provided numbers |
| Orchestrator | run the daily sequence, decide pick vs nothing, send the report | control logic + LLM for the write-up |

## Honest note (§9.2)
Most of the pipeline is a fixed sequence (scan → filter → analyse → reason), so
it could just be ordinary code with one LLM step at the end. Agents earn their
place only where judgement is genuinely needed: reading news, resolving
conflicting evidence, answering Ben's follow-ups ("why not stock Y?").
**Path: build the deterministic pipeline first, add agents later.**

## Reasoner guardrails (§9.3)
Cite the numbers used (occurrences, hit rate, base rate); always include the
case **against** and the stop level; be allowed and encouraged to say "nothing
strong today"; never invent a statistic — say when one is missing.

## Why no vision model (§10.1)
The chart is *drawn from* OHLCV, so an image is a blurrier copy of data we
already have exactly. Arithmetic is exact, instant across 1,500 codes, free,
and deterministic. A vision model is slower, costs per image, and can invent
shapes.

## Why no ML training (§10.2)
Price data is mostly noise and ML is excellent at memorising noise that looks
like signal. It also cannot explain itself, so the broker friend could not
argue with it. **Rules first, measured honestly.** ML may later be reconsidered
to *rank* rule-based signals — never as a black box.

## The split (§10.3)
Code: store/clean data, detect patterns, compute volume and context metrics,
measure historical hit rates, filter and rank.
LLM: read news, weigh conflicting evidence and write the reasoning, answer
Ben's questions.
In one line: **code counts what happened; the LLM explains the counts.**

## Data foundation (§11.5)
The earlier v0.1 platform brief (SSI streaming, Redis, TimescaleDB, ~$6/month
hosting) stands as the data foundation, with two changes: **no message broker**
(go direct, Redis pub/sub as a seam), and the product is this researcher, not a
dashboard. **End-of-day daily data is enough to start**; real-time comes later.

Related: [[data-sources]] [[funnel-and-scale]] [[decisions]]
