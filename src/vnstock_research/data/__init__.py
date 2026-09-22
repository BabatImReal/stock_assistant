"""Market data: fetch, store, and make comparable across corporate actions.

Doc §7.5 (what SSI FastConnect provides) and §4.3 (matched vs negotiated
volume).

Responsibilities, in the order data flows through them:

1. **SSI client** — authenticate with FastConnect Data (AccessToken) and call
   DailyStockPrice, DailyOhlc, DailyIndex, SecuritiesDetails. Credentials come
   from .env only, never from code.
2. **Download** — walk 2012 → today for every code, politely (the whole history
   is an overnight job, not weeks), and keep raw responses unchanged so a
   parsing mistake never costs a re-download.
3. **Storage** — PostgreSQL + TimescaleDB. ~5M daily candles, which is small.
4. **Price adjustment** — Vietnamese companies pay stock dividends and issue
   rights constantly, which put fake gaps in the chart. Unadjusted history makes
   patterns fire on events that never happened. The doc's approach: apply the
   ratio *adjusted close ÷ close* to open/high/low.

Nothing here is implemented yet, and deliberately so: Phase 3 probes the real
API first, because published field names and real payloads often differ, and a
schema built on assumptions has to be rebuilt.

Two unresolved blockers live in this module's territory — see
agent-memory/knowledge/open-questions.md, "must resolve before any measurement":
G1 (volume must be adjusted too, not just price) and G2 (SSI's adjusted close
may be re-stated after each new corporate action, which would make stored
history drift on every nightly update).
"""
