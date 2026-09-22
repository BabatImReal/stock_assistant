# Decisions

Format: Date | Decision | Reason | Rejected alternatives

| Date | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| 2026-09-22 (from doc) | Research tool, not prediction/auto-trading | Claims about measured history are checkable; also keeps clear of VN investment-advisory licensing since Ben is the only user | advisory product, auto-trading bot |
| 2026-09-22 (from doc) | **Rules-based** pattern detection in deterministic code | Exact, repeatable, free, explainable to the broker friend | vision model on chart images (a blurrier copy of data we already have exactly); ML training (memorises noise, cannot explain itself) — ML reconsidered later only to *rank* rule signals |
| 2026-09-22 (from doc) | History window **2012 → now**, daily/weekly/monthly | Broker friend studied from ~2010; 2012 skips the most distorted post-crisis years | 2010 start; shorter 5-year window |
| 2026-09-22 (from doc) | **EOD daily data first**; real-time streaming layer deferred | A 3–5 day horizon does not need intraday; minute data is ~200× larger | building the streaming pipeline first |
| 2026-09-22 (from doc §11.5) | **No message broker**; go direct, Redis pub/sub as a seam later | Avoids infrastructure the current scope does not need | Kafka/RabbitMQ from the v0.1 brief |
| 2026-09-22 (from doc) | Stack: SSI FastConnect → PostgreSQL + TimescaleDB, ~$6/month hosting, Telegram + web report | Carried over from the v0.1 platform brief as the data foundation | other data vendors (kept as backup if SSI history is short) |
| 2026-09-22 (from doc §4.3) | Money flow uses **matched volume only** | Negotiated block deals are not market demand and would fake accumulation | using total reported volume |
| 2026-09-22 (from doc §7.1) | Per-stock statistics with **stock → group → market** fallback | Most patterns fire only a few dozen times per stock in 15 years | global statistics only |
| 2026-09-22 (from doc §8.2) | Discover / validate / untouched-holdout split + walk-forward + paper trading before any real money | Tens of thousands of combinations guarantee lucky-looking results | single backtest over all history |
| 2026-09-22 (from doc §3.5) | Pattern thresholds fixed at textbook values first, stored as **config not code** | Choosing thresholds that look best on history is the classic self-deception | tuning parameters during discovery |
| 2026-09-22 (from doc §7.3) | "No recommendation today" is a valid output | A tool forced to pick daily will invent bad picks | always produce a top-ranked stock |
| 2026-09-22 (from doc §9.2) | Build the **deterministic pipeline first**, add agents only where judgement is needed | Most of the pipeline is a fixed sequence; agents earn their place at news, conflict and Q&A | multi-agent framework from day one |
| 2026-09-22 (session 01) | Phase 3 probes SSI **before** any schema design | Docs and real payloads often differ; a schema built on assumed field names would have to be rebuilt | designing the schema from the doc's §7.5 field list |

Related: [[architecture]] [[validation]] [[open-questions]]
