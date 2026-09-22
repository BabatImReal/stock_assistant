-- Turn the time-series tables into Timescale hypertables.
--
-- Chunked by YEAR, not by Timescale's 7-day default. The whole dataset is only
-- a few million rows across 26 years, so weekly chunks would create well over a
-- thousand of them -- more planning overhead than the partitioning saves. A
-- year per chunk gives ~26 chunks and matches how the data is actually queried:
-- whole histories per symbol, and year-by-year result reporting (doc §8.1).
--
-- At this size plain PostgreSQL would cope fine. Timescale is already running
-- and costs nothing here, so we use it -- but nothing depends on it.

SELECT create_hypertable('bar_raw', 'trade_date',
                         chunk_time_interval => INTERVAL '1 year',
                         if_not_exists => TRUE, migrate_data => TRUE);

SELECT create_hypertable('bar_adjusted', 'trade_date',
                         chunk_time_interval => INTERVAL '1 year',
                         if_not_exists => TRUE, migrate_data => TRUE);

SELECT create_hypertable('adjustment_factor', 'trade_date',
                         chunk_time_interval => INTERVAL '1 year',
                         if_not_exists => TRUE, migrate_data => TRUE);

SELECT create_hypertable('negotiated_volume', 'trade_date',
                         chunk_time_interval => INTERVAL '1 year',
                         if_not_exists => TRUE, migrate_data => TRUE);

-- Lookups are almost always "this symbol, over this period", so symbol leads.
CREATE INDEX IF NOT EXISTS bar_raw_symbol_date_idx
    ON bar_raw (symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS bar_adjusted_symbol_date_idx
    ON bar_adjusted (symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS adjustment_factor_symbol_date_idx
    ON adjustment_factor (symbol, trade_date DESC);
CREATE INDEX IF NOT EXISTS negotiated_volume_symbol_date_idx
    ON negotiated_volume (symbol, trade_date DESC);

-- The daily scan reads "every stock on this date" from the current build, so
-- that direction needs its own index.
CREATE INDEX IF NOT EXISTS bar_adjusted_build_date_idx
    ON bar_adjusted (build_id, trade_date DESC);
