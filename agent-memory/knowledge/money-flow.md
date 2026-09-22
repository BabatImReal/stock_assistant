# Money flow and volume (doc §4)

Ben's correction to a pattern-only view: **a candle shape without volume behind
it is just a drawing.** Heavy volume sustained over 5–7 days means real capital
is entering the company (accumulation), and that is often more informative than
the shape. So volume is a **first-class signal**, defined and measured exactly
like a pattern: write the rule, find every occurrence, count what happened next.

## Measures to compute (§4.1)
| Measure | Definition | Reads as |
| --- | --- | --- |
| RVOL | today's volume ÷ 20-day average | >1.5–2× = unusual interest |
| Sustained volume | days in last 5–7 with RVOL > 1.5 | persistent inflow, not a one-day spike |
| Up- vs down-volume | volume on green days vs red days over N days | who is in control |
| Price–volume agreement | price up **and** volume up | healthy move |
| Divergence | price up while volume shrinks | move running out of fuel |
| Traded value | price × volume in VND | real money; comparable across cheap and expensive stocks |
| Dry-up | volume well below average during a pause | sellers exhausted, often precedes a breakout |

## Volume as a filter (§4.2)
Every pattern is measured **twice**: on its own, and only when volume confirms
(e.g. RVOL ≥ 1.5 on the signal day). Published tests consistently find the
confirmed version better. If that holds on VN data, keep only the confirmed
version.

## Matched vs negotiated — the Vietnam-specific edge (§4.3)
Reported VN volume mixes two things:
- **Matched / khớp lệnh** — the real order-book auction.
- **Negotiated / thỏa thuận (block, deal)** — pre-agreed transfers, often huge,
  not market demand.

A stock can print enormous volume that was one negotiated block. That is **not**
accumulation. All money-flow measures use **matched volume only**. This is a
non-negotiable principle in CLAUDE.md and one of the real advantages this tool
has over generic charting software.

Good news for the data layer: SSI's DailyStockPrice returns the split
([[data-sources]]).

## Foreign and proprietary flow (§4.4) — later layer
The exchanges publish foreign net buy/sell; brokers track proprietary-desk
(tự doanh) flow. Persistent foreign net buying is widely watched as "smart
money". Candidate signal to test *after* the core works. Ask the broker friend
how much weight he actually gives it ([[open-questions]]).

Related: [[patterns]] [[context-vietnam]] [[data-sources]]
