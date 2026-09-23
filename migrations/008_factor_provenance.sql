-- Provenance for the backfill-seam rescale factors (G17, 2026-09-23).
--
-- scripts/check_backfill_seams.py multiplies a backfilled vnstock span by the
-- ratio that makes it meet CafeF at the seam, and stores that ratio as the
-- span's factor. It tagged the result source='vnstock', the same tag as the
-- plain backfill factors (exactly 1). So nothing could tell the two apart, and
-- the blocking "factor never above one" check failed on 15,670 rescale rows
-- (33 symbols, ratios 0.656..2.025).
--
-- 1. A distinct source, 'seam_rescale', plus a free-text reason.
-- 2. The existing rescale rows retagged. The rule is unambiguous (measured
--    2026-09-23): a 'vnstock' factor other than exactly 1 exists ONLY where the
--    seam rescale multiplied it -- one constant factor per symbol, always on a
--    backfilled vnstock bar; plain backfill factors are exactly 1.
-- The gate then exempts ONLY seam_rescale factors on backfilled bars
-- (data/checks.py FACTOR_ABOVE_ONE_SQL); any other factor above 1 still fails.
ALTER TABLE adjustment_factor ADD COLUMN IF NOT EXISTS reason text;

ALTER TABLE adjustment_factor DROP CONSTRAINT IF EXISTS adjustment_factor_source_check;
ALTER TABLE adjustment_factor ADD CONSTRAINT adjustment_factor_source_check
    CHECK (source IN ('cafef', 'inferred', 'vnstock', 'seam_rescale'));

UPDATE adjustment_factor
SET source = 'seam_rescale',
    reason = 'backfill seam rescale: vnstock span x ratio to meet CafeF '
             '(scripts/check_backfill_seams.py); factor = the seam ratio'
WHERE source = 'vnstock' AND factor <> 1;
