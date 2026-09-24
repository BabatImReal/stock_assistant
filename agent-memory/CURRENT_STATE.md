# Current state — 2026-09-24 (end of session 2026-09-23-03, run 20)

Rewritten from scratch. Checked this run: `git log`, the hypothesis log
(1,652 rows), the holdout results parquet, the stored returns (build 5),
`job_run`, pytest.

## Phase
**On main (`f53b72a`):** features, nightly hardening, exchange labels, the
pattern catalogue (T1–T4), the fingerprint (T5). Untouched; Ben merges.
**On `features/analog-backtest`:** design, E1, E2, E3, E4 and **THE HOLDOUT
(run once, 2026-09-24)**. Awaiting Ben's review.

## Git: ONE working branch, `features/analog-backtest`
1. The proposal `d6512e3`.
2. E1 `b4b601c`.
3. E2 `067f085`.
4. E3: registration `b3ca180`, then code `c132439`, then runs `0f9c763`.
5. E4: registration `a828418`, then code `e4671e5`, then `79262d6`.
6. **Holdout: the freeze + runner `4b01bc9` (before the run), then the run +
   log + report (commit 2).**

## The research result: complete
**E3:** N = 1,554 → 1,454 testable → 82 passed discovery → 16 held on
validate.

**THE HOLDOUT:**
- **Period:** 2024-01-01 → **F = 2026-09-10**, computed, not hardcoded. F is
  the session before the first entry with a pending outcome (2026-09-11,
  floor-deferred exits); the last settled session is 2026-09-21.
- **Result:** 16 → **6 ACCEPTED, 9 REJECTED, 1 NOT TESTABLE.**

ACCEPTED (edge, net exp per de-clustered occurrence, N, p):

| hypothesis | edge | net exp | N | p |
| --- | --- | --- | --- | --- |
| k3 marubozu_red + breadth_positive + rvol_high | +12.4% | +0.77% | 501 | 0.022 |
| k5 marubozu_red + ma_50_rising + rvol_high | +9.7% | +0.27% | 741 | 0.007 |
| k3 breakout + volume_dry | +9.5% | +0.67% | 46 | 0.087 |
| k3 three_black_crows + breadth_positive + rvol_high | +8.5% | +0.81% | 49 | 0.32 |
| k3 breakout + above_ma_50 + volume_dry | +3.7% | +0.44% | 34 | 0.64 |
| k3 higher_lows + breadth_positive + ma_50_rising | +3.3% | +0.17% | 508 | 0.34 |

**The honest reading:**
- Only the first 2 are both accepted AND significant.
- 8 rejects kept a positive edge but net ≤ 0 at the registered 0.40%. 5 of
  them flip to ACCEPT at 0.10% all-in, and 4 at 0.25%.
- 1 reject flipped sign: k3 three_black_crows + market_up + rvol_high.
- Not testable: k3 breakout + ma_50_rising + volume_dry (24 de-clustered).
- The report is `research/reports/holdout-2026-09-10.txt`.
- The log carries slice "holdout": 16 rows, protocol `0106fab4dc2f35a2`,
  code `e578e531d4fd14c3`, build 5.
- **The holdout is spent. It may never be run again.**

## The engine
- **Limits:** `checks.limit_prices`.
- **Returns:** `forward_returns` (net PROVISIONAL).
- **G20:** factor defects blanked like gaps.
- **Gate + evidence:** `backtest/evidence.py`.
- **Protocol:** `backtest/protocol.py`:
  - `discover` / `validate` / `summary`;
  - `freeze` / `holdout` (refuses a second run);
  - `run` still refuses "holdout".
- **Look-alikes:** `backtest/neighbours.py` (ILLUSTRATIVE; its pool still
  stops before 2024).

## Verified by running it this run
- pytest **537 passed, 0 failed, 0 skipped**; `ruff check .` clean.
- Strict proofs:
  - holdout **33/33**, E3 33/33, E4 23/23 (all re-run);
  - earlier and unchanged: E2 46, E1 50, fingerprint 27, universe/breadth 17,
    sector 23, exchange 15, guards 5, T1 23, T2 36, T3 55, T4 20.

## Blockers / open (for Ben: open-questions.md, "The holdout")
- **The broker fee is now decisive** (5 rejects hinge on it). NET is
  provisional.
- How G9 should weigh the weak-p accepts.
- 2026 is weaker for several survivors.
- `pool_before` for the look-alikes (a new neighbours version).
- G20 repair; X4, G19, G18, G2, G9, G10, G11.
- The limit rounding rules and UPCoM's reference are still to be confirmed.

## Rule to remember when judging missing data
The market is closed on Saturday, Sunday and public holidays
(`config/rules/holidays.yaml`). A missing day is only a defect when it is a
weekday the market was open.

## Next steps
1. Ben reviews the holdout; Ben merges.
2. G9: ranking to one pick, on the accepted survivors, with the fee confirmed.
3. The daily scan and report.

## Parked
TypeSafe / Jev; SSI FastConnect; flag/pause (P7); pattern strength numbers
(P9); precomputing market/sector per fingerprint build; target-before-stop.

## Reading order for the next session
1. This file. 2. `knowledge/00-index.md`. 3. Run 20 of
`logs/sessions/2026-09-23-session-03.md`. 4. `config/rules/protocol.yaml`,
`knowledge/validation.md`, `research/reports/holdout-2026-09-10.txt`.
5. Only the code the task touches, via `code-map.md`.
