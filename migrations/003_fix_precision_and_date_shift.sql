-- Two corrections found by the first run of the data-quality checks.
--
-- 1. bar_adjusted.matched_volume was numeric(20,2). Adjusted volume is
--    raw_volume / factor, and rounding THAT to two decimals is fine for a
--    million shares but not for ten: on a 10-share day with factor 0.3 the
--    stored value is off by up to 0.5%, which broke the traded-value
--    invariant on 479,511 rows. The invariant is the main proof that the G1
--    volume adjustment is right, so the storage has to be finer than the
--    check. Six decimals puts the rounding error below the tolerance even for
--    single-share days.
ALTER TABLE bar_adjusted
    ALTER COLUMN matched_volume TYPE numeric(24,6);

-- 2. CafeF sometimes dates a session one day late: on Saturday 2023-08-26 it
--    published 214 HNX bars whose values are Friday 2023-08-25's session
--    (verified against vnstock -- SHS's "Saturday" volume of 22,886,395 is
--    vnstock's Friday figure, and SHS has no Friday row in CafeF at all).
--    Those bars are real data with a wrong date, so the loader moves them to
--    the previous business day when that day is free for the symbol, and
--    records the move here rather than doing it invisibly.
ALTER TABLE bar_raw
    ADD COLUMN IF NOT EXISTS date_shifted boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN bar_raw.date_shifted IS
    'true when this bar was published by the source on a non-trading day and '
    'moved back to the previous business day at load time';
