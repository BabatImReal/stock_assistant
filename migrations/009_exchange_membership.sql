-- exchange_membership: which exchange a symbol was on, ONLY where that is dated
-- by evidence (Ben, 2026-09-23; data/exchanges.py).
--
-- bar_raw.exchange is the exchange CafeF FILED the row under, which for some
-- symbols is today's exchange applied to their whole history: DPG sits in the
-- HSX file from 2017 but joined HOSE on 2018-05-22, and the 46 vnstock
-- backfills (ACB: HNX until 2020-12) carry today's label. Per-exchange rules
-- (price limits, G3 ceiling/floor) need the exchange IN FORCE on the date.
--
-- Two kinds of evidence:
--   cafef_transfer  both spans of a CafeF-documented transfer (G4 Class A: the
--                   symbol trades in two exchange files, each dated);
--   kbs_listing     vnstock KBS overview.listing_date: the symbol has been on
--                   its CURRENT exchange since that date (valid_to NULL).
-- A date covered by neither is UNKNOWN: consumers borrow the filed exchange
-- and FLAG the result, and the backtest quarantines it (quarantine_flagged).
-- Derived and rebuildable (exchanges.rebuild) from symbol_exchange and the
-- cached KBS answers in data/raw/kbs_listing/.
CREATE TABLE IF NOT EXISTS exchange_membership (
    symbol      text NOT NULL CHECK (symbol ~ '^[A-Z]{3}$'),
    exchange    text NOT NULL CHECK (exchange IN ('HOSE', 'HNX', 'UPCOM')),
    valid_from  date NOT NULL,
    valid_to    date,
    source      text NOT NULL CHECK (source IN ('cafef_transfer', 'kbs_listing')),
    PRIMARY KEY (symbol, source, valid_from)
);
