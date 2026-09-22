"""VN Stock Pattern Researcher.

A research tool for the Vietnamese stock market (HOSE, HNX, UPCoM). It scans
every listed code daily, compares recent price and volume behaviour with what
historically followed similar behaviour since 2012, and proposes one stock with
its evidence — or says "nothing strong today".

Source of truth: docs/knowledge/pattern-research-knowledge.md (never edited).

The package is deliberately split along the pipeline the document describes, so
that each stage can be tested on its own:

    data      → raw market data in, adjusted candles out   (doc §7.5)
    features  → candles in, measures out                   (doc §4-5)
    patterns  → measures in, pattern flags out             (doc §3)
    backtest  → flags in, measured statistics out          (doc §2, §8)
    report    → statistics in, one recommendation out      (doc §7.4)

The rule that shapes all of it (doc §9, §10.3): deterministic code computes
every number; an LLM only reads news, weighs conflicting evidence and explains.
"""
