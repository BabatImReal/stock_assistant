-- symbol_industry: dated snapshots of each symbol's industry (doc §5.4).
--
-- The only free source (vnstock VCI, ICB) publishes CURRENT membership with no
-- history. So membership is only point-in-time from the first snapshot on:
-- each fetch writes a new dated snapshot (scripts/snapshot_industry.py), and a
-- date is judged by the latest snapshot on or before it. Dates before the
-- first snapshot can only borrow the earliest labels, and every value built on
-- them is FLAGGED (decisions.md 2026-09-23): exploratory, quarantined from
-- validated backtest results.
--
-- Only the ICB levels the sector rule uses are kept: level 2 is the sector,
-- and level 4 exists for the one documented exception (steel split out of
-- basic resources; data/sectors.py).
CREATE TABLE IF NOT EXISTS symbol_industry (
    symbol         text NOT NULL CHECK (symbol ~ '^[A-Z]{3}$'),
    snapshot_date  date NOT NULL,
    source         text NOT NULL,
    icb_l2         text NOT NULL,
    icb_l2_name    text NOT NULL,
    icb_l4         text NOT NULL,
    icb_l4_name    text NOT NULL,
    PRIMARY KEY (symbol, snapshot_date, source)
);
