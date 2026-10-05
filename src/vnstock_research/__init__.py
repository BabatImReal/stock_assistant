"""VN stock research tool (HOSE, HNX, UPCoM).

Goal: ONE or TWO stocks with a tested, evidenced reason, or "nothing strong today".
Research, not prediction; Ben decides. The pattern-matching method was retired on
2026-10-06 (see agent-memory/knowledge/decisions.md); what remains is the data layer:

    data      -> raw market data in, adjusted candles out
    features  -> candle loaders (bars.py)

A new method is being designed; nothing here picks stocks yet.
"""
