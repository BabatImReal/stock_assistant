# Current state — 2026-10-02 (session 2026-10-01-01, run 4)

## Purpose and boundary
- Private end-of-day Vietnamese stock research for Ben: HOSE, HNX, UPCoM.
- Deterministic code measures prices, patterns and returns; LLMs coordinate
  and explain. "Nothing strong today" is valid. This chart branch does not
  deliver an individual-stock report or change the existing daily scanner.
- Source of truth: `docs/knowledge/pattern-research-knowledge.md` (never edit).
- Phase: research-only chart formations beyond the original phase roadmap;
  no chart family is approved for recommendation or production promotion.

## Branch and approvals
- Branch `codex/pattern-research-next-step` was cut from
  `claude/design-system-pattern-history-aqbkd8` at `0e00a1f`. Only Ben merges.
- Ben approved a five-variant price-only pilot, a fixed v1 visual audit,
  separate observed up/down hypotheses, and v2 full-formation containment.
- V1 registration/detector/calendar/report commits: `0bfdf5a`, `5a931f6`,
  `d7b980f`, `74de8de`; fixed audit commits: `e8e4ff5`, `95cc733`.
- V2 registration `03c5105` preceded side-specific outcome inspection;
  detector/test `1772550` preceded the census; report `746f419` followed it.
- Preserve unrelated dirty/untracked files. Production scan/E3, `.env`, and
  the source document were not modified by the chart research or AI review.

## Chart research measured so far
- V1 rules: double top/bottom and symmetric/ascending/descending triangles,
  k=10 primary and 3/5/20 secondary. Promoted build 5 has 2,511,070
  stock-days across 1,705 symbols and 3,965 candidate episodes on 844
  symbols; 2,770 confirmed breaks. Artifact:
  `data/processed/chart_research/5_714965cdc639e7ac_f019f46d9336aa38/`.
- The fixed, event-return-blind 25-chart v1 audit replayed all 25 causally;
  3 of 20 confirmed triangles exceeded their eventual formation wall.
  `reports/chart-pattern-geometry-audit-2026-10-01.md` explains the sample
  limitation and range-like double-level ambiguity.
- V2 requires every first-through-last-anchor adjusted close inside its
  frozen walls at the existing family tolerance (1.5% repeated levels,
  1% triangles); v1's 0.5% last-anchor-to-candidate no-early-break check
  remains. Ten variant×side signals across four horizons make 40 registered
  trials. A down break remains a long-only risk hypothesis, not a short.
- V2 artifact:
  `data/processed/chart_research_v2/5_92c387181435be5a_9ef457b528d8d70f/`.
  Its manifests record 2,511,070 signal rows / 1,705 symbols and 3,172
  candidate episodes / 796 symbols. The v2 report records 1,133 confirmed
  up and 1,167 confirmed down breaks. It reuses version-checked v1 returns;
  v1 and the production scanner remain unchanged.
- `reports/chart-pattern-v2-2026-10-02.md` describes all ten primary-horizon
  side cells over already-seen 2012–2019 and 2020–2023 periods. The
  attractive-looking later descending-triangle/up cell has only 14 eligible
  cases. These periods are spent and **not** fresh predictive validation.
  Already-computed 2024–2026 outcomes cannot become a new holdout by renaming.

## Run 4 AI broker-style review
- Ben has no broker reviewer and requested a subagent critique. The
  source-linked `reports/Vietnam chart pattern broker review.md` examines
  chart semantics, causal breaks, Vietnam execution, pooled statistics, and
  next research gates. Notes are at
  `research_notes/Vietnam chart pattern broker review/reviewer.md`.
- This is **not** a licensed broker's opinion, investment advice, a blind v2
  chart-sample audit, new outcome test, or stock-strength verdict. The
  reviewer did not inspect 2024–2026 returns or edit code/config.
- Geometry containment fixes a known v1 flaw but does not establish prior-
  trend reversal labels or fillable trades. A first 0.5% wall cross is an
  observed event. The 40-trial, small-count, pooled spent-history table
  cannot measure an individual stock's strength or justify a recommendation.

## Next action and guardrails
1. Hash-select and assess a fixed *v2* event-date-only chart sample using a
   documented rubric: recognizable/range-like/ambiguous geometry, prior
   trend, wall containment, break significance and matched-volume context.
   Disclose that an AI rubric is not independent broker certification.
2. On spent history only, produce an execution/attrition ledger by side,
   exchange and year: candidate → confirmed → liquid → model-fillable →
   resolved. Surface ceiling rejects, floor-held/unresolved exits, intended
   order size/slippage and actual fee sensitivity; verify dated VN rules.
3. Freeze any justified correction as v3 before inspecting revised effects.
   Timestamp new days prospectively, then evaluate the whole registered
   family with multiplicity, costs, stock→tier→market fallback and one-pick-
   per-day/no-signal behavior. No v2 scan promotion now.
- UPCoM historical price-limit dating/fillability and actual broker fees
  remain unresolved. Rectangles, flags, matched-volume combinations, and
  individual stock reports remain separately approved future work.

## Session discipline
- Read this file, `knowledge/00-index.md`, then task-relevant notes/code.
- Log each run, rewrite this file from scratch, and verify numbers against
  git and stored manifests before replying.
