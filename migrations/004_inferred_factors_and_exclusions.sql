-- Two additions for handling corporate actions CafeF did not adjust for.
--
-- 1. adjustment_factor.source. Most factors come from CafeF's adjusted-vs-raw
--    file pair. A few are INFERRED by us, where the price gapped by a round
--    stock-dividend ratio that the second source does not show and the volume
--    jumped to match. An inferred factor is still a derivation -- bar_raw is
--    untouched -- but it is a weaker kind of evidence than a published one and
--    must be visible as such, not silently mixed in.
ALTER TABLE adjustment_factor
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'cafef'
    CHECK (source IN ('cafef', 'inferred', 'vnstock'));

-- 2. Windows research must not read.
--    Where a factor could NOT be inferred, the adjusted series contains a gap
--    that never happened in the market. Any feature whose lookback covers that
--    day is wrong, and so is any forward return that spans it, so the excluded
--    span is much wider than the event itself: the longest feature lookback
--    before it and the longest forward window after it.
CREATE TABLE IF NOT EXISTS excluded_window (
    symbol      text NOT NULL,
    valid_from  date NOT NULL,
    valid_to    date NOT NULL,
    reason      text NOT NULL,
    event_date  date,
    detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, valid_from, reason),
    CHECK (valid_to >= valid_from)
);

COMMENT ON TABLE excluded_window IS
    'Spans research must skip. Data is never deleted for these -- the raw bars '
    'remain -- but no feature, pattern or forward return may be computed on a '
    'day inside one.';

CREATE INDEX IF NOT EXISTS excluded_window_symbol_idx
    ON excluded_window (symbol, valid_from);
