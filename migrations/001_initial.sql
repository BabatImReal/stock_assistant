-- Phase 4 initial schema. See agent-memory/knowledge/data-model.md (APPROVED).
--
-- Two rules shape everything here:
--   1. bar_raw is permanent and never edited. Everything adjusted is derived
--      and rebuildable, so a new corporate action can only change a derivation.
--   2. Absent is not zero. A missing negotiated_volume row means "unknown",
--      never "there was no block trade".

-- ---------------------------------------------------------------------------
-- Symbol master
-- ---------------------------------------------------------------------------

-- Only 3-letter tickers. CafeF's HOSE file carries 2,535 symbols but only 474
-- are stocks; the rest are covered warrants (CACB2101). Without this filter
-- every count, base rate and scan is four times too big.
CREATE TABLE IF NOT EXISTS symbol (
    symbol            text PRIMARY KEY CHECK (symbol ~ '^[A-Z]{3}$'),
    first_trade_date  date NOT NULL,
    last_trade_date   date NOT NULL,
    current_exchange  text NOT NULL CHECK (current_exchange IN ('HOSE','HNX','UPCOM')),
    is_active         boolean NOT NULL,
    -- true when part of this symbol's history came from vnstock because CafeF
    -- dropped it at an exchange transfer. Volume-based signals are disabled on
    -- those spans (Ben's decision 2026-09-22).
    has_backfill      boolean NOT NULL DEFAULT false,
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- A symbol's exchange is a PERIOD, not a field: ACB traded on HNX for nine
-- years before moving to HOSE on 2020-12-14 (blocker G4).
CREATE TABLE IF NOT EXISTS symbol_exchange (
    symbol      text NOT NULL REFERENCES symbol(symbol) ON DELETE CASCADE,
    exchange    text NOT NULL CHECK (exchange IN ('HOSE','HNX','UPCOM')),
    valid_from  date NOT NULL,
    valid_to    date,              -- NULL = still trading there
    source      text NOT NULL,     -- 'cafef' or 'vnstock'
    PRIMARY KEY (symbol, valid_from)
);

-- ---------------------------------------------------------------------------
-- The permanent record
-- ---------------------------------------------------------------------------

-- Unadjusted bars exactly as published. Append-only: a corporate action does
-- not change what traded that day, so nothing here is ever rewritten.
CREATE TABLE IF NOT EXISTS bar_raw (
    symbol          text NOT NULL,
    trade_date      date NOT NULL,
    open            numeric(18,4) NOT NULL CHECK (open > 0),
    high            numeric(18,4) NOT NULL CHECK (high > 0),
    low             numeric(18,4) NOT NULL CHECK (low  > 0),
    close           numeric(18,4) NOT NULL CHECK (close > 0),
    -- Confirmed matched-only (khop lenh) by the G12 test: 20/20 on the days
    -- with the largest negotiated deals. This is the number doc §4.3 requires.
    matched_volume  bigint NOT NULL CHECK (matched_volume >= 0),
    exchange        text NOT NULL CHECK (exchange IN ('HOSE','HNX','UPCOM')),
    source          text NOT NULL,   -- 'cafef' | 'vnstock'
    -- vnstock returns ADJUSTED prices only, so a backfilled span has no
    -- unadjusted price, no derivable factor and therefore no adjustable volume.
    -- Price patterns and trend are fine on these; volume signals are not.
    is_adjusted_source boolean NOT NULL DEFAULT false,
    source_file     text,            -- which zip/CSV this row came from
    loaded_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, trade_date),
    CHECK (low <= open AND low <= close AND high >= open AND high >= close)
);

-- ---------------------------------------------------------------------------
-- Adjustment: versioned factors, rebuildable bars
-- ---------------------------------------------------------------------------

-- One row per rebuild. A new corporate action restates past adjusted prices, so
-- instead of editing them we create a new build and rebuild. Research results
-- record which build they were measured on, which is what makes an old number
-- reproducible.
CREATE TABLE IF NOT EXISTS adjustment_build (
    build_id     bigserial PRIMARY KEY,
    created_at   timestamptz NOT NULL DEFAULT now(),
    reason       text NOT NULL,          -- 'initial load', 'restatement: VNM', ...
    cafef_file_date date,                -- which CafeF publication it came from
    symbols_changed integer,             -- how many symbols' past factors moved
    status       text NOT NULL DEFAULT 'building'
                 CHECK (status IN ('building','good','failed')),
    notes        text
);

-- factor = adjusted close / unadjusted close, straight from CafeF's two files.
-- Append-only per build; old factors are kept because they are tiny, while old
-- bars are not kept because they regenerate from raw + factors.
CREATE TABLE IF NOT EXISTS adjustment_factor (
    symbol      text NOT NULL,
    trade_date  date NOT NULL,
    build_id    bigint NOT NULL REFERENCES adjustment_build(build_id),
    factor      numeric(18,10) NOT NULL CHECK (factor > 0),
    PRIMARY KEY (symbol, trade_date, build_id)
);

-- Derived and disposable. Price x factor, volume / factor.
-- CafeF adjusts price but NOT volume (verified: adjusted and unadjusted volume
-- identical on 100% of days), so without the division RVOL breaks across every
-- stock dividend -- and Vietnamese companies pay them constantly. Blocker G1.
CREATE TABLE IF NOT EXISTS bar_adjusted (
    symbol          text NOT NULL,
    trade_date      date NOT NULL,
    build_id        bigint NOT NULL REFERENCES adjustment_build(build_id),
    open            numeric(18,6) NOT NULL,
    high            numeric(18,6) NOT NULL,
    low             numeric(18,6) NOT NULL,
    close           numeric(18,6) NOT NULL,
    matched_volume  numeric(20,2) NOT NULL,
    -- false when this span came from a vnstock backfill: the volume could not
    -- be adjusted, so volume-based signals must skip it.
    volume_is_adjustable boolean NOT NULL DEFAULT true,
    PRIMARY KEY (symbol, trade_date, build_id)
);

-- ---------------------------------------------------------------------------
-- Negotiated volume -- absence means UNKNOWN
-- ---------------------------------------------------------------------------

-- From NN_<Low>. A row with 0 means CafeF published a row saying there was no
-- block trade. NO ROW means we do not know: coverage is 97-100% for 2012-2020
-- but only 46% in 2024. Never store a 0 to represent a missing row.
CREATE TABLE IF NOT EXISTS negotiated_volume (
    symbol        text NOT NULL,
    trade_date    date NOT NULL,
    deal_volume   bigint NOT NULL CHECK (deal_volume >= 0),
    source_file   text,
    PRIMARY KEY (symbol, trade_date)
);

-- ---------------------------------------------------------------------------
-- Calendar and index
-- ---------------------------------------------------------------------------

-- Built from STOCK rows, never from the index file, which carries rows dated
-- Saturday 2026-02-07 and Sunday 2026-03-08 on which no stock traded (G14).
-- symbols_traded makes a half-dead session visible instead of silent.
CREATE TABLE IF NOT EXISTS trading_day (
    trade_date      date NOT NULL,
    exchange        text NOT NULL CHECK (exchange IN ('HOSE','HNX','UPCOM')),
    symbols_traded  integer NOT NULL CHECK (symbols_traded > 0),
    PRIMARY KEY (trade_date, exchange)
);

-- VN-Index and HNX-Index, for market regime (doc §5.3) and funnel step 3.
-- Weekend rows are rejected at load time, not stored and filtered later.
CREATE TABLE IF NOT EXISTS index_bar (
    symbol      text NOT NULL,
    trade_date  date NOT NULL,
    open        numeric(18,4) NOT NULL,
    high        numeric(18,4) NOT NULL,
    low         numeric(18,4) NOT NULL,
    close       numeric(18,4) NOT NULL,
    volume      bigint NOT NULL,
    PRIMARY KEY (symbol, trade_date)
);

-- ---------------------------------------------------------------------------
-- Reconciliation and research provenance
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reconciliation_run (
    run_id           bigserial PRIMARY KEY,
    started_at       timestamptz NOT NULL DEFAULT now(),
    scope            text NOT NULL,   -- 'historical-sample' | 'nightly-liquid' | 'weekly-full'
    left_source      text NOT NULL,
    right_source     text NOT NULL,
    date_from        date,
    date_to          date,
    symbols_checked  integer,
    price_tolerance  numeric(10,6),
    volume_tolerance numeric(10,6),
    compared         integer,
    matched          integer,
    passed           boolean,
    notes            text
);

-- Storing the RATIO matters as much as the difference: a constant ratio is an
-- adjustment-policy difference between sources (VNM's 0.9835), while scattered
-- ratios are corruption. Only the second should fail a build.
CREATE TABLE IF NOT EXISTS reconciliation_mismatch (
    run_id      bigint NOT NULL REFERENCES reconciliation_run(run_id) ON DELETE CASCADE,
    symbol      text NOT NULL,
    trade_date  date NOT NULL,
    column_name text NOT NULL,
    left_value  numeric(20,6),
    right_value numeric(20,6),
    rel_diff    numeric(20,10),
    ratio       numeric(20,10),
    PRIMARY KEY (run_id, symbol, trade_date, column_name)
);

-- Every research result records the build it was measured on, so a number from
-- last week stays reproducible after a restatement (Ben, 2026-09-22).
CREATE TABLE IF NOT EXISTS research_result (
    result_id    bigserial PRIMARY KEY,
    created_at   timestamptz NOT NULL DEFAULT now(),
    build_id     bigint NOT NULL REFERENCES adjustment_build(build_id),
    kind         text NOT NULL,     -- 'pattern-stats' | 'base-rate' | 'scan' ...
    symbol       text,
    params       jsonb NOT NULL DEFAULT '{}'::jsonb,
    metrics      jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes        text
);

-- ---------------------------------------------------------------------------
-- Data-quality check results
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quality_check (
    check_id    bigserial PRIMARY KEY,
    run_at      timestamptz NOT NULL DEFAULT now(),
    build_id    bigint REFERENCES adjustment_build(build_id),
    name        text NOT NULL,
    passed      boolean NOT NULL,
    severity    text NOT NULL CHECK (severity IN ('fail','warn')),
    observed    text,
    detail      jsonb NOT NULL DEFAULT '{}'::jsonb
);
