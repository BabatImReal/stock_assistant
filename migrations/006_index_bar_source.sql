-- index_bar.source. CafeF's index file loses whole sessions (2024-05-17 and
-- 2026-07-02 for VNINDEX, found 2026-09-23). A single missing index day NaNs
-- every 50-session regime window that crosses it, so those days are backfilled
-- from vnstock -- but only where vnstock agrees with CafeF on the neighbouring
-- sessions (scripts/backfill_index_gaps.py). The second source must stay
-- visible, as with bar_raw.source and adjustment_factor.source: its VOLUME is
-- defined differently (6-9% off CafeF's), so nothing may compare the two.
ALTER TABLE index_bar
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'cafef'
    CHECK (source IN ('cafef', 'vnstock'));
